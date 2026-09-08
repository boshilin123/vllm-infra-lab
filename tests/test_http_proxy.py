from __future__ import annotations

import http.client
import json
import socket
import struct
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from router.http_proxy import BackendHealthChecker, LeastInflightProxyServer
from router.least_inflight import BackendConfig, LeastInflightRouter


@dataclass
class MockState:
    name: str
    healthy: bool = True
    requests: int = 0
    active: int = 0
    started: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)
    first_chunk_sent: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)


def mock_handler(state: MockState) -> type[BaseHTTPRequestHandler]:
    class MockBackendHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/health":
                self.send_error(404)
                return
            status = 200 if state.healthy else 503
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length:
                self.rfile.read(content_length)
            with state.lock:
                state.requests += 1
                state.active += 1
            state.started.set()
            try:
                if self.path in {"/blocked", "/balanced"}:
                    state.release.wait(timeout=5)
                    self._json_response()
                elif self.path == "/stream":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(b"data: first\n\n")
                    self.wfile.flush()
                    state.first_chunk_sent.set()
                    state.release.wait(timeout=5)
                    self.wfile.write(b"data: second\n\n")
                    self.wfile.flush()
                elif self.path == "/disconnect":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(b"data: first\n\n")
                    self.wfile.flush()
                    state.first_chunk_sent.set()
                    state.release.wait(timeout=5)
                    for _ in range(32):
                        self.wfile.write(b"x" * (64 * 1024))
                        self.wfile.flush()
                else:
                    self._json_response()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with state.lock:
                    state.active -= 1

        def _json_response(self) -> None:
            body = json.dumps({"backend": state.name}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return MockBackendHandler


def start_server(server: ThreadingHTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def wait_until(predicate: object, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if callable(predicate) and predicate():
            return
        time.sleep(0.01)
    raise AssertionError("等待条件超时")


class HttpProxyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.states = [MockState("a"), MockState("b")]
        self.backends: list[ThreadingHTTPServer] = []
        configs = []
        for state in self.states:
            server = ThreadingHTTPServer(("127.0.0.1", 0), mock_handler(state))
            server.daemon_threads = True
            start_server(server)
            self.backends.append(server)
            configs.append(
                BackendConfig(state.name, f"http://127.0.0.1:{server.server_port}")
            )
        self.router = LeastInflightRouter(configs)
        self.proxy = LeastInflightProxyServer(("127.0.0.1", 0), self.router, 5)
        start_server(self.proxy)

    def tearDown(self) -> None:
        self.proxy.shutdown()
        self.proxy.server_close()
        for server in self.backends:
            server.shutdown()
            server.server_close()

    def request(self, path: str) -> tuple[int, bytes, dict[str, str]]:
        connection = http.client.HTTPConnection("127.0.0.1", self.proxy.server_port, 5)
        connection.request("POST", path, body=b"{}", headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        status = response.status
        headers = {name.lower(): value for name, value in response.getheaders()}
        body = response.read()
        connection.close()
        return status, body, headers

    def get(self, path: str) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.proxy.server_port, 5)
        connection.request("GET", path)
        response = connection.getresponse()
        status = response.status
        body = response.read()
        connection.close()
        return status, body

    def loads(self) -> dict[str, int]:
        return {snapshot.name: snapshot.in_flight for snapshot in self.router.snapshots()}

    def test_non_streaming_lease_released_after_response(self) -> None:
        future_result: list[tuple[int, bytes, dict[str, str]]] = []
        thread = threading.Thread(
            target=lambda: future_result.append(self.request("/blocked")), daemon=True
        )
        thread.start()
        self.assertTrue(self.states[0].started.wait(timeout=2))
        self.assertEqual(self.loads(), {"a": 1, "b": 0})
        self.states[0].release.set()
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(future_result[0][0], 200)
        self.assertEqual(self.loads(), {"a": 0, "b": 0})

    def test_sse_lease_stays_held_after_headers_until_stream_ends(self) -> None:
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.proxy.server_port, timeout=3
        )
        connection.request("POST", "/stream", body=b"{}")
        response = connection.getresponse()
        first_event = response.read(len(b"data: first\n\n"))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/event-stream")
        self.assertEqual(first_event, b"data: first\n\n")
        self.assertEqual(self.loads(), {"a": 1, "b": 0})
        self.states[0].release.set()
        self.assertEqual(response.read(), b"data: second\n\n")
        connection.close()
        wait_until(lambda: self.loads() == {"a": 0, "b": 0})
        self.assertEqual(self.loads(), {"a": 0, "b": 0})

    def test_client_disconnect_releases_streaming_lease(self) -> None:
        client = socket.create_connection(("127.0.0.1", self.proxy.server_port), timeout=2)
        client.sendall(
            b"POST /disconnect HTTP/1.0\r\nHost: proxy\r\nContent-Length: 2\r\n\r\n{}"
        )
        received = b""
        while b"data: first\n\n" not in received:
            received += client.recv(4096)
        self.assertEqual(self.loads(), {"a": 1, "b": 0})
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        client.close()
        self.states[0].release.set()
        wait_until(lambda: self.loads() == {"a": 0, "b": 0})

    def test_upstream_connection_error_returns_502_and_releases(self) -> None:
        unavailable = socket.socket()
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        unavailable.close()
        router = LeastInflightRouter([BackendConfig("down", f"http://127.0.0.1:{port}")])
        proxy = LeastInflightProxyServer(("127.0.0.1", 0), router, 0.2)
        start_server(proxy)
        try:
            connection = http.client.HTTPConnection("127.0.0.1", proxy.server_port, 2)
            connection.request("POST", "/v1/chat/completions", body=b"{}")
            response = connection.getresponse()
            self.assertEqual(response.status, 502)
            response.read()
            connection.close()
            self.assertEqual(router.snapshots()[0].in_flight, 0)
            self.assertEqual(router.snapshots()[0].selections_total, 1)
        finally:
            proxy.shutdown()
            proxy.server_close()

    def test_sent_request_is_not_retried_on_another_backend(self) -> None:
        unavailable = socket.socket()
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        unavailable.close()
        healthy_port = self.backends[1].server_port
        router = LeastInflightRouter(
            [
                BackendConfig("down", f"http://127.0.0.1:{port}"),
                BackendConfig("healthy", f"http://127.0.0.1:{healthy_port}"),
            ]
        )
        proxy = LeastInflightProxyServer(("127.0.0.1", 0), router, 0.2)
        start_server(proxy)
        try:
            connection = http.client.HTTPConnection("127.0.0.1", proxy.server_port, 2)
            connection.request("POST", "/ready", body=b"{}")
            response = connection.getresponse()
            self.assertEqual(response.status, 502)
            response.read()
            connection.close()
            snapshots = router.snapshots()
            self.assertEqual([item.selections_total for item in snapshots], [1, 0])
            self.assertEqual(self.states[1].requests, 0)
        finally:
            proxy.shutdown()
            proxy.server_close()

    def test_health_check_removes_and_restores_backend(self) -> None:
        checker = BackendHealthChecker(self.router, interval=1, timeout=1)
        self.states[0].healthy = False
        self.assertEqual(checker.check_once(), {"a": False, "b": True})
        status, body, _ = self.request("/ready")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["backend"], "b")
        self.states[0].healthy = True
        self.assertEqual(checker.check_once(), {"a": True, "b": True})

    def test_all_unhealthy_returns_503_without_selection(self) -> None:
        for state in self.states:
            state.healthy = False
        checker = BackendHealthChecker(self.router, interval=1, timeout=1)
        checker.check_once()
        status, body, _ = self.request("/v1/chat/completions")
        self.assertEqual(status, 503)
        self.assertIn("没有健康后端", json.loads(body)["error"])
        self.assertEqual(
            [snapshot.selections_total for snapshot in self.router.snapshots()], [0, 0]
        )

    def test_status_endpoint_is_local_and_does_not_select_backend(self) -> None:
        lease = self.router.acquire()
        status, body = self.get("/_router/status")
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["policy"], "least-inflight")
        self.assertEqual(
            [
                (item["name"], item["healthy"], item["in_flight"], item["selections_total"])
                for item in payload["backends"]
            ],
            [("a", True, 1, 1), ("b", True, 0, 0)],
        )
        self.assertEqual([state.requests for state in self.states], [0, 0])
        lease.release()

    def test_sixteen_held_http_requests_split_eight_eight(self) -> None:
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(self.request, "/balanced") for _ in range(16)]
            wait_until(lambda: sum(state.active for state in self.states) == 16)
            self.assertEqual(self.loads(), {"a": 8, "b": 8})
            self.assertEqual([state.requests for state in self.states], [8, 8])
            for state in self.states:
                state.release.set()
            results = [future.result(timeout=3) for future in futures]
        self.assertTrue(all(status == 200 for status, _, _ in results))
        self.assertEqual(self.loads(), {"a": 0, "b": 0})


if __name__ == "__main__":
    unittest.main()

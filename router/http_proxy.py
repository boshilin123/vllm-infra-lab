"""基于标准库的最小 HTTP/SSE least-inflight 代理。"""

from __future__ import annotations

import argparse
import http.client
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib.parse import SplitResult, urlsplit

from .least_inflight import BackendConfig, LeastInflightRouter, NoHealthyBackends


_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _backend_url(backend: BackendConfig) -> SplitResult:
    parsed = urlsplit(backend.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"后端 {backend.name} 的 URL 必须是 http(s) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"后端 {backend.name} 的 URL 不能包含用户凭据")
    if parsed.query or parsed.fragment:
        raise ValueError(f"后端 {backend.name} 的 URL 不能包含 query 或 fragment")
    return parsed


def _target_path(base: SplitResult, request_path: str) -> str:
    prefix = base.path.rstrip("/")
    suffix = request_path if request_path.startswith("/") else f"/{request_path}"
    return f"{prefix}{suffix}" or "/"


def _connection(base: SplitResult, timeout: float) -> http.client.HTTPConnection:
    connection_type = (
        http.client.HTTPSConnection if base.scheme == "https" else http.client.HTTPConnection
    )
    return connection_type(base.hostname, base.port, timeout=timeout)


def _connection_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token.strip().lower() for token in value.split(",") if token.strip()}


class LeastInflightProxyServer(ThreadingHTTPServer):
    """保存路由状态和上游超时的多线程 HTTP server。"""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        router: LeastInflightRouter,
        upstream_timeout: float = 300.0,
    ) -> None:
        if upstream_timeout <= 0:
            raise ValueError("upstream_timeout 必须大于 0")
        for snapshot in router.snapshots():
            _backend_url(BackendConfig(snapshot.name, snapshot.base_url))
        self.router = router
        self.upstream_timeout = upstream_timeout
        super().__init__(server_address, LeastInflightProxyHandler)


class LeastInflightProxyHandler(BaseHTTPRequestHandler):
    """透明转发常用 HTTP 方法，并让 lease 覆盖完整响应传输。"""

    protocol_version = "HTTP/1.0"
    server: LeastInflightProxyServer

    def do_GET(self) -> None:  # noqa: N802
        if urlsplit(self.path).path == "/_router/status":
            self._router_status()
            return
        self._proxy()

    def do_POST(self) -> None:  # noqa: N802
        self._proxy()

    def do_PUT(self) -> None:  # noqa: N802
        self._proxy()

    def do_PATCH(self) -> None:  # noqa: N802
        self._proxy()

    def do_DELETE(self) -> None:  # noqa: N802
        self._proxy()

    def log_message(self, format: str, *args: object) -> None:
        # 最小离线适配默认不向测试输出写访问日志；生产日志不在本阶段范围内。
        return

    def _proxy(self) -> None:
        transfer_encoding = self.headers.get("Transfer-Encoding", "").lower()
        if transfer_encoding and transfer_encoding != "identity":
            self._send_json(HTTPStatus.NOT_IMPLEMENTED, "不支持 chunked 请求体")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, "Content-Length 无效")
            return
        if content_length < 0:
            self._send_json(HTTPStatus.BAD_REQUEST, "Content-Length 无效")
            return
        body = self.rfile.read(content_length) if content_length else None

        try:
            lease = self.server.router.acquire()
        except NoHealthyBackends:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, "没有健康后端")
            return

        connection: http.client.HTTPConnection | None = None
        response_started = False
        try:
            backend = lease.backend
            parsed = _backend_url(backend)
            connection = _connection(parsed, self.server.upstream_timeout)
            headers = self._upstream_headers(parsed, content_length)
            connection.request(
                self.command,
                _target_path(parsed, self.path),
                body=body,
                headers=headers,
            )
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            self._copy_response_headers(response.getheaders())
            self.send_header("Connection", "close")
            self.end_headers()
            response_started = True

            while True:
                chunk = response.read1(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # 客户端断开后关闭上游连接，并由 finally 释放 lease。
            self.close_connection = True
        except (OSError, http.client.HTTPException, ValueError) as error:
            if not response_started:
                self._send_json(HTTPStatus.BAD_GATEWAY, f"上游请求失败: {type(error).__name__}")
            self.close_connection = True
        finally:
            if connection is not None:
                connection.close()
            lease.release()

    def _upstream_headers(
        self, parsed: SplitResult, content_length: int
    ) -> dict[str, str]:
        connection_headers = _connection_tokens(self.headers.get("Connection"))
        excluded = _HOP_BY_HOP_HEADERS | connection_headers | {"host", "content-length"}
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in excluded
        }
        host = parsed.hostname or ""
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        headers["Host"] = host
        headers["Connection"] = "close"
        if content_length:
            headers["Content-Length"] = str(content_length)
        return headers

    def _copy_response_headers(self, headers: Iterable[tuple[str, str]]) -> None:
        header_list = list(headers)
        connection_value = next(
            (value for name, value in header_list if name.lower() == "connection"), None
        )
        excluded = (
            _HOP_BY_HOP_HEADERS
            | _connection_tokens(connection_value)
            | {"content-length"}
        )
        for name, value in header_list:
            if name.lower() not in excluded:
                self.send_header(name, value)

    def _send_json(self, status: HTTPStatus, message: str) -> None:
        self._send_json_payload(status, {"error": message})

    def _router_status(self) -> None:
        snapshots = self.server.router.snapshots()
        self._send_json_payload(
            HTTPStatus.OK,
            {
                "policy": "least-inflight",
                "backends": [
                    {
                        "name": snapshot.name,
                        "base_url": snapshot.base_url,
                        "healthy": snapshot.healthy,
                        "in_flight": snapshot.in_flight,
                        "selections_total": snapshot.selections_total,
                    }
                    for snapshot in snapshots
                ],
            },
        )

    def _send_json_payload(self, status: HTTPStatus, value: object) -> None:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True


class BackendHealthChecker:
    """用后端健康端点更新新请求选择资格。"""

    def __init__(
        self,
        router: LeastInflightRouter,
        path: str = "/health",
        interval: float = 5.0,
        timeout: float = 2.0,
    ) -> None:
        if not path.startswith("/"):
            raise ValueError("健康检查 path 必须以 / 开头")
        if interval <= 0 or timeout <= 0:
            raise ValueError("健康检查 interval 和 timeout 必须大于 0")
        self._router = router
        self._path = path
        self._interval = interval
        self._timeout = timeout
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check_once(self) -> dict[str, bool]:
        """立即探测所有后端；2xx 视为健康，失败则摘除新流量。"""

        results: dict[str, bool] = {}
        for snapshot in self._router.snapshots():
            backend = BackendConfig(snapshot.name, snapshot.base_url)
            connection: http.client.HTTPConnection | None = None
            healthy = False
            try:
                parsed = _backend_url(backend)
                connection = _connection(parsed, self._timeout)
                connection.request(
                    "GET",
                    _target_path(parsed, self._path),
                    headers={"Connection": "close"},
                )
                response = connection.getresponse()
                response.read()
                healthy = 200 <= response.status < 300
            except (OSError, http.client.HTTPException, ValueError):
                healthy = False
            finally:
                if connection is not None:
                    connection.close()
            self._router.mark_healthy(snapshot.name, healthy)
            results[snapshot.name] = healthy
        return results

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="backend-health-checker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval + self._timeout + 1)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.check_once()
            self._stop.wait(self._interval)


def _parse_backend(value: str) -> BackendConfig:
    try:
        name, base_url = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("后端格式必须为 NAME=URL") from error
    backend = BackendConfig(name.strip(), base_url.strip())
    try:
        if not backend.name:
            raise ValueError("后端 name 不能为空")
        _backend_url(backend)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return backend


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        action="append",
        required=True,
        type=_parse_backend,
        metavar="NAME=URL",
        help="可重复传入，例如 replica-a=http://127.0.0.1:8001",
    )
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8080)
    parser.add_argument("--upstream-timeout", type=float, default=300.0)
    parser.add_argument("--health-path", default="/health")
    parser.add_argument("--health-interval", type=float, default=5.0)
    parser.add_argument("--health-timeout", type=float, default=2.0)
    args = parser.parse_args()

    router = LeastInflightRouter(args.backend)
    server = LeastInflightProxyServer(
        (args.listen_host, args.listen_port),
        router,
        upstream_timeout=args.upstream_timeout,
    )
    health_checker = BackendHealthChecker(
        router,
        path=args.health_path,
        interval=args.health_interval,
        timeout=args.health_timeout,
    )
    health_checker.check_once()
    health_checker.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        health_checker.stop()
        server.server_close()


if __name__ == "__main__":
    main()

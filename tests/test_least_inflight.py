from __future__ import annotations

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from router import BackendConfig, LeastInflightRouter, NoHealthyBackends


def build_router() -> LeastInflightRouter:
    return LeastInflightRouter(
        [
            BackendConfig("a", "http://a:8000"),
            BackendConfig("b", "http://b:8000"),
        ]
    )


def loads(router: LeastInflightRouter) -> dict[str, int]:
    return {snapshot.name: snapshot.in_flight for snapshot in router.snapshots()}


class LeastInflightRouterTest(unittest.TestCase):
    def test_sixteen_held_requests_split_eight_eight(self) -> None:
        router = build_router()
        leases = [router.acquire() for _ in range(16)]
        self.assertEqual(loads(router), {"a": 8, "b": 8})
        for lease in leases:
            lease.release()
        self.assertEqual(loads(router), {"a": 0, "b": 0})

    def test_equal_load_uses_round_robin_tie_break(self) -> None:
        router = build_router()
        selected = []
        for _ in range(4):
            with router.acquire() as lease:
                selected.append(lease.backend.name)
        self.assertEqual(selected, ["a", "b", "a", "b"])

    def test_lease_stays_in_flight_until_full_lifecycle_ends(self) -> None:
        router = build_router()
        lease = router.acquire()
        self.assertEqual(loads(router), {"a": 1, "b": 0})
        self.assertFalse(lease.released)
        lease.release()
        lease.release()
        self.assertTrue(lease.released)
        self.assertEqual(loads(router), {"a": 0, "b": 0})

    def test_context_manager_releases_after_exception(self) -> None:
        router = build_router()
        with self.assertRaisesRegex(RuntimeError, "backend failed"):
            with router.acquire():
                raise RuntimeError("backend failed")
        self.assertEqual(loads(router), {"a": 0, "b": 0})

    def test_unhealthy_backend_rejects_new_but_keeps_existing_lease(self) -> None:
        router = build_router()
        existing = router.acquire()
        router.mark_healthy("a", False)
        new = router.acquire()
        self.assertEqual(existing.backend.name, "a")
        self.assertEqual(new.backend.name, "b")
        self.assertEqual(loads(router), {"a": 1, "b": 1})
        existing.release()
        new.release()

    def test_all_unhealthy_fails_fast(self) -> None:
        router = build_router()
        router.mark_healthy("a", False)
        router.mark_healthy("b", False)
        with self.assertRaises(NoHealthyBackends):
            router.acquire()

    def test_concurrent_acquire_is_atomic_and_balanced(self) -> None:
        router = build_router()
        acquired = threading.Barrier(17)
        release = threading.Event()

        def hold_request() -> None:
            lease = router.acquire()
            acquired.wait(timeout=5)
            release.wait(timeout=5)
            lease.release()

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(hold_request) for _ in range(16)]
            acquired.wait(timeout=5)
            self.assertEqual(loads(router), {"a": 8, "b": 8})
            release.set()
            for future in futures:
                future.result(timeout=5)
        self.assertEqual(loads(router), {"a": 0, "b": 0})


if __name__ == "__main__":
    unittest.main()

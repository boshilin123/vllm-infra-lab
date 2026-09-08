"""线程安全的 least-inflight 后端选择与请求生命周期记账。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from types import TracebackType


@dataclass(frozen=True)
class BackendConfig:
    """可被路由器选择的一个后端。"""

    name: str
    base_url: str


@dataclass(frozen=True)
class BackendSnapshot:
    """某一时刻的后端状态快照。"""

    name: str
    base_url: str
    healthy: bool
    in_flight: int
    selections_total: int


@dataclass
class _BackendState:
    config: BackendConfig
    healthy: bool = True
    in_flight: int = 0
    selections_total: int = 0


class NoHealthyBackends(RuntimeError):
    """当前没有可以接收新请求的健康后端。"""


class BackendLease:
    """一次已计入 in-flight 的后端租约，完成或失败时必须释放。"""

    def __init__(self, router: LeastInflightRouter, backend: BackendConfig) -> None:
        self._router = router
        self._backend = backend
        self._released = False
        self._release_lock = threading.Lock()

    @property
    def backend(self) -> BackendConfig:
        return self._backend

    @property
    def released(self) -> bool:
        with self._release_lock:
            return self._released

    def release(self) -> None:
        """恰好释放一次；重复调用是安全的。"""

        with self._release_lock:
            if self._released:
                return
            self._router._release(self._backend.name)
            self._released = True

    def __enter__(self) -> BackendLease:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


class LeastInflightRouter:
    """选择健康且 in-flight 最少的后端，并原子增加其计数。"""

    def __init__(self, backends: list[BackendConfig]) -> None:
        if not backends:
            raise ValueError("至少需要一个后端")
        names = [backend.name for backend in backends]
        if any(not name.strip() for name in names):
            raise ValueError("后端 name 不能为空")
        if len(set(names)) != len(names):
            raise ValueError("后端 name 必须唯一")
        if any(not backend.base_url.strip() for backend in backends):
            raise ValueError("后端 base_url 不能为空")

        self._order = tuple(names)
        self._states = {
            backend.name: _BackendState(config=backend) for backend in backends
        }
        self._next_index = 0
        self._lock = threading.Lock()

    def acquire(self) -> BackendLease:
        """原子选择后端并增加 in-flight；没有健康后端时快速失败。"""

        with self._lock:
            healthy = [state for state in self._states.values() if state.healthy]
            if not healthy:
                raise NoHealthyBackends("没有健康后端可接收新请求")
            minimum = min(state.in_flight for state in healthy)
            selected: _BackendState | None = None
            selected_index = self._next_index
            for offset in range(len(self._order)):
                index = (self._next_index + offset) % len(self._order)
                candidate = self._states[self._order[index]]
                if candidate.healthy and candidate.in_flight == minimum:
                    selected = candidate
                    selected_index = index
                    break
            if selected is None:
                raise RuntimeError("健康后端选择状态不一致")
            selected.in_flight += 1
            selected.selections_total += 1
            self._next_index = (selected_index + 1) % len(self._order)
            backend = selected.config
        return BackendLease(self, backend)

    def mark_healthy(self, name: str, healthy: bool) -> None:
        """控制后端是否接收新请求，不中断已经持有的租约。"""

        with self._lock:
            state = self._get_state(name)
            state.healthy = healthy

    def snapshots(self) -> tuple[BackendSnapshot, ...]:
        """按配置顺序返回一致的只读状态快照。"""

        with self._lock:
            return tuple(
                BackendSnapshot(
                    name=state.config.name,
                    base_url=state.config.base_url,
                    healthy=state.healthy,
                    in_flight=state.in_flight,
                    selections_total=state.selections_total,
                )
                for name in self._order
                for state in (self._states[name],)
            )

    def _get_state(self, name: str) -> _BackendState:
        try:
            return self._states[name]
        except KeyError as error:
            raise KeyError(f"未知后端: {name}") from error

    def _release(self, name: str) -> None:
        with self._lock:
            state = self._get_state(name)
            if state.in_flight <= 0:
                raise RuntimeError(f"后端 {name} 的 in-flight 不能低于 0")
            state.in_flight -= 1

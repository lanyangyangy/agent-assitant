from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class _CircuitState:
    failure_count: int = 0
    opened_at: float | None = None
    half_open_probe_in_progress: bool = False


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout_seconds: float = 60):
        if failure_threshold <= 0:
            raise ValueError("熔断失败阈值必须大于 0。")
        if recovery_timeout_seconds < 0:
            raise ValueError("熔断恢复时间不能小于 0。")
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._states: dict[str, _CircuitState] = {}

    def allow_request(self, tool_name: str) -> bool:
        state = self._states.get(tool_name)
        if state is None or state.opened_at is None:
            return True

        if time.monotonic() - state.opened_at < self.recovery_timeout_seconds:
            return False

        if state.half_open_probe_in_progress:
            return False

        state.half_open_probe_in_progress = True
        return True

    def record_failure(self, tool_name: str) -> None:
        state = self._states.setdefault(tool_name, _CircuitState())
        state.failure_count += 1
        if state.opened_at is not None or state.failure_count >= self.failure_threshold:
            state.failure_count = self.failure_threshold
            state.opened_at = time.monotonic()
            state.half_open_probe_in_progress = False

    def record_success(self, tool_name: str) -> None:
        self._states.pop(tool_name, None)

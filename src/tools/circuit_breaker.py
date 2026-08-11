from __future__ import annotations


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3):
        if failure_threshold <= 0:
            raise ValueError("熔断失败阈值必须大于 0。")
        self.failure_threshold = failure_threshold
        self._failure_counts: dict[str, int] = {}

    def allow_request(self, tool_name: str) -> bool:
        return self._failure_counts.get(tool_name, 0) < self.failure_threshold

    def record_failure(self, tool_name: str) -> None:
        self._failure_counts[tool_name] = self._failure_counts.get(tool_name, 0) + 1

    def record_success(self, tool_name: str) -> None:
        self._failure_counts.pop(tool_name, None)

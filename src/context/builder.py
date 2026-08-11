from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
import math
import re
from typing import Any, Callable, Protocol

from src.context.compress import SimpleCompressor
from src.context.history import format_history
from src.context.token_counter import estimate_tokens
from src.core.session_store import MessageRecord


_TEXT_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", re.UNICODE)


class Compressor(Protocol):
    async def compress(self, text: str, task: str | None = None) -> str:
        ...


@dataclass(frozen=True)
class ContextConfig:
    max_tokens: int = 4000
    reserve_ratio: float = 0.2
    min_relevance: float = 0.1
    enable_compression: bool = True
    recency_weight: float = 0.3
    relevance_weight: float = 0.7


@dataclass(frozen=True)
class ContextPacket:
    content: str
    timestamp: str
    relevance_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BuiltContext:
    text: str
    selected_packets: list[ContextPacket]
    compressed: bool


def jaccard_similarity(a: str, b: str) -> float:
    left = set(_tokenize(a))
    right = set(_tokenize(b))
    if not left or not right:
        return 0.0

    return len(left & right) / len(left | right)


class ContextBuilder:
    def __init__(
        self,
        config: ContextConfig | None = None,
        compressor: Compressor | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.config = config or ContextConfig()
        self.compressor = compressor or SimpleCompressor(max_chars=1200)
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    async def build(
        self,
        task: str,
        system_policy: str,
        history: Sequence[MessageRecord],
        memory_packets: Sequence[ContextPacket],
        custom_packets: Sequence[ContextPacket] | None = None,
    ) -> BuiltContext:
        packets = self._select_packets(task, [*memory_packets, *(custom_packets or [])])
        state_block = format_history(history) or "无历史消息。"
        context_block = self._format_context_packets(packets)
        text = self._structure(system_policy, task, state_block, context_block)

        compressed = False
        if self._needs_compression(text) and self.config.enable_compression and context_block.strip():
            context_block = await self.compressor.compress(context_block, task=task)
            text = self._structure(system_policy, task, state_block, context_block)
            compressed = True

        return BuiltContext(text=text, selected_packets=packets, compressed=compressed)

    def _select_packets(self, task: str, packets: list[ContextPacket]) -> list[ContextPacket]:
        scored_packets = []
        for packet in packets:
            store_score = _clamp(packet.relevance_score)
            text_score = jaccard_similarity(task, packet.content)
            relevance_score = max(store_score, text_score)
            if relevance_score < self.config.min_relevance:
                continue

            recency_score = self._recency_score(packet.timestamp)
            final_score = (
                self.config.relevance_weight * relevance_score
                + self.config.recency_weight * recency_score
            )
            scored_packets.append((final_score, relevance_score, recency_score, packet))

        scored_packets.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [packet for _, _, _, packet in scored_packets]

    def _needs_compression(self, text: str) -> bool:
        usable_budget = int(self.config.max_tokens * (1 - self.config.reserve_ratio))
        return estimate_tokens(text) > max(1, usable_budget)

    @staticmethod
    def _format_context_packets(packets: Sequence[ContextPacket]) -> str:
        if not packets:
            return "无可用上下文。"

        lines = []
        for packet in packets:
            lines.append(f"- {packet.content.strip()}")
        return "\n".join(lines)

    @staticmethod
    def _structure(system_policy: str, task: str, state_block: str, context_block: str) -> str:
        return "\n\n".join(
            [
                "[Role & Policies]\n" + (system_policy.strip() or "无额外系统策略。"),
                "[Task]\n" + (task.strip() or "无明确任务。"),
                "[State]\n" + state_block,
                "[Context]\n" + context_block,
                "[Output]\n请基于以上信息直接完成任务；如需工具，请先给出可执行的工具调用。",
            ]
        )

    def _recency_score(self, timestamp: str) -> float:
        parsed = _parse_timestamp(timestamp)
        if parsed is None:
            return 0.1

        now = _normalize_datetime(self.now_provider())
        age_hours = max(0.0, (now - parsed).total_seconds() / 3600)
        return _clamp_to_range(math.exp(-0.1 * age_hours / 24), minimum=0.1, maximum=1.0)


def _tokenize(text: str) -> Iterable[str]:
    for token in _TEXT_TOKEN_RE.findall(text.lower()):
        yield token


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _clamp_to_range(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
import re
from typing import Any, Protocol

from src.context.compress import SimpleCompressor
from src.context.history import format_history
from src.context.token_counter import estimate_tokens
from src.core.session_store import MessageRecord


_TEXT_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", re.UNICODE)


class Compressor(Protocol):
    def compress(self, text: str, task: str | None = None) -> str:
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
    ):
        self.config = config or ContextConfig()
        self.compressor = compressor or SimpleCompressor(max_chars=1200)

    def build(
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
            context_block = self.compressor.compress(context_block, task=task)
            text = self._structure(system_policy, task, state_block, context_block)
            compressed = True

        return BuiltContext(text=text, selected_packets=packets, compressed=compressed)

    def _select_packets(self, task: str, packets: list[ContextPacket]) -> list[ContextPacket]:
        scored_packets = []
        recency_scores = self._recency_scores(packets)
        for index, packet in enumerate(packets):
            store_score = _clamp(packet.relevance_score)
            text_score = jaccard_similarity(task, packet.content)
            if max(store_score, text_score) < self.config.min_relevance:
                continue

            relevance = (0.65 * text_score) + (0.35 * store_score)
            final_score = (
                self.config.relevance_weight * relevance
                + self.config.recency_weight * recency_scores[index]
            )
            scored_packets.append((final_score, relevance, recency_scores[index], packet))

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

    @staticmethod
    def _recency_scores(packets: Sequence[ContextPacket]) -> list[float]:
        if not packets:
            return []

        timestamps = [_parse_timestamp(packet.timestamp) for packet in packets]
        valid_timestamps = [timestamp for timestamp in timestamps if timestamp is not None]
        if not valid_timestamps:
            return [0.0 for _ in packets]
        if len(set(valid_timestamps)) == 1:
            return [1.0 if timestamp is not None else 0.0 for timestamp in timestamps]

        oldest = min(valid_timestamps)
        newest = max(valid_timestamps)
        span = (newest - oldest).total_seconds()
        if span <= 0:
            return [1.0 if timestamp is not None else 0.0 for timestamp in timestamps]

        return [
            0.0 if timestamp is None else (timestamp - oldest).total_seconds() / span
            for timestamp in timestamps
        ]


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


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.context.builder import BuiltContext, ContextBuilder, ContextConfig, ContextPacket
from src.context.token_counter import estimate_tokens
from src.context.history import format_history
from src.context.compress import SimpleCompressor
from src.context.builder import jaccard_similarity
from src.core.session_store import MessageRecord


@dataclass
class RecordingCompressor:
    replacement: str = "压缩后的上下文"
    called_with: str | None = None

    def compress(self, text: str, task: str | None = None) -> str:
        self.called_with = text
        return self.replacement


def _message(message_id: int, role: str, content: str) -> MessageRecord:
    return MessageRecord(
        id=message_id,
        user_id="alice",
        session_id="s1",
        role=role,
        content=content,
        created_at=f"2026-08-11T00:00:{message_id:02d}+00:00",
    )


def test_estimate_tokens_counts_english_and_chinese_lightly():
    assert estimate_tokens("hello world") >= 2
    assert estimate_tokens("你好世界") >= 2
    assert estimate_tokens("") == 0


def test_jaccard_similarity_matches_english_words_and_chinese_characters():
    assert jaccard_similarity("calculator tool weather", "use calculator tool") == pytest.approx(
        0.5
    )
    assert jaccard_similarity("请使用计算器工具", "计算器可以求和") > 0.1
    assert jaccard_similarity("", "anything") == 0.0


def test_format_history_uses_message_records_in_order():
    history = [
        _message(1, "user", "你好"),
        _message(2, "assistant", "我在"),
    ]

    assert format_history(history) == "user: 你好\nassistant: 我在"


def test_context_builder_sorts_by_relevance_recency_and_store_score():
    builder = ContextBuilder(
        ContextConfig(
            max_tokens=800,
            recency_weight=0.4,
            relevance_weight=0.6,
            enable_compression=False,
        )
    )
    packets = [
        ContextPacket("旧的计算器事实", "2026-08-10T00:00:00+00:00", 0.95, {"id": "old"}),
        ContextPacket("新的无关闲聊", "2026-08-12T00:00:00+00:00", 0.05, {"id": "new"}),
        ContextPacket("calculator tool can add numbers", "2026-08-11T00:00:00+00:00", 0.2, {"id": "mid"}),
    ]

    result = builder.build(
        task="Use calculator to add numbers",
        system_policy="遵守安全策略",
        history=[],
        memory_packets=packets,
    )

    assert isinstance(result, BuiltContext)
    assert result.compressed is False
    assert [packet.metadata["id"] for packet in result.selected_packets[:2]] == ["mid", "old"]


def test_context_builder_outputs_required_sections_and_history():
    builder = ContextBuilder(ContextConfig(max_tokens=800, enable_compression=False))
    history = [_message(1, "user", "之前问过天气"), _message(2, "assistant", "回答过天气")]
    packets = [ContextPacket("天气工具需要城市名", "2026-08-11T00:00:00+00:00", 0.7, {"kind": "fact"})]

    result = builder.build(
        task="查询北京天气",
        system_policy="你是中文助手",
        history=history,
        memory_packets=packets,
        custom_packets=[ContextPacket("优先简洁回答", "2026-08-12T00:00:00+00:00", 1.0, {"kind": "custom"})],
    )

    for section in ("[Role & Policies]", "[Task]", "[State]", "[Context]", "[Output]"):
        assert section in result.text
    assert "user: 之前问过天气" in result.text
    assert "assistant: 回答过天气" in result.text
    assert "天气工具需要城市名" in result.text
    assert "优先简洁回答" in result.text


def test_context_builder_compresses_only_context_section_when_over_budget():
    compressor = RecordingCompressor()
    builder = ContextBuilder(
        ContextConfig(max_tokens=35, enable_compression=True),
        compressor=compressor,
    )
    packets = [
        ContextPacket(
            "第一条很长的上下文，需要被压缩。" * 12,
            "2026-08-11T00:00:00+00:00",
            1.0,
            {"id": "long"},
        )
    ]

    result = builder.build(
        task="总结上下文",
        system_policy="保持中文",
        history=[_message(1, "user", "历史不应被压缩")],
        memory_packets=packets,
    )

    assert result.compressed is True
    assert compressor.called_with is not None
    assert "[Role & Policies]" not in compressor.called_with
    assert "[Task]" not in compressor.called_with
    assert "第一条很长的上下文" in compressor.called_with
    assert "压缩后的上下文" in result.text
    assert "历史不应被压缩" in result.text


def test_simple_compressor_keeps_a_short_chinese_summary():
    compressor = SimpleCompressor(max_chars=12)

    assert compressor.compress("这是一个很长的上下文片段") == "这是一个很长的上下..."

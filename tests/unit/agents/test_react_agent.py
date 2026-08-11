from __future__ import annotations

from dataclasses import dataclass
import json
from types import SimpleNamespace
from typing import Any

import pytest

from src.agents.react_agent import ReactAgent
from src.context.builder import BuiltContext, ContextPacket
from src.core.session_store import MessageRecord, SessionRecord
from src.tools.errors import ToolErrorCode
from src.tools.response import ToolResponse


@dataclass
class FakeTraceLogger:
    events: list[tuple[str, str, dict[str, Any]]]

    def log_event(self, trace_id: str, event) -> None:
        self.events.append((trace_id, event.type, event.data))


class FakeSessionStore:
    def __init__(self, exists: bool = True):
        self.exists = exists
        self.added: list[tuple[str, str, str, str]] = []
        self.history: list[MessageRecord] = []

    async def get_session(self, user_id: str, session_id: str):
        if not self.exists:
            return None
        return SessionRecord(session_id=session_id, user_id=user_id, created_at="2026-08-11T00:00:00+00:00")

    async def add_message(self, user_id: str, session_id: str, role: str, content: str):
        self.added.append((user_id, session_id, role, content))
        record = MessageRecord(
            id=len(self.history) + 1,
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            created_at=f"2026-08-11T00:00:{len(self.history):02d}+00:00",
        )
        self.history.append(record)
        return record

    async def get_recent_messages(self, user_id: str, session_id: str, limit: int = 10):
        return self.history[-limit:]


class FakeMemoryStore:
    def __init__(self):
        self.search_calls: list[tuple[str, str, str, int]] = []
        self.added: list[tuple[str, str, str, dict[str, Any]]] = []
        self.records = [
            SimpleNamespace(
                id=7,
                content="用户喜欢中文回答",
                created_at="2026-08-11T00:00:00+00:00",
                score=0.9,
                metadata={"kind": "preference"},
            )
        ]

    async def search(self, user_id: str, session_id: str, query: str, limit: int = 5):
        self.search_calls.append((user_id, session_id, query, limit))
        return self.records

    async def add(self, user_id: str, session_id: str, content: str, metadata=None):
        self.added.append((user_id, session_id, content, dict(metadata or {})))
        return SimpleNamespace(content=content)


class FakeContextBuilder:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def build(self, task, system_policy, history, memory_packets, custom_packets=None):
        self.calls.append(
            {
                "task": task,
                "system_policy": system_policy,
                "history": history,
                "memory_packets": memory_packets,
                "custom_packets": custom_packets,
            }
        )
        return BuiltContext(
            text="构建后的上下文",
            selected_packets=list(memory_packets),
            compressed=False,
        )


class FakeRegistry:
    def __init__(self):
        self.invocations: list[tuple[str, dict[str, Any]]] = []

    def to_qwen_tools(self):
        return [{"type": "function", "function": {"name": "calculator"}}]

    async def invoke(self, tool_name: str, arguments):
        self.invocations.append((tool_name, dict(arguments)))
        return ToolResponse(success=True, data={"result": 4}, message="调用成功", elapsed_ms=1.0)


class FakeQwenClient:
    def __init__(self, create_message: dict[str, Any], tokens: list[str]):
        self.create_message = create_message
        self.tokens = tokens
        self.create_calls: list[dict[str, Any]] = []
        self.stream_calls: list[list[dict[str, Any]]] = []

    def create_completion(self, messages, tools=None, tool_choice=None):
        self.create_calls.append(
            {"messages": list(messages), "tools": tools, "tool_choice": tool_choice}
        )
        return self.create_message

    def stream_completion(self, messages, tools=None, tool_choice=None):
        self.stream_calls.append(list(messages))
        yield from self.tokens


def _make_agent(qwen_message: dict[str, Any], tokens: list[str], session_exists: bool = True):
    qwen = FakeQwenClient(qwen_message, tokens)
    registry = FakeRegistry()
    builder = FakeContextBuilder()
    session_store = FakeSessionStore(exists=session_exists)
    memory_store = FakeMemoryStore()
    trace_logger = FakeTraceLogger([])
    agent = ReactAgent(qwen, registry, builder, session_store, memory_store, trace_logger)
    return agent, qwen, registry, builder, session_store, memory_store, trace_logger


@pytest.mark.asyncio
async def test_react_agent_executes_calculator_tool_and_saves_streamed_answer():
    tool_call_message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "calculator", "arguments": "{\"expression\":\"2+2\"}"},
            }
        ],
    }
    agent, qwen, registry, builder, session_store, memory_store, trace_logger = _make_agent(
        tool_call_message,
        ["答案是", "4"],
    )

    events = [
        event
        async for event in agent.stream_chat("alice", "s1", "请计算 2+2", metadata={"source": "unit"})
    ]

    assert [event.type for event in events] == [
        "message_start",
        "tool_call",
        "tool_result",
        "token",
        "token",
        "message_end",
    ]
    assert registry.invocations == [("calculator", {"expression": "2+2"})]
    assert isinstance(builder.calls[0]["memory_packets"][0], ContextPacket)
    assert builder.calls[0]["memory_packets"][0].metadata["memory_id"] == 7
    tool_messages = [message for message in qwen.stream_calls[0] if message["role"] == "tool"]
    assert json.loads(tool_messages[0]["content"])["data"] == {"result": 4}
    assert tool_messages[0]["tool_call_id"] == "call-1"
    assert session_store.added[-1] == ("alice", "s1", "assistant", "答案是4")
    assert memory_store.added[-1][2] == "答案是4"
    assert trace_logger.events[-1][1] == "message_end"


@pytest.mark.asyncio
async def test_react_agent_streams_final_answer_when_model_has_no_tool_call():
    agent, qwen, registry, _, session_store, _, _ = _make_agent(
        {"role": "assistant", "content": "无需工具"},
        ["直接", "回答"],
    )

    events = [event async for event in agent.stream_chat("alice", "s1", "你好")]

    assert [event.type for event in events] == ["message_start", "token", "token", "message_end"]
    assert registry.invocations == []
    assert qwen.create_calls[0]["tools"] == [{"type": "function", "function": {"name": "calculator"}}]
    assert session_store.added[-1] == ("alice", "s1", "assistant", "直接回答")


@pytest.mark.asyncio
async def test_react_agent_yields_error_when_session_does_not_exist():
    agent, _, _, _, session_store, memory_store, _ = _make_agent(
        {"role": "assistant", "content": "不会调用"},
        ["不会输出"],
        session_exists=False,
    )

    events = [event async for event in agent.stream_chat("alice", "missing", "你好")]

    assert len(events) == 1
    assert events[0].type == "error"
    assert "会话不存在" in events[0].data["message"]
    assert session_store.added == []
    assert memory_store.search_calls == []


@pytest.mark.asyncio
async def test_react_agent_returns_tool_result_error_for_invalid_arguments_json():
    bad_tool_call = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call-bad",
                "type": "function",
                "function": {"name": "calculator", "arguments": "{bad json"},
            }
        ],
    }
    agent, qwen, registry, _, _, _, _ = _make_agent(bad_tool_call, ["参数有误"])

    events = [event async for event in agent.stream_chat("alice", "s1", "请计算")]

    tool_result = next(event for event in events if event.type == "tool_result")
    tool_messages = [message for message in qwen.stream_calls[0] if message["role"] == "tool"]
    tool_payload = json.loads(tool_messages[0]["content"])
    assert registry.invocations == []
    assert tool_result.data["result"]["success"] is False
    assert tool_payload["error_code"] == ToolErrorCode.INVALID_ARGUMENTS.value
    assert "JSON" in tool_payload["message"]

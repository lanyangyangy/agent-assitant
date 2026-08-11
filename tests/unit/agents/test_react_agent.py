from __future__ import annotations

from dataclasses import dataclass
import inspect
import json
from types import SimpleNamespace
from typing import Any
from uuid import UUID

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
        self.fail_assistant_save = False

    async def get_session(self, user_id: str, session_id: str):
        if not self.exists:
            return None
        return SessionRecord(
            session_id=session_id,
            user_id=user_id,
            created_at="2026-08-11T00:00:00+00:00",
        )

    async def add_message(self, user_id: str, session_id: str, role: str, content: str):
        self.added.append((user_id, session_id, role, content))
        if role == "assistant" and self.fail_assistant_save:
            return None

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
        self.fail_add = False
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
        if self.fail_add:
            raise RuntimeError("memory database down")
        self.added.append((user_id, session_id, content, dict(metadata or {})))
        return SimpleNamespace(content=content)


class FakeContextBuilder:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def build(self, task, system_policy, history, memory_packets, custom_packets=None):
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
        return [
            {"type": "function", "function": {"name": "calculator"}},
            {"type": "function", "function": {"name": "search"}},
        ]

    async def invoke(self, tool_name: str, arguments):
        self.invocations.append((tool_name, dict(arguments)))
        if tool_name == "calculator":
            return ToolResponse(success=True, data={"result": 4}, message="调用成功", elapsed_ms=1.0)
        if tool_name == "search":
            return ToolResponse(
                success=True,
                data={"results": ["北京天气晴"]},
                message="调用成功",
                elapsed_ms=1.0,
            )
        return ToolResponse(success=True, data={"ok": True}, message="调用成功", elapsed_ms=1.0)


class FakeQwenClient:
    def __init__(
        self,
        create_messages: list[dict[str, Any]] | None = None,
        tokens: list[str] | None = None,
        create_exception: Exception | None = None,
        stream_exception_after: int | None = None,
    ):
        self.create_messages = create_messages or [{"role": "assistant", "content": "无需工具"}]
        self.tokens = tokens or []
        self.create_exception = create_exception
        self.stream_exception_after = stream_exception_after
        self.create_calls: list[dict[str, Any]] = []
        self.stream_calls: list[list[dict[str, Any]]] = []

    async def create_completion(self, messages, tools=None, tool_choice=None):
        self.create_calls.append(
            {"messages": list(messages), "tools": tools, "tool_choice": tool_choice}
        )
        if self.create_exception is not None:
            raise self.create_exception
        index = min(len(self.create_calls) - 1, len(self.create_messages) - 1)
        return self.create_messages[index]

    async def stream_completion(self, messages, tools=None, tool_choice=None):
        self.stream_calls.append(list(messages))
        for index, token in enumerate(self.tokens):
            if self.stream_exception_after is not None and index >= self.stream_exception_after:
                raise RuntimeError("stream broken")
            yield token


def _make_agent(
    qwen: FakeQwenClient,
    session_exists: bool = True,
    max_tool_rounds: int = 5,
):
    registry = FakeRegistry()
    builder = FakeContextBuilder()
    session_store = FakeSessionStore(exists=session_exists)
    memory_store = FakeMemoryStore()
    trace_logger = FakeTraceLogger([])
    agent = ReactAgent(
        qwen,
        registry,
        builder,
        session_store,
        memory_store,
        trace_logger,
        max_tool_rounds=max_tool_rounds,
    )
    return agent, registry, builder, session_store, memory_store, trace_logger


def _tool_call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def test_fake_qwen_client_uses_async_contract_like_real_client():
    assert inspect.iscoroutinefunction(FakeQwenClient.create_completion)
    assert inspect.isasyncgenfunction(FakeQwenClient.stream_completion)


def _assert_trace_metadata(trace_logger: FakeTraceLogger, user_id: str, session_id: str) -> None:
    trace_ids = {trace_id for trace_id, _, _ in trace_logger.events}
    assert len(trace_ids) == 1
    trace_id = next(iter(trace_ids))
    assert trace_id != session_id
    UUID(trace_id)
    assert all(data["user_id"] == user_id for _, _, data in trace_logger.events)
    assert all(data["session_id"] == session_id for _, _, data in trace_logger.events)
    assert all(data["trace_id"] == trace_id for _, _, data in trace_logger.events)


@pytest.mark.asyncio
async def test_react_agent_executes_calculator_tool_and_saves_streamed_answer():
    qwen = FakeQwenClient(
        create_messages=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call-1", "calculator", "{\"expression\":\"2+2\"}")],
            },
            {"role": "assistant", "content": "可以回答了"},
        ],
        tokens=["答案是", "4"],
    )
    agent, registry, builder, session_store, memory_store, trace_logger = _make_agent(qwen)

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
    assert set(tool_messages[0]) == {"role", "tool_call_id", "content"}
    assert json.loads(tool_messages[0]["content"])["data"] == {"result": 4}
    assert tool_messages[0]["tool_call_id"] == "call-1"
    assert session_store.added[-1] == ("alice", "s1", "assistant", "答案是4")
    assert memory_store.added[-1][2] == "答案是4"
    assert events[-1].data["memory_saved"] is True
    _assert_trace_metadata(trace_logger, "alice", "s1")


@pytest.mark.asyncio
async def test_react_agent_supports_multiple_tool_rounds_before_final_stream():
    qwen = FakeQwenClient(
        create_messages=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call-1", "calculator", "{\"expression\":\"2+2\"}")],
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call-2", "search", "{\"query\":\"北京天气\"}")],
            },
            {"role": "assistant", "content": "工具足够了"},
        ],
        tokens=["最终", "回答"],
    )
    agent, registry, _, _, _, _ = _make_agent(qwen)

    events = [event async for event in agent.stream_chat("alice", "s1", "先算再查")]

    assert registry.invocations == [
        ("calculator", {"expression": "2+2"}),
        ("search", {"query": "北京天气"}),
    ]
    assert [event.type for event in events].count("tool_call") == 2
    assert len(qwen.create_calls) == 3
    tool_messages = [message for message in qwen.stream_calls[0] if message["role"] == "tool"]
    assert [message["tool_call_id"] for message in tool_messages] == ["call-1", "call-2"]
    assert all(set(message) == {"role", "tool_call_id", "content"} for message in tool_messages)


@pytest.mark.asyncio
async def test_react_agent_streams_final_answer_when_model_has_no_tool_call():
    qwen = FakeQwenClient(
        create_messages=[{"role": "assistant", "content": "无需工具"}],
        tokens=["直接", "回答"],
    )
    agent, registry, _, session_store, _, _ = _make_agent(qwen)

    events = [event async for event in agent.stream_chat("alice", "s1", "你好")]

    assert [event.type for event in events] == ["message_start", "token", "token", "message_end"]
    assert registry.invocations == []
    assert qwen.create_calls[0]["tools"] == [
        {"type": "function", "function": {"name": "calculator"}},
        {"type": "function", "function": {"name": "search"}},
    ]
    assert session_store.added[-1] == ("alice", "s1", "assistant", "直接回答")


@pytest.mark.asyncio
async def test_react_agent_yields_error_when_qwen_create_fails_after_message_start():
    qwen = FakeQwenClient(create_exception=RuntimeError("qwen unavailable"))
    agent, _, _, session_store, memory_store, _ = _make_agent(qwen)

    events = [event async for event in agent.stream_chat("alice", "s1", "你好")]

    assert [event.type for event in events] == ["message_start", "error"]
    assert "模型调用失败" in events[-1].data["message"]
    assert [record[2] for record in session_store.added] == ["user"]
    assert memory_store.added == []


@pytest.mark.asyncio
async def test_react_agent_yields_error_when_qwen_stream_fails_after_tokens():
    qwen = FakeQwenClient(
        create_messages=[{"role": "assistant", "content": "无需工具"}],
        tokens=["半句", "不会到达"],
        stream_exception_after=1,
    )
    agent, _, _, session_store, memory_store, _ = _make_agent(qwen)

    events = [event async for event in agent.stream_chat("alice", "s1", "你好")]

    assert [event.type for event in events] == ["message_start", "token", "error"]
    assert events[1].data["content"] == "半句"
    assert "模型流式输出失败" in events[-1].data["message"]
    assert [record[2] for record in session_store.added] == ["user"]
    assert memory_store.added == []


@pytest.mark.asyncio
async def test_react_agent_yields_error_when_session_does_not_exist():
    qwen = FakeQwenClient(tokens=["不会输出"])
    agent, _, _, session_store, memory_store, trace_logger = _make_agent(qwen, session_exists=False)

    events = [event async for event in agent.stream_chat("alice", "missing", "你好")]

    assert len(events) == 1
    assert events[0].type == "error"
    assert "会话不存在" in events[0].data["message"]
    assert session_store.added == []
    assert memory_store.search_calls == []
    _assert_trace_metadata(trace_logger, "alice", "missing")


@pytest.mark.asyncio
async def test_react_agent_returns_tool_result_error_for_invalid_arguments_json():
    qwen = FakeQwenClient(
        create_messages=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [_tool_call("call-bad", "calculator", "{bad json")],
            },
            {"role": "assistant", "content": "参数有误"},
        ],
        tokens=["参数有误"],
    )
    agent, registry, _, _, _, _ = _make_agent(qwen)

    events = [event async for event in agent.stream_chat("alice", "s1", "请计算")]

    tool_result = next(event for event in events if event.type == "tool_result")
    tool_messages = [message for message in qwen.stream_calls[0] if message["role"] == "tool"]
    tool_payload = json.loads(tool_messages[0]["content"])
    assert registry.invocations == []
    assert tool_result.data["result"]["success"] is False
    assert tool_payload["error_code"] == ToolErrorCode.INVALID_ARGUMENTS.value
    assert "JSON" in tool_payload["message"]


@pytest.mark.asyncio
async def test_react_agent_yields_error_for_empty_assistant_message_without_persistence():
    qwen = FakeQwenClient(
        create_messages=[{"role": "assistant", "content": "无需工具"}],
        tokens=["   "],
    )
    agent, _, _, session_store, memory_store, _ = _make_agent(qwen)

    events = [event async for event in agent.stream_chat("alice", "s1", "空回复")]

    assert [event.type for event in events] == ["message_start", "token", "error"]
    assert "模型返回空回复" in events[-1].data["message"]
    assert [record[2] for record in session_store.added] == ["user"]
    assert memory_store.added == []


@pytest.mark.asyncio
async def test_react_agent_yields_error_when_assistant_message_save_returns_none():
    qwen = FakeQwenClient(
        create_messages=[{"role": "assistant", "content": "无需工具"}],
        tokens=["有效回复"],
    )
    agent, _, _, session_store, memory_store, _ = _make_agent(qwen)
    session_store.fail_assistant_save = True

    events = [event async for event in agent.stream_chat("alice", "s1", "你好")]

    assert [event.type for event in events] == ["message_start", "token", "error"]
    assert "保存助手消息失败" in events[-1].data["message"]
    assert memory_store.added == []


@pytest.mark.asyncio
async def test_react_agent_keeps_message_end_when_memory_save_fails():
    qwen = FakeQwenClient(
        create_messages=[{"role": "assistant", "content": "无需工具"}],
        tokens=["有效回复"],
    )
    agent, _, _, session_store, memory_store, _ = _make_agent(qwen)
    memory_store.fail_add = True

    events = [event async for event in agent.stream_chat("alice", "s1", "你好")]

    assert [event.type for event in events] == ["message_start", "token", "message_end"]
    assert session_store.added[-1] == ("alice", "s1", "assistant", "有效回复")
    assert events[-1].data["memory_saved"] is False
    assert "记忆保存失败" in events[-1].data["warning"]


@pytest.mark.asyncio
async def test_react_agent_keeps_streaming_when_trace_logging_fails():
    qwen = FakeQwenClient(
        create_messages=[{"role": "assistant", "content": "无需工具"}],
        tokens=["仍然", "回复"],
    )
    agent, _, _, _, _, _ = _make_agent(qwen)
    agent.trace_logger = FailingTraceLogger()

    events = [event async for event in agent.stream_chat("alice", "s1", "你好")]

    assert [event.type for event in events] == ["message_start", "token", "token", "message_end"]
    assert events[-1].data["content"] == "仍然回复"


class FailingTraceLogger:
    def log_event(self, trace_id, event) -> None:
        raise RuntimeError("trace disk full")

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
import json
from typing import Any

from src.context.builder import ContextPacket
from src.core.agent import AgentEvent
from src.tools.errors import ToolErrorCode
from src.tools.response import ToolResponse


class ReactAgent:
    def __init__(
        self,
        qwen_client: Any,
        registry: Any,
        context_builder: Any,
        session_store: Any,
        memory_store: Any,
        trace_logger: Any,
    ):
        self.qwen_client = qwen_client
        self.registry = registry
        self.context_builder = context_builder
        self.session_store = session_store
        self.memory_store = memory_store
        self.trace_logger = trace_logger

    async def stream_chat(
        self,
        user_id: str,
        session_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        session = await self.session_store.get_session(user_id, session_id)
        if session is None:
            yield self._event(session_id, "error", {"message": f"会话不存在：{session_id}"})
            return

        user_record = await self.session_store.add_message(user_id, session_id, "user", message)
        if user_record is None:
            yield self._event(session_id, "error", {"message": "保存用户消息失败，会话可能已经不存在。"})
            return

        history = await self.session_store.get_recent_messages(user_id, session_id, limit=10)
        memory_records = await self.memory_store.search(user_id, session_id, message, limit=5)
        memory_packets = [self._memory_to_packet(record) for record in memory_records]
        built_context = self.context_builder.build(
            task=message,
            system_policy="你是一个中文智能助手，必要时可以调用工具并基于工具结果回答。",
            history=history,
            memory_packets=memory_packets,
            custom_packets=None,
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": built_context.text},
            {"role": "user", "content": message},
        ]

        yield self._event(
            session_id,
            "message_start",
            {
                "user_id": user_id,
                "session_id": session_id,
                "compressed_context": built_context.compressed,
            },
        )

        assistant_probe = self.qwen_client.create_completion(
            messages,
            tools=self.registry.to_qwen_tools(),
        )
        tool_calls = assistant_probe.get("tool_calls") or []
        if tool_calls:
            messages.append(assistant_probe)

        for tool_call in tool_calls:
            async for event in self._handle_tool_call(session_id, messages, tool_call):
                yield event

        answer_parts: list[str] = []
        for token in self.qwen_client.stream_completion(messages):
            answer_parts.append(token)
            yield self._event(session_id, "token", {"content": token})

        assistant_message = "".join(answer_parts)
        await self.session_store.add_message(user_id, session_id, "assistant", assistant_message)
        await self.memory_store.add(
            user_id,
            session_id,
            assistant_message,
            {
                "source": "assistant",
                "user_message": message,
                **(metadata or {}),
            },
        )

        yield self._event(
            session_id,
            "message_end",
            {"content": assistant_message, "selected_context": len(built_context.selected_packets)},
        )

    async def _handle_tool_call(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        tool_call: Mapping[str, Any],
    ) -> AsyncIterator[AgentEvent]:
        tool_call_id = str(tool_call.get("id") or "")
        function = tool_call.get("function") if isinstance(tool_call, Mapping) else None
        function = function if isinstance(function, Mapping) else {}
        tool_name = str(function.get("name") or "")
        raw_arguments = function.get("arguments", "{}")

        yield self._event(
            session_id,
            "tool_call",
            {"id": tool_call_id, "name": tool_name, "arguments": raw_arguments},
        )

        parsed_arguments, parse_error = self._parse_arguments(raw_arguments)
        if parse_error is not None:
            tool_response = ToolResponse(
                success=False,
                data=None,
                error_code=ToolErrorCode.INVALID_ARGUMENTS,
                message=parse_error,
                elapsed_ms=0.0,
            )
        else:
            tool_response = await self.registry.invoke(tool_name, parsed_arguments)

        result = tool_response.to_dict()
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            }
        )
        yield self._event(
            session_id,
            "tool_result",
            {"id": tool_call_id, "name": tool_name, "result": result},
        )

    @staticmethod
    def _memory_to_packet(record: Any) -> ContextPacket:
        metadata = dict(getattr(record, "metadata", {}) or {})
        memory_id = getattr(record, "id", None)
        if memory_id is not None:
            metadata.setdefault("memory_id", memory_id)

        return ContextPacket(
            content=getattr(record, "content", ""),
            timestamp=getattr(record, "created_at", ""),
            relevance_score=float(getattr(record, "score", 0.0)),
            metadata=metadata,
        )

    @staticmethod
    def _parse_arguments(raw_arguments: Any) -> tuple[dict[str, Any], str | None]:
        if raw_arguments in (None, ""):
            return {}, None
        if isinstance(raw_arguments, Mapping):
            return dict(raw_arguments), None
        if not isinstance(raw_arguments, str):
            return {}, "工具参数必须是 JSON 对象字符串。"

        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}, "工具参数不是有效 JSON。"

        if not isinstance(parsed, dict):
            return {}, "工具参数 JSON 必须是对象。"

        return parsed, None

    def _event(self, trace_id: str, event_type: str, data: dict[str, Any]) -> AgentEvent:
        event = AgentEvent(event_type, data)
        self.trace_logger.log_event(trace_id, event)
        return event

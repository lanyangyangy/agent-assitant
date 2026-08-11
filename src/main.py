from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
import json
from pathlib import Path
import re
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.agents.qwen_client import QwenClient
from src.agents.react_agent import ReactAgent
from src.api.routes import router as api_router
from src.context.builder import ContextBuilder
from src.core.config import Settings, get_settings
from src.core.memory import SQLiteMemoryStore
from src.core.session_store import SQLiteSessionStore
from src.core.trace_logger import TraceLogger
from src.tools.base import BaseTool, ToolParameter
from src.tools.calculator import CalculatorTool
from src.tools.errors import ToolInputError
from src.tools.registry import ToolRegistry
from src.tools.search import TavilySearchTool
from src.tools.weather import OpenMeteoWeatherTool


def create_app(
    data_dir: Path | None = None,
    settings: Settings | None = None,
    qwen_client: Any | None = None,
) -> FastAPI:
    effective_settings = settings or get_settings()
    if data_dir is not None:
        effective_settings = effective_settings.model_copy(update={"app_data_dir": Path(data_dir)})

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        data_root = effective_settings.data_dir
        data_root.mkdir(parents=True, exist_ok=True)

        session_store = SQLiteSessionStore(effective_settings.sqlite_path)
        memory_store = SQLiteMemoryStore(effective_settings.sqlite_path)
        await session_store.initialize()
        await memory_store.initialize()

        registry = _build_tool_registry(effective_settings)
        managed_qwen_client, owns_qwen_client, model_configured = _build_qwen_client(
            effective_settings,
            qwen_client,
        )
        trace_logger = TraceLogger(data_root / "traces")
        agent = ReactAgent(
            qwen_client=managed_qwen_client,
            registry=registry,
            context_builder=ContextBuilder(),
            session_store=session_store,
            memory_store=memory_store,
            trace_logger=trace_logger,
        )

        app.state.settings = effective_settings
        app.state.session_store = session_store
        app.state.memory_store = memory_store
        app.state.tool_registry = registry
        app.state.qwen_client = managed_qwen_client
        app.state.agent = agent
        app.state.model_configured = model_configured
        app.state.search_available = bool(effective_settings.tavily_api_key)

        try:
            yield
        finally:
            await _close_registry_tools(registry)
            if owns_qwen_client and hasattr(managed_qwen_client, "aclose"):
                await managed_qwen_client.aclose()

    app = FastAPI(title=effective_settings.app_name, lifespan=lifespan)
    app.add_exception_handler(RequestValidationError, _request_validation_error_handler)
    app.include_router(api_router)
    return app


def _build_tool_registry(settings: Settings) -> ToolRegistry:
    registry = ToolRegistry(
        timeout_seconds=settings.tool_timeout_seconds,
        failure_threshold=settings.circuit_breaker_failure_threshold,
    )
    registry.register(CalculatorTool())
    registry.register(_build_search_tool(settings))
    registry.register(OpenMeteoWeatherTool())
    return registry


def _build_search_tool(settings: Settings) -> BaseTool:
    if settings.tavily_api_key:
        return TavilySearchTool(settings.tavily_api_key)
    return _UnavailableSearchTool()


def _build_qwen_client(
    settings: Settings,
    injected_client: Any | None,
) -> tuple[Any, bool, bool]:
    if injected_client is not None:
        return injected_client, False, True

    if settings.dashscope_api_key:
        return (
            QwenClient(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
                model=settings.llm_model_id,
            ),
            True,
            True,
        )

    return _LocalEchoClient(), False, False


async def _close_registry_tools(registry: ToolRegistry) -> None:
    for tool in registry.list_tools():
        close = getattr(tool, "aclose", None)
        if close is not None:
            try:
                await close()
            except Exception:
                continue


async def _request_validation_error_handler(
    request: Any,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "请求参数校验失败。",
            "errors": [_validation_error_to_dict(error) for error in exc.errors()],
        },
    )


def _validation_error_to_dict(error: dict[str, Any]) -> dict[str, Any]:
    return {
        "loc": list(error.get("loc", [])),
        "type": str(error.get("type", "validation_error")),
        "message": "字段校验失败。",
    }


class _UnavailableSearchTool(BaseTool):
    name = "search"
    description = "使用 Tavily 搜索互联网并返回摘要答案和结果列表。"
    parameters = [
        ToolParameter("query", "string", "搜索关键词。"),
        ToolParameter("max_results", "integer", "最多返回的搜索结果数量。", required=False, default=5),
    ]

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raise ToolInputError("搜索工具暂不可用：未配置 TAVILY_API_KEY。")


class _LocalEchoClient:
    async def create_completion(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        expression = self._calculator_expression(messages)
        if expression is not None:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "local-calculator-1",
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": json.dumps(
                                {"expression": expression},
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    }
                ],
            }

        return {"role": "assistant", "content": "本地回显无需继续调用工具。"}

    async def stream_completion(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        answer = self._answer_from_tool_result(messages)
        if answer is None:
            answer = f"本地回显：{self._last_user_message(messages)}"

        for token in self._split_tokens(answer):
            yield token

    async def aclose(self) -> None:
        return None

    @classmethod
    def _calculator_expression(cls, messages: Sequence[dict[str, Any]]) -> str | None:
        if any(message.get("role") == "tool" for message in messages):
            return None
        user_message = cls._last_user_message(messages)
        has_calculation_keyword = any(keyword in user_message for keyword in _CALCULATION_KEYWORDS)
        return cls._extract_expression(
            user_message,
            require_operator=not has_calculation_keyword,
        )

    @staticmethod
    def _last_user_message(messages: Sequence[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                content = message.get("content")
                return content if isinstance(content, str) else ""
        return ""

    @classmethod
    def _extract_expression(cls, message: str, require_operator: bool = False) -> str | None:
        candidates: list[str] = []
        for match in _MATH_FRAGMENT_RE.finditer(message):
            fragment = cls._best_balanced_fragment(match.group(0))
            if fragment is None:
                continue
            if require_operator and not cls._has_operator(fragment):
                continue
            candidates.append(fragment)

        if not candidates:
            return None
        return max(candidates, key=lambda value: (len(value), cls._operator_count(value)))

    @classmethod
    def _best_balanced_fragment(cls, raw_fragment: str) -> str | None:
        fragment = raw_fragment.strip()
        best = None
        for start in range(len(fragment)):
            for end in range(len(fragment), start, -1):
                candidate = fragment[start:end].strip()
                if len(best or "") >= len(candidate):
                    break
                if cls._is_complete_expression(candidate):
                    best = candidate
                    break
        return best

    @classmethod
    def _is_complete_expression(cls, value: str) -> bool:
        if not value or not any(char.isdigit() for char in value):
            return False
        if not cls._parentheses_balanced(value):
            return False
        return value[0] not in "*/%)" and value[-1] not in "+-*/%("

    @staticmethod
    def _parentheses_balanced(value: str) -> bool:
        depth = 0
        for char in value:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth < 0:
                    return False
        return depth == 0

    @staticmethod
    def _has_operator(value: str) -> bool:
        return any(operator in value for operator in ("+", "-", "*", "/", "%"))

    @staticmethod
    def _operator_count(value: str) -> int:
        return sum(1 for char in value if char in "+-*/%")

    @staticmethod
    def _answer_from_tool_result(messages: Sequence[dict[str, Any]]) -> str | None:
        for message in reversed(messages):
            if message.get("role") != "tool":
                continue
            content = message.get("content")
            if not isinstance(content, str):
                continue
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                continue

            result = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(result, dict) and "result" in result:
                return f"计算结果是 {result['result']}。"
        return None

    @staticmethod
    def _split_tokens(answer: str) -> list[str]:
        if len(answer) <= 8:
            return [answer]
        return [answer[index : index + 8] for index in range(0, len(answer), 8)]


_CALCULATION_KEYWORDS = ("计算", "算")
_MATH_FRAGMENT_RE = re.compile(r"[\d\s().+\-*/%]+")


app = create_app()

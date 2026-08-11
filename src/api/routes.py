from __future__ import annotations

import json
from collections.abc import AsyncIterator

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from src.api.dependencies import (
    get_agent,
    get_model_configured,
    get_search_available,
    get_settings,
    get_session_store,
    get_tool_registry,
    require_user_id,
)
from src.api.schemas import (
    ChatStreamRequest,
    HealthResponse,
    SessionListResponse,
    SessionResponse,
    ToolParameterResponse,
    ToolResponseSchema,
)
from src.core.config import Settings
from src.core.session_store import SQLiteSessionStore
from src.core.streaming import format_sse
from src.tools.registry import ToolRegistry


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: Settings = Depends(get_settings),
    model_configured: bool = Depends(get_model_configured),
    search_available: bool = Depends(get_search_available),
) -> HealthResponse:
    sqlite_available = await _check_sqlite(settings.sqlite_path)
    status_text = "ok" if sqlite_available else "degraded"
    message = "服务正常，SQLite 可用。" if sqlite_available else "服务可用，但 SQLite 检查失败。"
    return HealthResponse(
        status=status_text,
        message=message,
        model_configured=model_configured,
        sqlite_available=sqlite_available,
        search_available=search_available,
    )


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    user_id: str = Depends(require_user_id),
    session_store: SQLiteSessionStore = Depends(get_session_store),
) -> SessionResponse:
    session = await session_store.create_session(user_id)
    return SessionResponse.from_record(session)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user_id: str = Depends(require_user_id),
    session_store: SQLiteSessionStore = Depends(get_session_store),
) -> SessionListResponse:
    sessions = await session_store.list_sessions(user_id)
    return SessionListResponse(
        sessions=[SessionResponse.from_record(session) for session in sessions],
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    user_id: str = Depends(require_user_id),
    session_store: SQLiteSessionStore = Depends(get_session_store),
) -> Response:
    deleted = await session_store.delete_session(user_id, session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权访问。",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tools", response_model=list[ToolResponseSchema])
async def list_tools(registry: ToolRegistry = Depends(get_tool_registry)) -> list[ToolResponseSchema]:
    return [_tool_to_schema(tool) for tool in registry.list_tools()]


@router.post("/tools/{tool_name}/invoke")
async def invoke_tool(
    tool_name: str,
    request: Request,
    registry: ToolRegistry = Depends(get_tool_registry),
) -> dict:
    try:
        arguments = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="工具参数必须是 JSON 对象。",
        ) from exc

    if not isinstance(arguments, dict):
        raise HTTPException(
            status_code=422,
            detail="工具参数必须是 JSON 对象。",
        )

    tool_response = await registry.invoke(tool_name, arguments)
    return tool_response.to_dict()


@router.post("/chat/stream")
async def chat_stream(
    body: ChatStreamRequest,
    user_id: str = Depends(require_user_id),
    agent=Depends(get_agent),
) -> StreamingResponse:
    async def _events() -> AsyncIterator[str]:
        async for event in agent.stream_chat(
            user_id=user_id,
            session_id=body.session_id,
            message=body.message,
            metadata=body.metadata,
        ):
            yield format_sse(event)

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _check_sqlite(db_path) -> bool:
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("SELECT 1")
        return True
    except Exception:
        return False


def _tool_to_schema(tool) -> ToolResponseSchema:
    return ToolResponseSchema(
        name=tool.name,
        description=tool.description,
        parameters=[
            ToolParameterResponse(
                name=parameter.name,
                type=parameter.type,
                description=parameter.description,
                required=parameter.required,
                default=parameter.default,
            )
            for parameter in tool.parameters
        ],
    )

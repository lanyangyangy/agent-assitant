from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException, Request, status

from src.agents.react_agent import ReactAgent
from src.core.config import Settings
from src.core.memory import SQLiteMemoryStore
from src.core.session_store import SQLiteSessionStore
from src.tools.registry import ToolRegistry


def require_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    if x_user_id is None or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 X-User-Id 请求头。",
        )
    return x_user_id.strip()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_store(request: Request) -> SQLiteSessionStore:
    return request.app.state.session_store


def get_memory_store(request: Request) -> SQLiteMemoryStore:
    return request.app.state.memory_store


def get_tool_registry(request: Request) -> ToolRegistry:
    return request.app.state.tool_registry


def get_agent(request: Request) -> ReactAgent:
    return request.app.state.agent


def get_model_configured(request: Request) -> bool:
    return bool(getattr(request.app.state, "model_configured", False))


def get_search_available(request: Request) -> bool:
    return bool(getattr(request.app.state, "search_available", False))


def get_qwen_client(request: Request) -> Any:
    return request.app.state.qwen_client

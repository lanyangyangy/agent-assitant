from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.session_store import SessionRecord


class HealthResponse(BaseModel):
    status: str
    message: str
    model_configured: bool
    sqlite_available: bool
    search_available: bool


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    created_at: str

    @classmethod
    def from_record(cls, record: SessionRecord) -> SessionResponse:
        return cls(
            session_id=record.session_id,
            user_id=record.user_id,
            created_at=record.created_at,
        )


class ToolParameterResponse(BaseModel):
    name: str
    type: str
    description: str
    required: bool
    default: Any = None


class ToolResponseSchema(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameterResponse]


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    metadata: dict[str, Any] | None = None

    @field_validator("session_id", "message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("不能为空。")
        return value.strip()

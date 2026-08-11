from __future__ import annotations

from enum import Enum


class ToolErrorCode(str, Enum):
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class ToolInputError(ValueError):
    """工具入参或用户输入无效，registry 应返回 INVALID_ARGUMENTS。"""

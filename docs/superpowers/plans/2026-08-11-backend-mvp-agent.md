# Backend MVP Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-only FastAPI MVP where Qwen Plus can recognize tool needs, call calculator/search/weather tools, integrate the tool result, and stream the final answer through SSE with user/session isolation.

**Architecture:** One FastAPI service with internal modules for API routes, Qwen Agent orchestration, tools, context, SQLite persistence, streaming, and trace logging. Each module has tests before integration, then the combined chat path is debugged through mocked API tests and real external smoke tests.

**Tech Stack:** Python 3.12, uv, FastAPI, Uvicorn, Pydantic Settings, httpx, aiosqlite, SQLite FTS5, pytest, pytest-asyncio, DashScope OpenAI-compatible Chat API, Tavily Search API, Open-Meteo Geocoding and Forecast APIs.

---

## External API References

- DashScope OpenAI-compatible Chat API: https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
- Tavily Search API: https://docs.tavily.com/documentation/api-reference/endpoint/search
- Open-Meteo Geocoding API: https://open-meteo.com/en/docs/geocoding-api
- Open-Meteo Forecast API: https://open-meteo.com/en/docs

## Multi-Agent Work Split

- Agent A: Tasks 1-3, project scaffold, settings, SQLite sessions/messages, memory.
- Agent B: Tasks 4-6, tool protocol, registry, circuit breaker, calculator, Tavily search, Open-Meteo weather.
- Agent C: Tasks 7-9, context pipeline, Qwen client, compression, Agent tool loop.
- Agent D: Tasks 10-12, FastAPI routes, SSE tests, integration smoke tests, final combined debug, issue log, git hygiene.

Tasks 2, 3, 4, 5, 6, and 7 can proceed after Task 1. Tasks 8 and 9 depend on Tasks 4-7. Task 10 depends on Tasks 2, 4, and 9. Task 11 depends on all runtime modules. Task 12 is the final verification pass.

## File Structure

- Create: `pyproject.toml` for uv-managed package metadata, dependencies, pytest markers, and ruff settings.
- Create: `.gitignore` to exclude `.env`, SQLite files, caches, logs, and local data.
- Create: `README.md` with startup and test commands.
- Create: `docs/issue-resolution-log.md` with the required fix-record format.
- Create: `src/__init__.py` to make `src` importable.
- Create: `src/main.py` to expose `app = create_app()`.
- Create: `src/api/__init__.py`, `src/api/dependencies.py`, `src/api/routes.py`, `src/api/schemas.py`.
- Create: `src/agents/__init__.py`, `src/agents/qwen_client.py`, `src/agents/react_agent.py`.
- Create: `src/core/__init__.py`, `src/core/agent.py`, `src/core/config.py`, `src/core/exceptions.py`, `src/core/memory.py`, `src/core/session_store.py`, `src/core/streaming.py`, `src/core/trace_logger.py`.
- Create: `src/context/__init__.py`, `src/context/builder.py`, `src/context/compress.py`, `src/context/history.py`, `src/context/token_counter.py`.
- Create: `src/tools/__init__.py`, `src/tools/base.py`, `src/tools/calculator.py`, `src/tools/circuit_breaker.py`, `src/tools/errors.py`, `src/tools/registry.py`, `src/tools/response.py`, `src/tools/search.py`, `src/tools/weather.py`.
- Create: `tests/conftest.py`.
- Create: `tests/unit/core/test_config.py`, `tests/unit/core/test_session_store.py`, `tests/unit/core/test_memory.py`, `tests/unit/core/test_streaming_trace.py`.
- Create: `tests/unit/tools/test_registry_and_circuit_breaker.py`, `tests/unit/tools/test_calculator.py`, `tests/unit/tools/test_search_weather.py`.
- Create: `tests/unit/context/test_context_builder.py`.
- Create: `tests/unit/agents/test_qwen_client.py`, `tests/unit/agents/test_react_agent.py`.
- Create: `tests/api/test_health_sessions_tools.py`, `tests/api/test_chat_stream.py`.
- Create: `tests/integration/test_external_smoke.py`.

---

### Task 1: Project Scaffold And Settings

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `docs/issue-resolution-log.md`
- Create: `src/__init__.py`
- Create: `src/core/__init__.py`
- Create: `src/core/config.py`
- Test: `tests/unit/core/test_config.py`

- [ ] **Step 1: Write the failing settings test**

```python
# tests/unit/core/test_config.py
from pathlib import Path

from src.core.config import Settings


def test_settings_loads_env_values(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dash-key")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://example.test/compatible-mode/v1")
    monkeypatch.setenv("LLM_MODEL_ID", "qwen-plus")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    settings = Settings(_env_file=None)

    assert settings.dashscope_api_key == "dash-key"
    assert settings.dashscope_base_url == "https://example.test/compatible-mode/v1"
    assert settings.llm_model_id == "qwen-plus"
    assert settings.tavily_api_key == "tavily-key"
    assert settings.data_dir == tmp_path
    assert settings.sqlite_path == tmp_path / "agent.sqlite3"
    assert settings.tool_timeout_seconds == 180
    assert settings.circuit_breaker_failure_threshold == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/core/test_config.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.config'`.

- [ ] **Step 3: Create uv project metadata and package scaffold**

```toml
# pyproject.toml
[project]
name = "backend-mvp-agent"
version = "0.1.0"
description = "FastAPI backend MVP for a Qwen Plus streaming tool-calling Agent."
requires-python = ">=3.12"
dependencies = [
    "aiosqlite>=0.20.0",
    "fastapi>=0.115.0",
    "httpx>=0.27.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "uvicorn[standard]>=0.30.0",
]

[dependency-groups]
dev = [
    "asgi-lifespan>=2.1.0",
    "pytest>=8.3.0",
    "pytest-asyncio>=0.23.0",
    "python-dotenv>=1.0.1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "integration: real external API smoke tests",
]

[tool.ruff]
line-length = 100
target-version = "py312"
```

```gitignore
# .gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
*.sqlite3
*.db
data/
logs/
traces/
```

```markdown
<!-- docs/issue-resolution-log.md -->
# Issue Resolution Log

Every code change made to fix a failed test, runtime exception, or integration error gets an entry here before the fix commit.

## Entry Format

- Date:
- Symptom:
- Root Cause:
- Changed Files:
- Verification Command:
- Result:
```

```python
# src/__init__.py
```

```python
# src/core/__init__.py
```

- [ ] **Step 4: Implement settings**

```python
# src/core/config.py
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Backend MVP Agent"
    app_data_dir: Path = Field(default=Path("data"), alias="APP_DATA_DIR")
    dashscope_api_key: str | None = Field(default=None, alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="DASHSCOPE_BASE_URL",
    )
    llm_model_id: str = Field(default="qwen-plus", alias="LLM_MODEL_ID")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    tool_timeout_seconds: float = Field(default=180.0, alias="TOOL_TIMEOUT_SECONDS")
    circuit_breaker_failure_threshold: int = Field(
        default=3,
        alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    )

    @property
    def data_dir(self) -> Path:
        return self.app_data_dir

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "agent.sqlite3"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Run the settings test**

Run: `uv run pytest tests/unit/core/test_config.py -v`

Expected: PASS.

- [ ] **Step 6: Commit scaffold**

```bash
git add pyproject.toml .gitignore README.md docs/issue-resolution-log.md src tests/unit/core/test_config.py
git commit -m "chore: scaffold backend mvp project"
```

---

### Task 2: SQLite Session And Message Store

**Files:**
- Create: `src/core/session_store.py`
- Test: `tests/unit/core/test_session_store.py`

- [ ] **Step 1: Write failing session isolation tests**

```python
# tests/unit/core/test_session_store.py
from pathlib import Path

import pytest

from src.core.session_store import SQLiteSessionStore


@pytest.mark.asyncio
async def test_sessions_are_scoped_by_user(tmp_path: Path):
    store = SQLiteSessionStore(tmp_path / "agent.sqlite3")
    await store.initialize()

    alice_session = await store.create_session("alice")
    bob_session = await store.create_session("bob")

    assert await store.get_session("alice", alice_session.session_id) == alice_session
    assert await store.get_session("bob", alice_session.session_id) is None
    assert await store.list_sessions("alice") == [alice_session]
    assert await store.list_sessions("bob") == [bob_session]


@pytest.mark.asyncio
async def test_messages_are_scoped_and_recent_history_is_limited(tmp_path: Path):
    store = SQLiteSessionStore(tmp_path / "agent.sqlite3")
    await store.initialize()
    session = await store.create_session("alice")

    for index in range(12):
        role = "user" if index % 2 == 0 else "assistant"
        await store.add_message("alice", session.session_id, role, f"message-{index}")

    await store.add_message("bob", session.session_id, "user", "not visible")

    recent = await store.get_recent_messages("alice", session.session_id, limit=10)

    assert [message.content for message in recent] == [f"message-{index}" for index in range(2, 12)]
    assert await store.get_recent_messages("bob", session.session_id, limit=10) == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/core/test_session_store.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.session_store'`.

- [ ] **Step 3: Implement SQLite session store**

```python
# src/core/session_store.py
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import aiosqlite


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    user_id: str
    created_at: str


@dataclass(frozen=True)
class MessageRecord:
    id: int
    user_id: str
    session_id: str
    role: str
    content: str
    created_at: str


class SQLiteSessionStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_scope ON messages(user_id, session_id, id)"
            )
            await db.commit()

    async def create_session(self, user_id: str) -> SessionRecord:
        record = SessionRecord(session_id=str(uuid4()), user_id=user_id, created_at=utc_now_iso())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions(session_id, user_id, created_at) VALUES (?, ?, ?)",
                (record.session_id, record.user_id, record.created_at),
            )
            await db.commit()
        return record

    async def get_session(self, user_id: str, session_id: str) -> SessionRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            row = await (
                await db.execute(
                    "SELECT session_id, user_id, created_at FROM sessions WHERE user_id = ? AND session_id = ?",
                    (user_id, session_id),
                )
            ).fetchone()
        return SessionRecord(*row) if row else None

    async def list_sessions(self, user_id: str) -> list[SessionRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            rows = await (
                await db.execute(
                    "SELECT session_id, user_id, created_at FROM sessions WHERE user_id = ? ORDER BY created_at",
                    (user_id,),
                )
            ).fetchall()
        return [SessionRecord(*row) for row in rows]

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            )
            await db.execute(
                "DELETE FROM messages WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            )
            await db.commit()
        return cursor.rowcount > 0

    async def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
    ) -> MessageRecord:
        created_at = utc_now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO messages(user_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, session_id, role, content, created_at),
            )
            await db.commit()
            message_id = cursor.lastrowid
        return MessageRecord(message_id, user_id, session_id, role, content, created_at)

    async def get_recent_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10,
    ) -> list[MessageRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            rows = await (
                await db.execute(
                    """
                    SELECT id, user_id, session_id, role, content, created_at
                    FROM messages
                    WHERE user_id = ? AND session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, session_id, limit),
                )
            ).fetchall()
        return [MessageRecord(*row) for row in reversed(rows)]
```

- [ ] **Step 4: Run session tests**

Run: `uv run pytest tests/unit/core/test_session_store.py -v`

Expected: PASS.

- [ ] **Step 5: Commit session store**

```bash
git add src/core/session_store.py tests/unit/core/test_session_store.py
git commit -m "feat: add sqlite session store"
```

---

### Task 3: SQLite Memory With FTS5 BM25

**Files:**
- Create: `src/core/memory.py`
- Test: `tests/unit/core/test_memory.py`

- [ ] **Step 1: Write failing memory tests**

```python
# tests/unit/core/test_memory.py
from pathlib import Path

import pytest

from src.core.memory import SQLiteMemoryStore


@pytest.mark.asyncio
async def test_memory_search_uses_session_scope(tmp_path: Path):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()

    await memory.add("alice", "s1", "Qwen can call calculator tools", {"kind": "fact"})
    await memory.add("alice", "s2", "Weather belongs to another session", {"kind": "fact"})
    await memory.add("bob", "s1", "Bob private calculator memory", {"kind": "fact"})

    hits = await memory.search("alice", "s1", "calculator tools", limit=5)

    assert len(hits) == 1
    assert hits[0].content == "Qwen can call calculator tools"
    assert hits[0].metadata == {"kind": "fact"}
    assert hits[0].score >= 0.0


@pytest.mark.asyncio
async def test_empty_memory_search_returns_empty_list(tmp_path: Path):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()

    assert await memory.search("alice", "missing", "anything") == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/core/test_memory.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.memory'`.

- [ ] **Step 3: Implement FTS-backed memory store**

```python
# src/core/memory.py
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class MemoryRecord:
    id: int
    user_id: str
    session_id: str
    content: str
    metadata: dict[str, Any]
    created_at: str
    score: float


class SQLiteMemoryStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(content, user_id UNINDEXED, session_id UNINDEXED, memory_id UNINDEXED)
                """
            )
            await db.commit()

    async def add(
        self,
        user_id: str,
        session_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        created_at = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO memories(user_id, session_id, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, session_id, content, metadata_json, created_at),
            )
            memory_id = cursor.lastrowid
            await db.execute(
                "INSERT INTO memory_fts(content, user_id, session_id, memory_id) VALUES (?, ?, ?, ?)",
                (content, user_id, session_id, memory_id),
            )
            await db.commit()
        return MemoryRecord(memory_id, user_id, session_id, content, metadata or {}, created_at, 0.0)

    async def search(
        self,
        user_id: str,
        session_id: str,
        query: str,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            rows = await (
                await db.execute(
                    """
                    SELECT m.id, m.user_id, m.session_id, m.content, m.metadata_json, m.created_at,
                           bm25(memory_fts) AS rank
                    FROM memory_fts
                    JOIN memories m ON m.id = memory_fts.memory_id
                    WHERE memory_fts MATCH ?
                      AND memory_fts.user_id = ?
                      AND memory_fts.session_id = ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, user_id, session_id, limit),
                )
            ).fetchall()
        return [
            MemoryRecord(
                id=row[0],
                user_id=row[1],
                session_id=row[2],
                content=row[3],
                metadata=json.loads(row[4]),
                created_at=row[5],
                score=float(abs(row[6])),
            )
            for row in rows
        ]
```

- [ ] **Step 4: Run memory tests**

Run: `uv run pytest tests/unit/core/test_memory.py -v`

Expected: PASS.

- [ ] **Step 5: Commit memory store**

```bash
git add src/core/memory.py tests/unit/core/test_memory.py
git commit -m "feat: add sqlite memory search"
```

---

### Task 4: Tool Protocol, Registry, Response, And Circuit Breaker

**Files:**
- Create: `src/tools/__init__.py`
- Create: `src/tools/base.py`
- Create: `src/tools/circuit_breaker.py`
- Create: `src/tools/errors.py`
- Create: `src/tools/registry.py`
- Create: `src/tools/response.py`
- Test: `tests/unit/tools/test_registry_and_circuit_breaker.py`

- [ ] **Step 1: Write failing registry and circuit breaker tests**

```python
# tests/unit/tools/test_registry_and_circuit_breaker.py
import pytest

from src.tools.base import BaseTool, ToolParameter
from src.tools.circuit_breaker import CircuitBreaker
from src.tools.errors import ToolErrorCode
from src.tools.registry import ToolRegistry


class EchoTool(BaseTool):
    name = "echo"
    description = "Echoes text."
    parameters = [
        ToolParameter(name="text", type="string", description="Text to echo.", required=True)
    ]

    async def run(self, arguments):
        return {"echo": arguments["text"]}


@pytest.mark.asyncio
async def test_registry_exposes_qwen_schema_and_invokes_tool():
    registry = ToolRegistry()
    registry.register(EchoTool())

    schemas = registry.to_qwen_tools()
    result = await registry.invoke("echo", {"text": "hello"})

    assert schemas == [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "Echoes text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to echo."}
                    },
                    "required": ["text"],
                },
            },
        }
    ]
    assert result.success is True
    assert result.data == {"echo": "hello"}


@pytest.mark.asyncio
async def test_registry_returns_error_for_missing_parameter():
    registry = ToolRegistry()
    registry.register(EchoTool())

    result = await registry.invoke("echo", {})

    assert result.success is False
    assert result.error_code == ToolErrorCode.INVALID_ARGUMENTS
    assert "text" in result.message


def test_circuit_breaker_opens_after_three_failures():
    breaker = CircuitBreaker(failure_threshold=3)

    assert breaker.allow_request("search") is True
    breaker.record_failure("search")
    breaker.record_failure("search")
    assert breaker.allow_request("search") is True
    breaker.record_failure("search")
    assert breaker.allow_request("search") is False
    breaker.record_success("search")
    assert breaker.allow_request("search") is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/tools/test_registry_and_circuit_breaker.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.base'`.

- [ ] **Step 3: Implement tool protocol and response**

```python
# src/tools/errors.py
from enum import StrEnum


class ToolErrorCode(StrEnum):
    INVALID_ARGUMENTS = "invalid_arguments"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    CIRCUIT_OPEN = "circuit_open"
    EXECUTION_ERROR = "execution_error"
```

```python
# src/tools/response.py
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from src.tools.errors import ToolErrorCode


@dataclass(frozen=True)
class ToolResponse:
    success: bool
    data: Any | None
    error_code: ToolErrorCode | None
    message: str
    elapsed_ms: float


class ToolTimer:
    def __init__(self):
        self.started_at = perf_counter()

    def elapsed_ms(self) -> float:
        return round((perf_counter() - self.started_at) * 1000, 3)
```

```python
# src/tools/base.py
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any | None = None


class BaseTool:
    name: str
    description: str
    parameters: list[ToolParameter]

    async def run(self, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError
```

- [ ] **Step 4: Implement circuit breaker and registry**

```python
# src/tools/circuit_breaker.py
class CircuitBreaker:
    def __init__(self, failure_threshold: int):
        self.failure_threshold = failure_threshold
        self._failures: dict[str, int] = {}

    def allow_request(self, name: str) -> bool:
        return self._failures.get(name, 0) < self.failure_threshold

    def record_success(self, name: str) -> None:
        self._failures[name] = 0

    def record_failure(self, name: str) -> None:
        self._failures[name] = self._failures.get(name, 0) + 1
```

```python
# src/tools/registry.py
import asyncio
from typing import Any

from src.tools.base import BaseTool
from src.tools.circuit_breaker import CircuitBreaker
from src.tools.errors import ToolErrorCode
from src.tools.response import ToolResponse, ToolTimer


class ToolRegistry:
    def __init__(self, timeout_seconds: float = 180, failure_threshold: int = 3):
        self._tools: dict[str, BaseTool] = {}
        self._timeout_seconds = timeout_seconds
        self._breaker = CircuitBreaker(failure_threshold)

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def to_qwen_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            param.name: {
                                "type": param.type,
                                "description": param.description,
                            }
                            for param in tool.parameters
                        },
                        "required": [param.name for param in tool.parameters if param.required],
                    },
                },
            }
            for tool in self._tools.values()
        ]

    async def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResponse:
        timer = ToolTimer()
        tool = self._tools.get(name)
        if tool is None:
            return ToolResponse(False, None, ToolErrorCode.NOT_FOUND, f"Unknown tool: {name}", timer.elapsed_ms())
        if not self._breaker.allow_request(name):
            return ToolResponse(False, None, ToolErrorCode.CIRCUIT_OPEN, f"Circuit open: {name}", timer.elapsed_ms())
        missing = [param.name for param in tool.parameters if param.required and param.name not in arguments]
        if missing:
            return ToolResponse(False, None, ToolErrorCode.INVALID_ARGUMENTS, f"Missing required parameters: {', '.join(missing)}", timer.elapsed_ms())
        for param in tool.parameters:
            if param.name not in arguments and param.default is not None:
                arguments[param.name] = param.default
        try:
            data = await asyncio.wait_for(tool.run(arguments), timeout=self._timeout_seconds)
        except TimeoutError:
            self._breaker.record_failure(name)
            return ToolResponse(False, None, ToolErrorCode.TIMEOUT, f"Tool timed out: {name}", timer.elapsed_ms())
        except Exception as exc:
            self._breaker.record_failure(name)
            return ToolResponse(False, None, ToolErrorCode.EXECUTION_ERROR, str(exc), timer.elapsed_ms())
        self._breaker.record_success(name)
        return ToolResponse(True, data, None, "ok", timer.elapsed_ms())
```

```python
# src/tools/__init__.py
```

- [ ] **Step 5: Run registry and circuit breaker tests**

Run: `uv run pytest tests/unit/tools/test_registry_and_circuit_breaker.py -v`

Expected: PASS.

- [ ] **Step 6: Commit tool protocol**

```bash
git add src/tools tests/unit/tools/test_registry_and_circuit_breaker.py
git commit -m "feat: add tool registry and circuit breaker"
```

---

### Task 5: Calculator Tool

**Files:**
- Create: `src/tools/calculator.py`
- Test: `tests/unit/tools/test_calculator.py`

- [ ] **Step 1: Write failing calculator tests**

```python
# tests/unit/tools/test_calculator.py
import pytest

from src.tools.calculator import CalculatorTool


@pytest.mark.asyncio
async def test_calculator_evaluates_arithmetic():
    tool = CalculatorTool()

    result = await tool.run({"expression": "2 + 3 * (4 + 5)"})

    assert result == {"expression": "2 + 3 * (4 + 5)", "result": 29}


@pytest.mark.asyncio
async def test_calculator_rejects_code_execution():
    tool = CalculatorTool()

    with pytest.raises(ValueError, match="Unsupported expression"):
        await tool.run({"expression": "__import__('os').system('echo unsafe')"})


@pytest.mark.asyncio
async def test_calculator_rejects_division_by_zero():
    tool = CalculatorTool()

    with pytest.raises(ValueError, match="division by zero"):
        await tool.run({"expression": "1 / 0"})
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/tools/test_calculator.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.calculator'`.

- [ ] **Step 3: Implement restricted AST calculator**

```python
# src/tools/calculator.py
import ast
import operator
from typing import Any

from src.tools.base import BaseTool, ToolParameter


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Evaluate safe arithmetic expressions."
    parameters = [
        ToolParameter(
            name="expression",
            type="string",
            description="Arithmetic expression using numbers and +, -, *, /, //, %, **, and parentheses.",
            required=True,
        )
    ]

    _binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary_ops = {ast.UAdd: operator.pos, ast.USub: operator.neg}

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        expression = str(arguments["expression"])
        try:
            parsed = ast.parse(expression, mode="eval")
            result = self._eval(parsed.body)
        except ZeroDivisionError as exc:
            raise ValueError("division by zero") from exc
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Unsupported expression") from exc
        return {"expression": expression, "result": result}

    def _eval(self, node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._binary_ops:
            return self._binary_ops[type(node.op)](self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._unary_ops:
            return self._unary_ops[type(node.op)](self._eval(node.operand))
        raise ValueError("Unsupported expression")
```

- [ ] **Step 4: Run calculator tests**

Run: `uv run pytest tests/unit/tools/test_calculator.py -v`

Expected: PASS.

- [ ] **Step 5: Commit calculator tool**

```bash
git add src/tools/calculator.py tests/unit/tools/test_calculator.py
git commit -m "feat: add safe calculator tool"
```

---

### Task 6: Tavily Search And Open-Meteo Weather Tools

**Files:**
- Create: `src/tools/search.py`
- Create: `src/tools/weather.py`
- Test: `tests/unit/tools/test_search_weather.py`

- [ ] **Step 1: Write failing HTTP tool tests**

```python
# tests/unit/tools/test_search_weather.py
import json

import httpx
import pytest

from src.tools.search import TavilySearchTool
from src.tools.weather import OpenMeteoWeatherTool


@pytest.mark.asyncio
async def test_tavily_search_posts_query_and_returns_results():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert request.url == "https://api.tavily.com/search"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert payload["query"] == "Qwen tool calling"
        return httpx.Response(
            200,
            json={
                "answer": "summary",
                "results": [{"title": "Doc", "url": "https://example.test", "content": "text"}],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = TavilySearchTool(api_key="test-key", http_client=client)

    result = await tool.run({"query": "Qwen tool calling", "max_results": 1})

    assert result["answer"] == "summary"
    assert result["results"][0]["title"] == "Doc"
    await client.aclose()


@pytest.mark.asyncio
async def test_weather_uses_geocoding_then_forecast():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geocoding-api.open-meteo.com":
            return httpx.Response(
                200,
                json={"results": [{"name": "Beijing", "latitude": 39.9, "longitude": 116.4}]},
            )
        assert request.url.host == "api.open-meteo.com"
        return httpx.Response(
            200,
            json={
                "current": {
                    "temperature_2m": 21.5,
                    "relative_humidity_2m": 40,
                    "weather_code": 1,
                    "wind_speed_10m": 3.2,
                },
                "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = OpenMeteoWeatherTool(http_client=client)

    result = await tool.run({"location": "Beijing", "unit": "celsius"})

    assert result["location"]["name"] == "Beijing"
    assert result["current"]["temperature"] == 21.5
    assert result["current"]["temperature_unit"] == "°C"
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/tools/test_search_weather.py -v`

Expected: FAIL with `ModuleNotFoundError` for `src.tools.search`.

- [ ] **Step 3: Implement Tavily search tool**

```python
# src/tools/search.py
from typing import Any

import httpx

from src.tools.base import BaseTool, ToolParameter


class TavilySearchTool(BaseTool):
    name = "search"
    description = "Search the web for current information using Tavily."
    parameters = [
        ToolParameter(name="query", type="string", description="Search query.", required=True),
        ToolParameter(name="max_results", type="integer", description="Maximum results.", required=False, default=5),
    ]

    def __init__(self, api_key: str | None, http_client: httpx.AsyncClient | None = None):
        self.api_key = api_key
        self.http_client = http_client
        self._owns_client = http_client is None

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is required for search")
        client = self.http_client or httpx.AsyncClient(timeout=30)
        response = await client.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "query": arguments["query"],
                "search_depth": "basic",
                "max_results": int(arguments.get("max_results", 5)),
                "include_answer": True,
            },
        )
        response.raise_for_status()
        data = response.json()
        if self._owns_client:
            await client.aclose()
        return {
            "answer": data.get("answer"),
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content"),
                }
                for item in data.get("results", [])
            ],
        }
```

- [ ] **Step 4: Implement Open-Meteo weather tool**

```python
# src/tools/weather.py
from typing import Any

import httpx

from src.tools.base import BaseTool, ToolParameter


class OpenMeteoWeatherTool(BaseTool):
    name = "get_weather"
    description = "Get current weather for a location."
    parameters = [
        ToolParameter(name="location", type="string", description="Location name.", required=True),
        ToolParameter(name="unit", type="string", description="celsius or fahrenheit.", required=False, default="celsius"),
    ]

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self.http_client = http_client
        self._owns_client = http_client is None

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        client = self.http_client or httpx.AsyncClient(timeout=30)
        location = str(arguments["location"])
        unit = str(arguments.get("unit", "celsius"))
        geocode = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "language": "en", "format": "json"},
        )
        geocode.raise_for_status()
        results = geocode.json().get("results") or []
        if not results:
            raise ValueError(f"Location not found: {location}")
        place = results[0]
        forecast = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "temperature_unit": "fahrenheit" if unit == "fahrenheit" else "celsius",
            },
        )
        forecast.raise_for_status()
        data = forecast.json()
        if self._owns_client:
            await client.aclose()
        current = data["current"]
        units = data.get("current_units", {})
        return {
            "location": {
                "name": place.get("name"),
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
            },
            "current": {
                "temperature": current.get("temperature_2m"),
                "temperature_unit": units.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "weather_code": current.get("weather_code"),
                "wind_speed": current.get("wind_speed_10m"),
                "wind_speed_unit": units.get("wind_speed_10m"),
            },
        }
```

- [ ] **Step 5: Run HTTP tool tests**

Run: `uv run pytest tests/unit/tools/test_search_weather.py -v`

Expected: PASS.

- [ ] **Step 6: Commit HTTP tools**

```bash
git add src/tools/search.py src/tools/weather.py tests/unit/tools/test_search_weather.py
git commit -m "feat: add search and weather tools"
```

---

### Task 7: Context Pipeline

**Files:**
- Create: `src/context/__init__.py`
- Create: `src/context/token_counter.py`
- Create: `src/context/history.py`
- Create: `src/context/compress.py`
- Create: `src/context/builder.py`
- Test: `tests/unit/context/test_context_builder.py`

- [ ] **Step 1: Write failing context tests**

```python
# tests/unit/context/test_context_builder.py
from datetime import datetime, timedelta, timezone

import pytest

from src.context.builder import ContextBuilder, ContextConfig, ContextPacket, jaccard_similarity
from src.context.compress import StaticCompressor


def test_jaccard_similarity_uses_word_sets():
    assert jaccard_similarity("qwen weather", "qwen search") == pytest.approx(1 / 3)
    assert jaccard_similarity("", "qwen") == 0.0


@pytest.mark.asyncio
async def test_context_builder_sorts_by_relevance_and_recency():
    now = datetime.now(timezone.utc)
    builder = ContextBuilder(
        config=ContextConfig(max_tokens=1000, min_relevance=0.0),
        compressor=StaticCompressor("compressed"),
    )
    result = await builder.build(
        task="Need weather in Beijing",
        system_policy="You are helpful.",
        history=[],
        memory_packets=[
            ContextPacket("weather Beijing sunny", now - timedelta(minutes=1), 0.0, {"source": "memory"}),
            ContextPacket("unrelated cooking", now - timedelta(days=20), 0.0, {"source": "memory"}),
        ],
    )

    assert "[Role & Policies]\nYou are helpful." in result.text
    assert "[Task]\nNeed weather in Beijing" in result.text
    assert result.selected_packets[0].content == "weather Beijing sunny"


@pytest.mark.asyncio
async def test_context_builder_compresses_context_when_token_budget_exceeded():
    now = datetime.now(timezone.utc)
    builder = ContextBuilder(
        config=ContextConfig(max_tokens=20, enable_compression=True, min_relevance=0.0),
        compressor=StaticCompressor("compressed memory summary"),
    )

    result = await builder.build(
        task="summarize",
        system_policy="policy",
        history=[],
        memory_packets=[ContextPacket("word " * 200, now, 1.0, {})],
    )

    assert "compressed memory summary" in result.text
    assert result.compressed is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/context/test_context_builder.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.context.builder'`.

- [ ] **Step 3: Implement token counting and compressor protocol**

```python
# src/context/token_counter.py
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)
```

```python
# src/context/compress.py
from typing import Protocol


class Compressor(Protocol):
    async def compress(self, text: str, max_tokens: int) -> str:
        ...


class StaticCompressor:
    def __init__(self, text: str):
        self.text = text

    async def compress(self, text: str, max_tokens: int) -> str:
        return self.text
```

```python
# src/context/history.py
from src.core.session_store import MessageRecord


def format_history(messages: list[MessageRecord]) -> str:
    return "\n".join(f"{message.role}: {message.content}" for message in messages)
```

- [ ] **Step 4: Implement context builder**

```python
# src/context/builder.py
from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp
import re
from typing import Any

from src.context.compress import Compressor
from src.context.history import format_history
from src.context.token_counter import estimate_tokens
from src.core.session_store import MessageRecord


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\w\u4e00-\u9fff]+", text.lower()))


def jaccard_similarity(a: str, b: str) -> float:
    left = tokenize(a)
    right = tokenize(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


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
    timestamp: datetime
    relevance_score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class BuiltContext:
    text: str
    selected_packets: list[ContextPacket]
    compressed: bool


class ContextBuilder:
    def __init__(self, config: ContextConfig, compressor: Compressor):
        self.config = config
        self.compressor = compressor

    async def build(
        self,
        task: str,
        system_policy: str,
        history: list[MessageRecord],
        memory_packets: list[ContextPacket],
        custom_packets: list[ContextPacket] | None = None,
    ) -> BuiltContext:
        now = datetime.now(timezone.utc)
        packets = memory_packets + (custom_packets or [])
        scored = sorted(
            packets,
            key=lambda packet: self._combined_score(packet, task, now),
            reverse=True,
        )
        selected = [
            packet for packet in scored if self._combined_score(packet, task, now) >= self.config.min_relevance
        ]
        context_text = "\n".join(packet.content for packet in selected)
        history_text = format_history(history)
        output_text = "Stream the final answer as plain conversational text."
        full = self._structure(system_policy, task, "active", history_text, context_text, output_text)
        compressed = False
        if self.config.enable_compression and estimate_tokens(full) > self.config.max_tokens:
            compressed_context = await self.compressor.compress(
                context_text,
                int(self.config.max_tokens * (1 - self.config.reserve_ratio)),
            )
            full = self._structure(system_policy, task, "active", history_text, compressed_context, output_text)
            compressed = True
        return BuiltContext(text=full, selected_packets=selected, compressed=compressed)

    def _combined_score(self, packet: ContextPacket, task: str, now: datetime) -> float:
        relevance = jaccard_similarity(packet.content, task)
        age_hours = (now - packet.timestamp).total_seconds() / 3600
        recency = clamp(exp(-0.1 * age_hours / 24), 0.1, 1.0)
        return self.config.relevance_weight * relevance + self.config.recency_weight * recency

    def _structure(
        self,
        system_policy: str,
        task: str,
        state: str,
        history_text: str,
        context_text: str,
        output_text: str,
    ) -> str:
        return "\n\n".join(
            [
                f"[Role & Policies]\n{system_policy}",
                f"[Task]\n{task}",
                f"[State]\n{state}",
                f"[Context]\n{history_text}\n{context_text}".strip(),
                f"[Output]\n{output_text}",
            ]
        )
```

- [ ] **Step 5: Run context tests**

Run: `uv run pytest tests/unit/context/test_context_builder.py -v`

Expected: PASS.

- [ ] **Step 6: Commit context pipeline**

```bash
git add src/context tests/unit/context/test_context_builder.py
git commit -m "feat: add context builder pipeline"
```

---

### Task 8: Qwen Client And LLM Compression

**Files:**
- Create: `src/agents/__init__.py`
- Create: `src/agents/qwen_client.py`
- Modify: `src/context/compress.py`
- Test: `tests/unit/agents/test_qwen_client.py`

- [ ] **Step 1: Write failing Qwen client tests**

```python
# tests/unit/agents/test_qwen_client.py
import json

import httpx
import pytest

from src.agents.qwen_client import QwenClient
from src.context.compress import QwenCompressor


@pytest.mark.asyncio
async def test_qwen_client_posts_openai_compatible_payload():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert request.url == "https://dashscope.test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer key"
        assert payload["model"] == "qwen-plus"
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "hello"}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    qwen = QwenClient("key", "https://dashscope.test/v1", "qwen-plus", http_client=client)

    message = await qwen.create_completion([{"role": "user", "content": "hi"}])

    assert message["content"] == "hello"
    await client.aclose()


@pytest.mark.asyncio
async def test_qwen_client_streams_sse_tokens():
    async def handler(request: httpx.Request) -> httpx.Response:
        lines = [
            'data: {"choices":[{"delta":{"content":"he"}}]}',
            'data: {"choices":[{"delta":{"content":"llo"}}]}',
            "data: [DONE]",
        ]
        return httpx.Response(200, content="\n\n".join(lines).encode())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    qwen = QwenClient("key", "https://dashscope.test/v1", "qwen-plus", http_client=client)

    chunks = [chunk async for chunk in qwen.stream_completion([{"role": "user", "content": "hi"}])]

    assert chunks == ["he", "llo"]
    await client.aclose()


@pytest.mark.asyncio
async def test_qwen_compressor_uses_client_completion():
    class FakeClient:
        async def create_completion(self, messages, tools=None, tool_choice=None):
            assert "Compress context" in messages[0]["content"]
            return {"role": "assistant", "content": "short summary"}

    compressor = QwenCompressor(FakeClient())

    assert await compressor.compress("long text", max_tokens=20) == "short summary"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/agents/test_qwen_client.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.agents.qwen_client'`.

- [ ] **Step 3: Implement Qwen client**

```python
# src/agents/qwen_client.py
import json
from typing import Any, AsyncIterator

import httpx


class QwenClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http_client = http_client
        self._owns_client = http_client is None

    async def create_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._payload(messages, stream=False, tools=tools, tool_choice=tool_choice)
        client = self.http_client or httpx.AsyncClient(timeout=60)
        response = await client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        if self._owns_client:
            await client.aclose()
        return data["choices"][0]["message"]

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        payload = self._payload(messages, stream=True, tools=tools, tool_choice=tool_choice)
        client = self.http_client or httpx.AsyncClient(timeout=None)
        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
        if self._owns_client:
            await client.aclose()

    def _payload(
        self,
        messages: list[dict[str, Any]],
        stream: bool,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": stream}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        return payload

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
```

- [ ] **Step 4: Add Qwen compressor**

```python
# src/context/compress.py
from typing import Protocol


class Compressor(Protocol):
    async def compress(self, text: str, max_tokens: int) -> str:
        ...


class StaticCompressor:
    def __init__(self, text: str):
        self.text = text

    async def compress(self, text: str, max_tokens: int) -> str:
        return self.text


class QwenCompressor:
    def __init__(self, qwen_client):
        self.qwen_client = qwen_client

    async def compress(self, text: str, max_tokens: int) -> str:
        message = await self.qwen_client.create_completion(
            [
                {
                    "role": "system",
                    "content": f"Compress context into at most {max_tokens} estimated tokens.",
                },
                {"role": "user", "content": text},
            ]
        )
        return message.get("content") or ""
```

```python
# src/agents/__init__.py
```

- [ ] **Step 5: Run Qwen client tests**

Run: `uv run pytest tests/unit/agents/test_qwen_client.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Qwen client**

```bash
git add src/agents src/context/compress.py tests/unit/agents/test_qwen_client.py
git commit -m "feat: add qwen client and compressor"
```

---

### Task 9: ReAct Agent Tool Loop

**Files:**
- Create: `src/core/agent.py`
- Create: `src/core/streaming.py`
- Create: `src/core/trace_logger.py`
- Create: `src/agents/react_agent.py`
- Test: `tests/unit/agents/test_react_agent.py`
- Test: `tests/unit/core/test_streaming_trace.py`

- [ ] **Step 1: Write failing Agent tool-loop test**

```python
# tests/unit/agents/test_react_agent.py
from datetime import datetime, timezone

import pytest

from src.agents.react_agent import ReactAgent
from src.context.builder import BuiltContext
from src.tools.calculator import CalculatorTool
from src.tools.registry import ToolRegistry


class FakeQwenClient:
    def __init__(self):
        self.messages_seen = []

    async def create_completion(self, messages, tools=None, tool_choice=None):
        self.messages_seen.append(messages)
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "calculator", "arguments": '{"expression":"6*7"}'},
                }
            ],
        }

    async def stream_completion(self, messages, tools=None, tool_choice=None):
        self.messages_seen.append(messages)
        for chunk in ["The answer is ", "42."]:
            yield chunk


class FakeContextBuilder:
    async def build(self, task, system_policy, history, memory_packets, custom_packets=None):
        return BuiltContext(text="structured context", selected_packets=[], compressed=False)


class FakeSessionStore:
    def __init__(self):
        self.messages = []

    async def get_session(self, user_id, session_id):
        return object()

    async def add_message(self, user_id, session_id, role, content):
        self.messages.append((user_id, session_id, role, content))

    async def get_recent_messages(self, user_id, session_id, limit=10):
        return []


class FakeMemory:
    async def search(self, user_id, session_id, query, limit=5):
        return []

    async def add(self, user_id, session_id, content, metadata=None):
        return object()


class FakeTraceLogger:
    async def log(self, trace_id, event_type, payload):
        return None


@pytest.mark.asyncio
async def test_agent_invokes_tool_and_streams_integrated_answer():
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    session_store = FakeSessionStore()
    agent = ReactAgent(
        qwen_client=FakeQwenClient(),
        registry=registry,
        context_builder=FakeContextBuilder(),
        session_store=session_store,
        memory_store=FakeMemory(),
        trace_logger=FakeTraceLogger(),
    )

    events = [
        event async for event in agent.stream_chat("alice", "s1", "calculate 6*7", {"source": "test"})
    ]

    assert [event.type for event in events] == [
        "message_start",
        "tool_call",
        "tool_result",
        "token",
        "token",
        "message_end",
    ]
    assert events[1].data["name"] == "calculator"
    assert events[2].data["success"] is True
    assert ("alice", "s1", "assistant", "The answer is 42.") in session_store.messages
```

- [ ] **Step 2: Write failing trace logger test**

```python
# tests/unit/core/test_streaming_trace.py
import json
from pathlib import Path

import pytest

from src.core.agent import AgentEvent
from src.core.streaming import format_sse
from src.core.trace_logger import TraceLogger


def test_format_sse_serializes_event():
    event = AgentEvent(type="token", data={"text": "hello"})

    assert format_sse(event) == 'event: token\ndata: {"text":"hello"}\n\n'


@pytest.mark.asyncio
async def test_trace_logger_writes_jsonl_and_html(tmp_path: Path):
    logger = TraceLogger(tmp_path)

    await logger.log("trace-1", "tool_call", {"name": "calculator"})

    jsonl = tmp_path / "trace-1.jsonl"
    html = tmp_path / "trace-1.html"
    assert json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])["event_type"] == "tool_call"
    assert "calculator" in html.read_text(encoding="utf-8")
```

- [ ] **Step 3: Run tests to verify failure**

Run: `uv run pytest tests/unit/agents/test_react_agent.py tests/unit/core/test_streaming_trace.py -v`

Expected: FAIL with missing `src.agents.react_agent` and `src.core.streaming`.

- [ ] **Step 4: Implement Agent event, SSE formatting, and trace logger**

```python
# src/core/agent.py
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentEvent:
    type: str
    data: dict[str, Any]
```

```python
# src/core/streaming.py
import json

from src.core.agent import AgentEvent


def format_sse(event: AgentEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False, separators=(',', ':'))}\n\n"
```

```python
# src/core/trace_logger.py
from datetime import datetime, timezone
import html
import json
from pathlib import Path
from typing import Any


class TraceLogger:
    def __init__(self, trace_dir: Path):
        self.trace_dir = trace_dir

    async def log(self, trace_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        jsonl_path = self.trace_dir / f"{trace_id}.jsonl"
        html_path = self.trace_dir / f"{trace_id}.html"
        with jsonl_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        existing = html_path.read_text(encoding="utf-8") if html_path.exists() else "<html><body><ol>"
        row = f"<li><strong>{html.escape(event_type)}</strong><pre>{html.escape(json.dumps(payload, ensure_ascii=False, indent=2))}</pre></li>"
        html_path.write_text(existing + row + "</ol></body></html>", encoding="utf-8")
```

- [ ] **Step 5: Implement ReAct Agent two-phase tool loop**

```python
# src/agents/react_agent.py
import json
from typing import Any, AsyncIterator
from uuid import uuid4

from src.context.builder import ContextPacket
from src.core.agent import AgentEvent


SYSTEM_POLICY = (
    "You are a backend MVP Agent. Use tools when they are useful. "
    "When tool results are provided, integrate them into the final answer."
)


class ReactAgent:
    def __init__(
        self,
        qwen_client,
        registry,
        context_builder,
        session_store,
        memory_store,
        trace_logger,
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
        trace_id = str(uuid4())
        session = await self.session_store.get_session(user_id, session_id)
        if session is None:
            yield AgentEvent("error", {"message": "session not found"})
            return
        await self.session_store.add_message(user_id, session_id, "user", message)
        history = await self.session_store.get_recent_messages(user_id, session_id, limit=10)
        memory_hits = await self.memory_store.search(user_id, session_id, message, limit=5)
        memory_packets = [
            ContextPacket(hit.content, _parse_timestamp(hit.created_at), hit.score, hit.metadata)
            for hit in memory_hits
        ]
        built = await self.context_builder.build(
            task=message,
            system_policy=SYSTEM_POLICY,
            history=history,
            memory_packets=memory_packets,
        )
        yield AgentEvent("message_start", {"trace_id": trace_id})
        messages = [{"role": "system", "content": built.text}, {"role": "user", "content": message}]
        first = await self.qwen_client.create_completion(messages, tools=self.registry.to_qwen_tools())
        tool_calls = first.get("tool_calls") or []
        if tool_calls:
            messages.append({"role": "assistant", "content": first.get("content"), "tool_calls": tool_calls})
        for call in tool_calls:
            name = call["function"]["name"]
            arguments = json.loads(call["function"].get("arguments") or "{}")
            await self.trace_logger.log(trace_id, "tool_call", {"name": name, "arguments": arguments})
            yield AgentEvent("tool_call", {"id": call["id"], "name": name, "arguments": arguments})
            result = await self.registry.invoke(name, arguments)
            result_payload = {
                "success": result.success,
                "data": result.data,
                "error_code": result.error_code,
                "message": result.message,
                "elapsed_ms": result.elapsed_ms,
            }
            await self.trace_logger.log(trace_id, "tool_result", result_payload)
            yield AgentEvent("tool_result", {"id": call["id"], **result_payload})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result_payload, ensure_ascii=False),
                }
            )
        answer_parts = []
        async for token in self.qwen_client.stream_completion(messages):
            answer_parts.append(token)
            yield AgentEvent("token", {"text": token})
        final_answer = "".join(answer_parts)
        await self.session_store.add_message(user_id, session_id, "assistant", final_answer)
        await self.memory_store.add(user_id, session_id, final_answer, {"source": "assistant"})
        await self.trace_logger.log(trace_id, "message_end", {"length": len(final_answer)})
        yield AgentEvent("message_end", {"trace_id": trace_id})


def _parse_timestamp(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)
```

- [ ] **Step 6: Run Agent and trace tests**

Run: `uv run pytest tests/unit/agents/test_react_agent.py tests/unit/core/test_streaming_trace.py -v`

Expected: PASS.

- [ ] **Step 7: Commit Agent loop**

```bash
git add src/agents/react_agent.py src/core/agent.py src/core/streaming.py src/core/trace_logger.py tests/unit/agents/test_react_agent.py tests/unit/core/test_streaming_trace.py
git commit -m "feat: add tool-calling agent loop"
```

---

### Task 10: FastAPI Routes And Dependency Wiring

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/dependencies.py`
- Create: `src/api/routes.py`
- Create: `src/api/schemas.py`
- Create: `src/main.py`
- Modify: `README.md`
- Test: `tests/conftest.py`
- Test: `tests/api/test_health_sessions_tools.py`
- Test: `tests/api/test_chat_stream.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/api/test_health_sessions_tools.py
import httpx
import pytest
from asgi_lifespan import LifespanManager

from src.main import create_app


@pytest.mark.asyncio
async def test_health_and_session_isolation(tmp_path):
    app = create_app(data_dir=tmp_path)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            created = await client.post("/sessions", headers={"X-User-Id": "alice"})
            session_id = created.json()["session_id"]
            alice_sessions = await client.get("/sessions", headers={"X-User-Id": "alice"})
            bob_sessions = await client.get("/sessions", headers={"X-User-Id": "bob"})
            bob_delete = await client.delete(f"/sessions/{session_id}", headers={"X-User-Id": "bob"})

    assert alice_sessions.json()["sessions"][0]["session_id"] == session_id
    assert bob_sessions.json()["sessions"] == []
    assert bob_delete.status_code == 404


@pytest.mark.asyncio
async def test_tools_list_and_calculator_invoke(tmp_path):
    app = create_app(data_dir=tmp_path)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            tools = await client.get("/tools")
            result = await client.post("/tools/calculator/invoke", json={"expression": "8*9"})

    assert "calculator" in [tool["name"] for tool in tools.json()["tools"]]
    assert result.json()["success"] is True
    assert result.json()["data"]["result"] == 72
```

```python
# tests/api/test_chat_stream.py
import json

import httpx
import pytest
from asgi_lifespan import LifespanManager

from src.main import create_app


@pytest.mark.asyncio
async def test_chat_stream_emits_sse_events(tmp_path):
    app = create_app(data_dir=tmp_path)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post("/sessions", headers={"X-User-Id": "alice"})
            session_id = created.json()["session_id"]
            response = await client.post(
                "/chat/stream",
                headers={"X-User-Id": "alice"},
                json={"session_id": session_id, "message": "calculate 6*7"},
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: message_start" in response.text
    assert "event: token" in response.text
    assert "event: message_end" in response.text
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/api -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.main'`.

- [ ] **Step 3: Implement API schemas and dependencies**

```python
# src/api/schemas.py
from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    metadata: dict | None = None
```

```python
# src/api/dependencies.py
from typing import Annotated

from fastapi import Header, HTTPException


async def require_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    return x_user_id
```

- [ ] **Step 4: Implement routes and app factory**

```python
# src/api/routes.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.dependencies import require_user_id
from src.api.schemas import ChatStreamRequest
from src.core.streaming import format_sse

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    settings = request.app.state.settings
    return {
        "status": "ok",
        "model_configured": bool(settings.dashscope_api_key),
        "sqlite_available": True,
    }


@router.post("/sessions")
async def create_session(request: Request, user_id: str = Depends(require_user_id)):
    record = await request.app.state.session_store.create_session(user_id)
    return record.__dict__


@router.get("/sessions")
async def list_sessions(request: Request, user_id: str = Depends(require_user_id)):
    records = await request.app.state.session_store.list_sessions(user_id)
    return {"sessions": [record.__dict__ for record in records]}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request, user_id: str = Depends(require_user_id)):
    deleted = await request.app.state.session_store.delete_session(user_id, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")
    return {"deleted": True}


@router.get("/tools")
async def list_tools(request: Request):
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": [param.__dict__ for param in tool.parameters],
            }
            for tool in request.app.state.registry.list_tools()
        ]
    }


@router.post("/tools/{tool_name}/invoke")
async def invoke_tool(tool_name: str, arguments: dict, request: Request):
    result = await request.app.state.registry.invoke(tool_name, arguments)
    return result.__dict__


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatStreamRequest,
    request: Request,
    user_id: str = Depends(require_user_id),
):
    async def event_source():
        async for event in request.app.state.agent.stream_chat(
            user_id,
            payload.session_id,
            payload.message,
            payload.metadata or {},
        ):
            yield format_sse(event)

    return StreamingResponse(event_source(), media_type="text/event-stream")
```

```python
# src/main.py
from pathlib import Path

from fastapi import FastAPI

from src.agents.qwen_client import QwenClient
from src.agents.react_agent import ReactAgent
from src.api.routes import router
from src.context.builder import ContextBuilder, ContextConfig
from src.context.compress import QwenCompressor, StaticCompressor
from src.core.config import Settings
from src.core.memory import SQLiteMemoryStore
from src.core.session_store import SQLiteSessionStore
from src.core.trace_logger import TraceLogger
from src.tools.calculator import CalculatorTool
from src.tools.registry import ToolRegistry
from src.tools.search import TavilySearchTool
from src.tools.weather import OpenMeteoWeatherTool


def create_app(data_dir: Path | None = None) -> FastAPI:
    settings = Settings(_env_file=".env")
    if data_dir is not None:
        settings.app_data_dir = data_dir
    app = FastAPI(title=settings.app_name)
    session_store = SQLiteSessionStore(settings.sqlite_path)
    memory_store = SQLiteMemoryStore(settings.sqlite_path)
    registry = ToolRegistry(
        timeout_seconds=settings.tool_timeout_seconds,
        failure_threshold=settings.circuit_breaker_failure_threshold,
    )
    registry.register(CalculatorTool())
    registry.register(TavilySearchTool(settings.tavily_api_key))
    registry.register(OpenMeteoWeatherTool())
    if settings.dashscope_api_key:
        qwen_client = QwenClient(settings.dashscope_api_key, settings.dashscope_base_url, settings.llm_model_id)
        compressor = QwenCompressor(qwen_client)
    else:
        qwen_client = _LocalEchoClient()
        compressor = StaticCompressor("compressed context")
    context_builder = ContextBuilder(ContextConfig(), compressor)
    trace_logger = TraceLogger(settings.data_dir / "traces")
    app.state.settings = settings
    app.state.session_store = session_store
    app.state.memory_store = memory_store
    app.state.registry = registry
    app.state.agent = ReactAgent(qwen_client, registry, context_builder, session_store, memory_store, trace_logger)

    @app.on_event("startup")
    async def startup():
        await session_store.initialize()
        await memory_store.initialize()

    app.include_router(router)
    return app


class _LocalEchoClient:
    async def create_completion(self, messages, tools=None, tool_choice=None):
        return {"role": "assistant", "content": "local response"}

    async def stream_completion(self, messages, tools=None, tool_choice=None):
        yield "local response"


app = create_app()
```

```python
# src/api/__init__.py
```

- [ ] **Step 5: Run API tests**

Run: `uv run pytest tests/api -v`

Expected: PASS.

- [ ] **Step 6: Commit API layer**

```bash
git add src/api src/main.py tests/api README.md
git commit -m "feat: expose backend mvp api"
```

---

### Task 11: Real External Integration Smoke Tests

**Files:**
- Create: `tests/integration/test_external_smoke.py`
- Modify: `README.md`

- [ ] **Step 1: Write integration smoke tests**

```python
# tests/integration/test_external_smoke.py
import pytest

from src.agents.qwen_client import QwenClient
from src.core.config import Settings
from src.tools.calculator import CalculatorTool
from src.tools.registry import ToolRegistry
from src.tools.search import TavilySearchTool
from src.tools.weather import OpenMeteoWeatherTool


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_real_open_meteo_weather_smoke():
    tool = OpenMeteoWeatherTool()

    result = await tool.run({"location": "Beijing", "unit": "celsius"})

    assert result["location"]["latitude"]
    assert result["current"]["temperature"] is not None


@pytest.mark.asyncio
async def test_real_tavily_search_smoke():
    settings = Settings(_env_file=".env")
    if not settings.tavily_api_key:
        pytest.skip("TAVILY_API_KEY is not set")
    tool = TavilySearchTool(api_key=settings.tavily_api_key)

    result = await tool.run({"query": "Qwen function calling documentation", "max_results": 2})

    assert result["results"]
    assert result["results"][0]["url"]


@pytest.mark.asyncio
async def test_real_qwen_tool_call_smoke():
    settings = Settings(_env_file=".env")
    if not settings.dashscope_api_key:
        pytest.skip("DASHSCOPE_API_KEY is not set")
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    client = QwenClient(settings.dashscope_api_key, settings.dashscope_base_url, settings.llm_model_id)

    message = await client.create_completion(
        [
            {
                "role": "system",
                "content": "You must use the calculator tool for arithmetic.",
            },
            {"role": "user", "content": "Use the calculator tool to compute 19 * 23."},
        ],
        tools=registry.to_qwen_tools(),
    )

    assert message.get("tool_calls"), message
    assert message["tool_calls"][0]["function"]["name"] == "calculator"
```

- [ ] **Step 2: Run weather-only smoke test**

Run: `uv run pytest tests/integration/test_external_smoke.py::test_real_open_meteo_weather_smoke -v -m integration`

Expected: PASS with a real Open-Meteo response.

- [ ] **Step 3: Run key-backed smoke tests**

Run: `uv run pytest tests/integration -v -m integration`

Expected: PASS for Qwen and Tavily when keys exist in `.env`; SKIP with clear skip messages if keys are missing from the process environment.

- [ ] **Step 4: Commit smoke tests**

```bash
git add tests/integration/test_external_smoke.py README.md docs/issue-resolution-log.md
git commit -m "test: add external integration smoke tests"
```

---

### Task 12: Combined Debug, Full Verification, And Final Git Hygiene

**Files:**
- Modify as required by failed verification: exact changed files must be listed in `docs/issue-resolution-log.md` before each fix commit.
- Modify: `README.md`
- Modify: `docs/issue-resolution-log.md`

- [ ] **Step 1: Run the complete ordinary test suite**

Run: `uv run pytest -m "not integration" -v`

Expected: PASS for all unit and API tests.

- [ ] **Step 2: Run the real integration suite**

Run: `uv run pytest -m integration -v`

Expected: PASS for Open-Meteo and PASS for Qwen/Tavily when keys are configured.

- [ ] **Step 3: Start the local service**

Run: `uv run uvicorn src.main:app --host 127.0.0.1 --port 8000`

Expected: server starts and logs `Uvicorn running on http://127.0.0.1:8000`.

- [ ] **Step 4: Run a manual session and stream check**

In a second shell, run:

```bash
curl -s -X POST http://127.0.0.1:8000/sessions -H "X-User-Id: alice"
```

Use the returned `session_id`, then run:

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-User-Id: alice" \
  -d "{\"session_id\":\"REPLACE_WITH_SESSION_ID\",\"message\":\"Use calculator to compute 19 * 23 and explain the result.\"}"
```

Expected: SSE output contains `event: message_start`, `event: tool_call`, `event: tool_result`, multiple `event: token` rows, and `event: message_end`.

- [ ] **Step 5: Run a cross-user isolation check**

Run:

```bash
curl -s http://127.0.0.1:8000/sessions -H "X-User-Id: bob"
```

Expected: Bob's response does not include Alice's `session_id`.

- [ ] **Step 6: For each failure, write issue log before the fix**

Use this exact entry shape:

```markdown
## 2026-08-11 - Short failure title

- Date: 2026-08-11
- Symptom: Exact command and failing output summary.
- Root Cause: Concrete code or configuration cause.
- Changed Files: `path/to/file.py`, `tests/path/to/test.py`
- Verification Command: Exact command rerun after the fix.
- Result: PASS, or the remaining error if another fix is required.
```

Then commit each fix:

```bash
git add docs/issue-resolution-log.md path/to/changed_file.py tests/path/to/changed_test.py
git commit -m "fix: resolve short failure title"
```

- [ ] **Step 7: Update README with verified commands**

````markdown
# Backend MVP Agent

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

## Test

```bash
uv run pytest -m "not integration" -v
uv run pytest -m integration -v
```

## Required Headers

All session and chat routes require `X-User-Id`.
````

- [ ] **Step 8: Final repository check**

Run: `git status --short --branch`

Expected: no uncommitted source, test, or docs changes created by this implementation. `.env` and the original source design document may remain untracked unless the user asks to commit them.

- [ ] **Step 9: Commit final docs update**

```bash
git add README.md docs/issue-resolution-log.md
git commit -m "docs: add backend mvp runbook"
```

## Plan Self-Review

- Spec coverage: Tasks 1-12 cover backend-only scope, FastAPI/SSE, Qwen tool calling, calculator/search/weather, session isolation, SQLite memory, context pipeline, trace logging, module tests, external smoke tests, combined debug, issue log, and git commits.
- Ambiguity scan: No unresolved marker terms, deferred requirements, or vague test instructions are intentionally present.
- Type consistency: The plan consistently uses `AgentEvent`, `ToolRegistry.invoke`, `ToolResponse`, `SQLiteSessionStore`, `SQLiteMemoryStore`, `ContextBuilder.build`, `QwenClient.create_completion`, and `QwenClient.stream_completion` across tests and implementation steps.

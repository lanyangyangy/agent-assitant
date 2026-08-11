from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

import aiosqlite


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


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

        async with self._connect() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_user_session_id
                    ON memories (user_id, session_id, id);

                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    content,
                    content='memories',
                    content_rowid='id'
                );
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
        metadata_dict = dict(metadata or {})
        try:
            metadata_json = json.dumps(metadata_dict, ensure_ascii=False, separators=(",", ":"))
        except TypeError as exc:
            raise ValueError("metadata 必须是可 JSON 序列化的字典。") from exc

        created_at = self._now()
        async with self._connect() as db:
            cursor = await db.execute(
                """
                INSERT INTO memories (user_id, session_id, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, session_id, content, metadata_json, created_at),
            )
            memory_id = cursor.lastrowid
            if memory_id is None:
                await db.rollback()
                raise RuntimeError("写入记忆失败：SQLite 未返回记录 ID。")

            await db.execute(
                """
                INSERT INTO memory_fts (rowid, content)
                VALUES (?, ?)
                """,
                (memory_id, content),
            )
            await db.commit()

        return MemoryRecord(
            id=memory_id,
            user_id=user_id,
            session_id=session_id,
            content=content,
            metadata=metadata_dict,
            created_at=created_at,
            score=0.0,
        )

    async def search(
        self,
        user_id: str,
        session_id: str,
        query: str,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        if limit <= 0:
            return []

        fts_query = self._build_fts_query(query)
        if fts_query is None:
            return []

        async with self._connect() as db:
            rows = await db.execute_fetchall(
                """
                SELECT
                    m.id,
                    m.user_id,
                    m.session_id,
                    m.content,
                    m.metadata_json,
                    m.created_at,
                    bm25(memory_fts) AS rank
                FROM memory_fts
                JOIN memories AS m ON m.id = memory_fts.rowid
                WHERE memory_fts MATCH ?
                    AND m.user_id = ?
                    AND m.session_id = ?
                ORDER BY rank ASC, m.id DESC
                LIMIT ?
                """,
                (fts_query, user_id, session_id, limit),
            )

        return [self._memory_from_row(row) for row in rows]

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.db_path) as connection:
            connection.row_factory = aiosqlite.Row
            yield connection

    @staticmethod
    def _build_fts_query(query: str) -> str | None:
        # 只保留词元并逐个加引号，避免未闭合引号、OR 等 FTS 特殊语法炸库。
        tokens = _TOKEN_RE.findall(query)
        if not tokens:
            return None

        return " OR ".join(f'"{token}"' for token in tokens)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @classmethod
    def _memory_from_row(cls, row: aiosqlite.Row) -> MemoryRecord:
        rank = float(row["rank"])
        return MemoryRecord(
            id=row["id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            content=row["content"],
            metadata=cls._metadata_from_json(row["metadata_json"]),
            created_at=row["created_at"],
            score=max(0.0, -rank),
        )

    @staticmethod
    def _metadata_from_json(value: str) -> dict[str, Any]:
        try:
            metadata = json.loads(value)
        except json.JSONDecodeError:
            return {}

        return metadata if isinstance(metadata, dict) else {}

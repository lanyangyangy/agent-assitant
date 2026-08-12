from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

import aiosqlite


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+", re.UNICODE)
_QUESTION_MARKERS = (
    "?",
    "？",
    "什么",
    "吗",
    "呢",
    "谁",
    "哪",
    "哪里",
    "怎么",
    "为什么",
    "是否",
    "能不能",
    "可不可以",
    "记得",
)
_UNCERTAIN_ANSWER_MARKERS = (
    "不记得",
    "无法知道",
    "不知道",
    "没有关于",
    "没有记录",
    "无可用上下文",
    "不具备记忆",
)


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

                DROP TRIGGER IF EXISTS memories_ai;
                DROP TRIGGER IF EXISTS memories_ad;
                DROP TRIGGER IF EXISTS memories_au;
                DROP TABLE IF EXISTS memory_fts;

                CREATE VIRTUAL TABLE memory_fts USING fts5(
                    content,
                    metadata_json,
                    content='memories',
                    content_rowid='id',
                    tokenize='trigram'
                );

                CREATE TRIGGER IF NOT EXISTS memories_ai
                AFTER INSERT ON memories
                BEGIN
                    INSERT INTO memory_fts(rowid, content, metadata_json)
                    VALUES (new.id, new.content, new.metadata_json);
                END;

                CREATE TRIGGER IF NOT EXISTS memories_ad
                AFTER DELETE ON memories
                BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, content, metadata_json)
                    VALUES ('delete', old.id, old.content, old.metadata_json);
                END;

                CREATE TRIGGER IF NOT EXISTS memories_au
                AFTER UPDATE ON memories
                BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, content, metadata_json)
                    VALUES ('delete', old.id, old.content, old.metadata_json);
                    INSERT INTO memory_fts(rowid, content, metadata_json)
                    VALUES (new.id, new.content, new.metadata_json);
                END;
                """
            )
            await db.execute("INSERT INTO memory_fts(memory_fts) VALUES ('rebuild')")
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
                (fts_query, user_id, session_id, max(limit * 4, 20)),
            )

        records = [self._memory_from_row(row) for row in rows]
        records = _rerank_memory_records(query, records)[:limit]
        return self._normalize_scores(records)

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.db_path) as connection:
            connection.row_factory = aiosqlite.Row
            yield connection

    @staticmethod
    def _build_fts_query(query: str) -> str | None:
        # 只保留词元并逐个加引号，避免未闭合引号、OR 等 FTS 特殊语法炸库。
        tokens = _search_terms(query)
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
    def _normalize_scores(records: list[MemoryRecord]) -> list[MemoryRecord]:
        if not records:
            return []

        if len(records) == 1:
            return [replace(records[0], score=1.0)]

        max_raw_score = max(record.score for record in records)
        if max_raw_score <= 0.0:
            return [replace(record, score=1.0) for record in records]

        # BM25 原始分值通常很小，这里按单次搜索内最大值归一化。
        return [
            replace(record, score=min(1.0, max(0.0, record.score / max_raw_score)))
            for record in records
        ]

    @staticmethod
    def _metadata_from_json(value: str) -> dict[str, Any]:
        try:
            metadata = json.loads(value)
        except json.JSONDecodeError:
            return {}

        return metadata if isinstance(metadata, dict) else {}


def _search_terms(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(query):
        for term in _expand_search_token(token):
            if term not in seen:
                terms.append(term)
                seen.add(term)
    return terms


def _expand_search_token(token: str) -> list[str]:
    if not _CJK_RE.fullmatch(token) or len(token) <= 3:
        return [token]

    return [token[index : index + 3] for index in range(len(token) - 2)]


def _rerank_memory_records(query: str, records: list[MemoryRecord]) -> list[MemoryRecord]:
    if not records:
        return []

    records = sorted(
        records,
        key=lambda record: (
            _record_quality_score(record),
            record.score,
            record.id,
        ),
        reverse=True,
    )

    if not _is_recall_query(query):
        return records

    factual_records = [record for record in records if _is_user_fact_record(record)]
    if not factual_records:
        return records

    factual_ids = {record.id for record in factual_records}
    neutral_records = [
        record
        for record in records
        if record.id not in factual_ids and not _is_uncertain_or_question_record(record)
    ]
    return [*factual_records, *neutral_records]


def _record_quality_score(record: MemoryRecord) -> int:
    if _is_user_fact_record(record):
        return 2
    if _is_uncertain_or_question_record(record):
        return 0
    return 1


def _is_user_fact_record(record: MemoryRecord) -> bool:
    user_message = record.metadata.get("user_message")
    return isinstance(user_message, str) and bool(user_message.strip()) and not _looks_like_question(user_message)


def _is_uncertain_or_question_record(record: MemoryRecord) -> bool:
    user_message = record.metadata.get("user_message")
    return (
        isinstance(user_message, str)
        and _looks_like_question(user_message)
        or _contains_any(record.content, _UNCERTAIN_ANSWER_MARKERS)
    )


def _is_recall_query(query: str) -> bool:
    return "记得" in query or ("我" in query and _contains_any(query, ("什么", "哪", "谁", "多少")))


def _looks_like_question(text: str) -> bool:
    return _contains_any(text, _QUESTION_MARKERS)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)

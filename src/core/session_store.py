from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiosqlite


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

        async with self._connect() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, session_id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id, session_id)
                        REFERENCES sessions (user_id, session_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_user_session_id
                    ON messages (user_id, session_id, id);
                """
            )
            await db.commit()

    async def create_session(self, user_id: str) -> SessionRecord:
        session = SessionRecord(
            session_id=str(uuid4()),
            user_id=user_id,
            created_at=self._now(),
        )

        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO sessions (user_id, session_id, created_at)
                VALUES (?, ?, ?)
                """,
                (session.user_id, session.session_id, session.created_at),
            )
            await db.commit()

        return session

    async def get_session(self, user_id: str, session_id: str) -> SessionRecord | None:
        async with self._connect() as db:
            async with db.execute(
                """
                SELECT user_id, session_id, created_at
                FROM sessions
                WHERE user_id = ? AND session_id = ?
                """,
                (user_id, session_id),
            ) as cursor:
                row = await cursor.fetchone()

        return self._session_from_row(row) if row is not None else None

    async def list_sessions(self, user_id: str) -> list[SessionRecord]:
        async with self._connect() as db:
            rows = await db.execute_fetchall(
                """
                SELECT user_id, session_id, created_at
                FROM sessions
                WHERE user_id = ?
                ORDER BY created_at ASC, session_id ASC
                """,
                (user_id,),
            )

        return [self._session_from_row(row) for row in rows]

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                DELETE FROM sessions
                WHERE user_id = ? AND session_id = ?
                """,
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
    ) -> MessageRecord | None:
        async with self._connect() as db:
            created_at = self._now()
            try:
                cursor = await db.execute(
                    """
                    INSERT INTO messages (user_id, session_id, role, content, created_at)
                    SELECT ?, ?, ?, ?, ?
                    WHERE EXISTS (
                        SELECT 1
                        FROM sessions
                        WHERE user_id = ? AND session_id = ?
                    )
                    """,
                    (
                        user_id,
                        session_id,
                        role,
                        content,
                        created_at,
                        user_id,
                        session_id,
                    ),
                )
            except aiosqlite.IntegrityError:
                await db.rollback()
                return None

            if cursor.rowcount == 0:
                await db.rollback()
                return None

            await db.commit()

            return MessageRecord(
                id=cursor.lastrowid,
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                created_at=created_at,
            )

    async def get_recent_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10,
    ) -> list[MessageRecord]:
        if limit <= 0:
            return []

        async with self._connect() as db:
            rows = await db.execute_fetchall(
                """
                SELECT id, user_id, session_id, role, content, created_at
                FROM messages
                WHERE user_id = ? AND session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, session_id, limit),
            )

        return [self._message_from_row(row) for row in reversed(rows)]

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.db_path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("PRAGMA foreign_keys = ON")
            yield connection

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _session_from_row(row: aiosqlite.Row) -> SessionRecord:
        return SessionRecord(
            session_id=row["session_id"],
            user_id=row["user_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _message_from_row(row: aiosqlite.Row) -> MessageRecord:
        return MessageRecord(
            id=row["id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )

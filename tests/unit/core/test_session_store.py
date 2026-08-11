from pathlib import Path

import aiosqlite
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

    assert [message.content for message in recent] == [
        f"message-{index}" for index in range(2, 12)
    ]
    assert await store.get_recent_messages("bob", session.session_id, limit=10) == []


@pytest.mark.asyncio
async def test_add_message_returns_none_when_session_disappears_during_insert(
    tmp_path: Path,
):
    db_path = tmp_path / "agent.sqlite3"
    store = SQLiteSessionStore(db_path)
    await store.initialize()
    session = await store.create_session("alice")

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """
            CREATE TRIGGER delete_session_before_message_insert
            BEFORE INSERT ON messages
            FOR EACH ROW
            BEGIN
                DELETE FROM sessions
                WHERE user_id = NEW.user_id
                    AND session_id = NEW.session_id;
            END;
            """
        )
        await db.commit()

    assert await store.add_message("alice", session.session_id, "user", "hello") is None
    assert await store.get_recent_messages("alice", session.session_id) == []


@pytest.mark.asyncio
async def test_delete_session_is_scoped_and_cascades_messages(tmp_path: Path):
    store = SQLiteSessionStore(tmp_path / "agent.sqlite3")
    await store.initialize()
    session = await store.create_session("alice")

    message = await store.add_message("alice", session.session_id, "user", "hello")

    assert message is not None
    assert await store.delete_session("bob", session.session_id) is False
    recent_messages = await store.get_recent_messages("alice", session.session_id)
    assert [message.content for message in recent_messages] == ["hello"]

    assert await store.delete_session("alice", session.session_id) is True
    assert await store.get_session("alice", session.session_id) is None
    assert await store.get_recent_messages("alice", session.session_id) == []

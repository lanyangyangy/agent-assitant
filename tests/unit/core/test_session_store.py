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

    assert [message.content for message in recent] == [
        f"message-{index}" for index in range(2, 12)
    ]
    assert await store.get_recent_messages("bob", session.session_id, limit=10) == []

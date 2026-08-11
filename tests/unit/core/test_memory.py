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


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   \t\n"])
async def test_blank_query_returns_empty_list(tmp_path: Path, query: str):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()
    await memory.add("alice", "s1", "Calculator tools are available", {"kind": "fact"})

    assert await memory.search("alice", "s1", query) == []


@pytest.mark.asyncio
async def test_query_with_fts_special_characters_is_safe(tmp_path: Path):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()
    await memory.add("alice", "s1", "Calculator tools are available", {"kind": "fact"})

    hits = await memory.search("alice", "s1", 'calculator OR "bad', limit=5)

    assert isinstance(hits, list)
    assert all(hit.user_id == "alice" and hit.session_id == "s1" for hit in hits)


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -1])
async def test_non_positive_limit_returns_empty_list(tmp_path: Path, limit: int):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()
    await memory.add("alice", "s1", "Calculator tools are available", {"kind": "fact"})

    assert await memory.search("alice", "s1", "calculator", limit=limit) == []

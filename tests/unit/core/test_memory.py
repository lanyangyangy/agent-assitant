from pathlib import Path

import aiosqlite
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
async def test_initialize_rebuilds_fts_after_direct_update_and_delete(tmp_path: Path):
    db_path = tmp_path / "agent.sqlite3"
    memory = SQLiteMemoryStore(db_path)
    await memory.initialize()
    updated = await memory.add("alice", "s1", "old calculator phrase", {"kind": "fact"})
    deleted = await memory.add("alice", "s1", "delete marker phrase", {"kind": "fact"})

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE memories
            SET content = ?
            WHERE id = ?
            """,
            ("fresh weather phrase", updated.id),
        )
        await db.execute("DELETE FROM memories WHERE id = ?", (deleted.id,))
        await db.commit()

    await memory.initialize()

    assert await memory.search("alice", "s1", "calculator") == []
    assert await memory.search("alice", "s1", "delete marker") == []
    fresh_hits = await memory.search("alice", "s1", "fresh weather")
    assert [hit.content for hit in fresh_hits] == ["fresh weather phrase"]


@pytest.mark.asyncio
async def test_single_memory_search_score_is_one(tmp_path: Path):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()
    await memory.add("alice", "s1", "Calculator tools are available", {"kind": "fact"})

    hits = await memory.search("alice", "s1", "calculator")

    assert len(hits) == 1
    assert hits[0].score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_multiple_memory_search_scores_are_normalized(tmp_path: Path):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()
    await memory.add("alice", "s1", "Calculator tools are available", {"kind": "fact"})
    await memory.add("alice", "s1", "Calculator tools can answer arithmetic", {"kind": "fact"})
    await memory.add("alice", "s1", "A calculator may call tools", {"kind": "fact"})

    hits = await memory.search("alice", "s1", "calculator tools", limit=5)

    assert len(hits) == 3
    scores = [hit.score for hit in hits]
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert max(scores) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_chinese_memory_search_matches_substring_without_spaces(tmp_path: Path):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()
    await memory.add("alice", "s1", "计算器工具可用", {"kind": "fact"})

    hits = await memory.search("alice", "s1", "计算器")

    assert [hit.content for hit in hits] == ["计算器工具可用"]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -1])
async def test_non_positive_limit_returns_empty_list(tmp_path: Path, limit: int):
    memory = SQLiteMemoryStore(tmp_path / "agent.sqlite3")
    await memory.initialize()
    await memory.add("alice", "s1", "Calculator tools are available", {"kind": "fact"})

    assert await memory.search("alice", "s1", "calculator", limit=limit) == []

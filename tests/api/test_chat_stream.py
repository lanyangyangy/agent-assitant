from __future__ import annotations

import json


def _parse_sse(raw: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in raw.strip().split("\n\n"):
        event_name = None
        event_data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            if line.startswith("data: "):
                event_data = json.loads(line.removeprefix("data: "))
        if event_name is not None:
            events.append({"event": event_name, "data": event_data})
    return events


async def test_chat_stream_runs_local_calculator_tool_call(client):
    created = await client.post("/sessions", headers={"X-User-Id": "alice"})
    session_id = created.json()["session_id"]

    response = await client.post(
        "/chat/stream",
        headers={"X-User-Id": "alice"},
        json={"session_id": session_id, "message": "请计算 6*7", "metadata": {"source": "api-test"}},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    event_names = [event["event"] for event in events]
    assert event_names[0] == "message_start"
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert "token" in event_names
    assert event_names[-1] == "message_end"

    tool_call = next(event for event in events if event["event"] == "tool_call")
    assert tool_call["data"]["name"] == "calculator"

    tool_result = next(event for event in events if event["event"] == "tool_result")
    result = tool_result["data"]["result"]
    assert result["success"] is True
    assert result["data"]["result"] == 42


async def test_chat_stream_returns_sse_error_for_missing_session(client):
    response = await client.post(
        "/chat/stream",
        headers={"X-User-Id": "alice"},
        json={"session_id": "missing-session", "message": "你好"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert [event["event"] for event in events] == ["error"]
    assert "会话" in events[0]["data"]["message"]

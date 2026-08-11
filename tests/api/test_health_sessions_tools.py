from __future__ import annotations


async def test_health_reports_model_and_sqlite_status(client):
    response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_configured"] is False
    assert payload["sqlite_available"] is True
    assert "服务" in payload["message"]


async def test_sessions_are_created_listed_and_deleted_per_user(client):
    missing_user = await client.post("/sessions")
    assert missing_user.status_code == 400
    assert "X-User-Id" in missing_user.json()["detail"]

    created = await client.post("/sessions", headers={"X-User-Id": "alice"})
    assert created.status_code == 201
    alice_session = created.json()
    assert alice_session["user_id"] == "alice"
    assert alice_session["session_id"]
    assert alice_session["created_at"]

    alice_list = await client.get("/sessions", headers={"X-User-Id": "alice"})
    assert alice_list.status_code == 200
    assert alice_list.json() == [alice_session]

    bob_list = await client.get("/sessions", headers={"X-User-Id": "bob"})
    assert bob_list.status_code == 200
    assert bob_list.json() == []

    bob_delete = await client.delete(
        f"/sessions/{alice_session['session_id']}",
        headers={"X-User-Id": "bob"},
    )
    assert bob_delete.status_code == 404
    assert "不存在" in bob_delete.json()["detail"]

    alice_delete = await client.delete(
        f"/sessions/{alice_session['session_id']}",
        headers={"X-User-Id": "alice"},
    )
    assert alice_delete.status_code == 204

    empty_after_delete = await client.get("/sessions", headers={"X-User-Id": "alice"})
    assert empty_after_delete.json() == []


async def test_tools_are_listed_and_calculator_can_be_invoked(client):
    listed = await client.get("/tools")
    assert listed.status_code == 200
    tools = listed.json()
    names = {tool["name"] for tool in tools}
    assert {"calculator", "search", "get_weather"}.issubset(names)
    assert all(isinstance(tool["parameters"], list) for tool in tools)

    calculator = next(tool for tool in tools if tool["name"] == "calculator")
    assert calculator["description"]
    assert calculator["parameters"][0]["name"] == "expression"

    invoked = await client.post("/tools/calculator/invoke", json={"expression": "8*9"})
    assert invoked.status_code == 200
    payload = invoked.json()
    assert payload["success"] is True
    assert payload["data"]["result"] == 72

    invalid_body = await client.post("/tools/calculator/invoke", json=["not", "object"])
    assert invalid_body.status_code in {400, 422}
    assert "参数" in invalid_body.json()["detail"]

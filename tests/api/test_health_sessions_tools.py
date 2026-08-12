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
    assert alice_list.json() == {"sessions": [alice_session]}

    bob_list = await client.get("/sessions", headers={"X-User-Id": "bob"})
    assert bob_list.status_code == 200
    assert bob_list.json() == {"sessions": []}

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
    assert empty_after_delete.json() == {"sessions": []}


async def test_session_messages_are_listed_per_user_after_chat(client):
    created = await client.post("/sessions", headers={"X-User-Id": "alice"})
    session_id = created.json()["session_id"]

    streamed = await client.post(
        "/chat/stream",
        headers={"X-User-Id": "alice"},
        json={"session_id": session_id, "message": "请计算 6*7"},
    )
    assert streamed.status_code == 200

    listed = await client.get(
        f"/sessions/{session_id}/messages",
        headers={"X-User-Id": "alice"},
    )

    assert listed.status_code == 200
    messages = listed.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "请计算 6*7"
    assert "42" in messages[1]["content"]

    bob_listed = await client.get(
        f"/sessions/{session_id}/messages",
        headers={"X-User-Id": "bob"},
    )
    assert bob_listed.status_code == 404
    assert "会话不存在" in bob_listed.json()["detail"]


async def test_missing_user_id_is_required_for_all_user_scoped_endpoints(client):
    get_sessions = await client.get("/sessions")
    assert get_sessions.status_code == 400
    assert "X-User-Id" in get_sessions.json()["detail"]
    assert "缺少" in get_sessions.json()["detail"]

    delete_session = await client.delete("/sessions/not-found")
    assert delete_session.status_code == 400
    assert "X-User-Id" in delete_session.json()["detail"]
    assert "缺少" in delete_session.json()["detail"]

    chat_stream = await client.post(
        "/chat/stream",
        json={"session_id": "not-found", "message": "你好"},
    )
    assert chat_stream.status_code == 400
    assert "X-User-Id" in chat_stream.json()["detail"]
    assert "缺少" in chat_stream.json()["detail"]


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


async def test_tool_invoke_openapi_uses_response_model(client):
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()["paths"]["/tools/{tool_name}/invoke"]["post"]["responses"]["200"]
    assert schema["content"]["application/json"]["schema"]["$ref"].endswith("/ToolInvokeResponse")


async def test_message_response_openapi_limits_role_values(client):
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    role_schema = response.json()["components"]["schemas"]["MessageResponse"]["properties"]["role"]
    assert role_schema["enum"] == ["user", "assistant"]


async def test_search_tool_returns_chinese_unavailable_when_tavily_key_missing(client):
    response = await client.post("/tools/search/invoke", json={"query": "今天新闻"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "搜索工具" in payload["message"]
    assert "TAVILY_API_KEY" in payload["message"]


async def test_close_registry_tools_continues_after_tool_close_failure():
    from src.main import _close_registry_tools

    failed_tool = _CloseTrackingTool(should_fail=True)
    later_tool = _CloseTrackingTool()
    registry = _FakeRegistry([failed_tool, later_tool])

    await _close_registry_tools(registry)

    assert failed_tool.closed is True
    assert later_tool.closed is True


class _FakeRegistry:
    def __init__(self, tools):
        self._tools = tools

    def list_tools(self):
        return self._tools


class _CloseTrackingTool:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.closed = False

    async def aclose(self):
        self.closed = True
        if self.should_fail:
            raise RuntimeError("close failed")

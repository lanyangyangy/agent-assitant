from __future__ import annotations

import json

import httpx
import pytest

from src.agents.qwen_client import QwenClient, QwenClientError
from src.context.compress import QwenCompressor


def test_create_completion_posts_openai_payload_and_keeps_tool_calls():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": "{\"expression\":\"1+1\"}",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    client = QwenClient(
        api_key="test-key",
        base_url="https://dashscope.example/compatible-mode/v1/",
        model="qwen-plus",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    tools = [{"type": "function", "function": {"name": "calculator"}}]

    message = client.create_completion(
        messages=[{"role": "user", "content": "算一下"}],
        tools=tools,
        tool_choice="auto",
    )

    assert captured["url"] == "https://dashscope.example/compatible-mode/v1/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    assert captured["payload"] == {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": "算一下"}],
        "stream": False,
        "tools": tools,
        "tool_choice": "auto",
    }
    assert message["tool_calls"][0]["function"]["name"] == "calculator"


def test_stream_completion_yields_content_tokens_and_skips_non_data_lines():
    sse_body = "\n".join(
        [
            "",
            ": keep-alive",
            "event: ping",
            'data: {"choices":[{"delta":{"content":"你"}}]}',
            "",
            'data: {"choices":[{"delta":{"content":"好"}}]}',
            "data: [DONE]",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["stream"] is True
        return httpx.Response(200, text=sse_body)

    client = QwenClient(
        api_key="test-key",
        base_url="https://dashscope.example/v1",
        model="qwen-plus",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert list(client.stream_completion([{"role": "user", "content": "hello"}])) == ["你", "好"]


def test_http_error_is_wrapped_in_stable_chinese_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    client = QwenClient(
        api_key="test-key",
        base_url="https://dashscope.example/v1",
        model="qwen-plus",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(QwenClientError) as exc_info:
        client.create_completion([{"role": "user", "content": "hello"}])

    message = str(exc_info.value)
    assert "Qwen 请求失败" in message
    assert "503" in message


def test_qwen_compressor_uses_create_completion_with_chinese_system_prompt():
    class FakeQwenClient:
        def __init__(self):
            self.messages: list[dict[str, str]] | None = None

        def create_completion(self, messages, tools=None, tool_choice=None):
            self.messages = messages
            assert tools is None
            assert tool_choice is None
            return {"role": "assistant", "content": "摘要：保留关键事实"}

    fake_client = FakeQwenClient()
    compressor = QwenCompressor(fake_client)

    assert compressor.compress("很长的上下文", task="回答用户问题") == "摘要：保留关键事实"
    assert fake_client.messages is not None
    assert fake_client.messages[0]["role"] == "system"
    assert "中文" in fake_client.messages[0]["content"]
    assert "回答用户问题" in fake_client.messages[1]["content"]

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
import json
from typing import Any

import httpx


class QwenClientError(RuntimeError):
    """Qwen 调用失败时抛出的稳定业务异常。"""


class QwenClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        http_client: httpx.AsyncClient | None = None,
    ):
        if not api_key:
            raise ValueError("Qwen API Key 不能为空。")
        if not base_url:
            raise ValueError("Qwen base_url 不能为空。")
        if not model:
            raise ValueError("Qwen model 不能为空。")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http_client = http_client or httpx.AsyncClient(timeout=60)

    async def create_completion(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._payload(messages, stream=False, tools=tools, tool_choice=tool_choice)

        try:
            response = await self.http_client.post(
                self._completion_url(),
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise self._http_error(exc) from exc
        except httpx.RequestError as exc:
            raise QwenClientError(f"Qwen 请求失败：网络错误，{exc}") from exc
        except json.JSONDecodeError as exc:
            raise QwenClientError("Qwen 请求失败：响应不是有效 JSON。") from exc

        return self._message_from_response(data)

    async def stream_completion(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        payload = self._payload(messages, stream=True, tools=tools, tool_choice=tool_choice)

        try:
            async with self.http_client.stream(
                "POST",
                self._completion_url(),
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    token = self._token_from_sse_line(line)
                    if token is _Done:
                        break
                    if isinstance(token, str) and token:
                        yield token
        except httpx.HTTPStatusError as exc:
            raise self._http_error(exc) from exc
        except httpx.RequestError as exc:
            raise QwenClientError(f"Qwen 请求失败：网络错误，{exc}") from exc

    def _payload(
        self,
        messages: Sequence[dict[str, Any]],
        stream: bool,
        tools: Sequence[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "stream": stream,
        }
        if tools is not None:
            payload["tools"] = list(tools)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        return payload

    def _completion_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _message_from_response(data: dict[str, Any]) -> dict[str, Any]:
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise QwenClientError("Qwen 请求失败：响应缺少 message 字段。") from exc

        if not isinstance(message, dict):
            raise QwenClientError("Qwen 请求失败：message 字段格式无效。")
        return message

    @staticmethod
    def _token_from_sse_line(line: str) -> str | object | None:
        clean_line = line.strip()
        if not clean_line or not clean_line.startswith("data:"):
            return None

        data = clean_line[len("data:") :].strip()
        if data == "[DONE]":
            return _Done

        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            return None

        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
        if not isinstance(delta, dict):
            return None

        content = delta.get("content")
        return content if isinstance(content, str) else None

    @staticmethod
    def _http_error(exc: httpx.HTTPStatusError) -> QwenClientError:
        response = exc.response
        body = response.text[:200].strip()
        detail = f"：{body}" if body else ""
        return QwenClientError(f"Qwen 请求失败：HTTP {response.status_code}{detail}")


_Done = object()

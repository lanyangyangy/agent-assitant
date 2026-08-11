from __future__ import annotations

from typing import Any

import httpx

from src.tools.base import BaseTool, ToolParameter


class TavilySearchTool(BaseTool):
    name = "search"
    description = "使用 Tavily 搜索互联网并返回摘要答案和结果列表。"
    parameters = [
        ToolParameter("query", "string", "搜索关键词。"),
        ToolParameter("max_results", "integer", "最多返回的搜索结果数量。", required=False, default=5),
    ]

    def __init__(self, api_key: str | None, http_client: httpx.AsyncClient | None = None):
        if not api_key:
            raise ValueError("缺少 Tavily API Key，请设置 TAVILY_API_KEY。")
        self.api_key = api_key
        self._client = http_client or httpx.AsyncClient()
        self._owns_client = http_client is None

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("参数 query 必须是非空字符串。")

        max_results = arguments.get("max_results", 5)
        if not isinstance(max_results, int) or max_results <= 0:
            raise ValueError("参数 max_results 必须是正整数。")

        response = await self._client.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": True,
            },
        )
        response.raise_for_status()
        payload = response.json()

        return {
            "answer": payload.get("answer"),
            "results": [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content"),
                }
                for item in payload.get("results", [])
            ],
        }

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

from __future__ import annotations

from typing import Any


class SimpleCompressor:
    def __init__(self, max_chars: int = 1200):
        self.max_chars = max(4, max_chars)

    def compress(self, text: str, task: str | None = None) -> str:
        clean_text = text.strip()
        if len(clean_text) < self.max_chars:
            return clean_text

        return clean_text[: self.max_chars - 3].rstrip() + "..."


class QwenCompressor:
    def __init__(self, qwen_client: Any):
        self.qwen_client = qwen_client

    def compress(self, text: str, task: str | None = None) -> str:
        task_text = task or "未提供具体任务"
        message = self.qwen_client.create_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "你是上下文压缩器。请用中文保留和任务相关的事实、约束、"
                        "工具结果和用户偏好，删除重复和闲聊。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"任务：{task_text}\n\n待压缩上下文：\n{text}",
                },
            ]
        )
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()

        return SimpleCompressor().compress(text)

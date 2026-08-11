from __future__ import annotations


class SimpleCompressor:
    def __init__(self, max_chars: int = 1200):
        self.max_chars = max(4, max_chars)

    def compress(self, text: str, task: str | None = None) -> str:
        clean_text = text.strip()
        if len(clean_text) < self.max_chars:
            return clean_text

        return clean_text[: self.max_chars - 3].rstrip() + "..."

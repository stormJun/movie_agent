from __future__ import annotations

from typing import Protocol


class ChatCompletionPort(Protocol):
    async def generate(self, *, message: str, memory_context: str | None = None) -> str:
        ...

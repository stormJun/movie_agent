from __future__ import annotations

from typing import Any, Protocol


class ChatCompletionPort(Protocol):
    async def generate(
        self,
        *,
        message: str,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> str:

        ...

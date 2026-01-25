from __future__ import annotations

from typing import Protocol
from uuid import UUID


class ConversationSummarizerPort(Protocol):
    async def get_summary_text(self, *, conversation_id: UUID) -> str | None:
        ...

    async def schedule_update(self, *, conversation_id: UUID) -> bool:
        ...


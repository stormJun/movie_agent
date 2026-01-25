from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Sequence
from uuid import UUID


class ConversationEpisodicMemoryPort(Protocol):
    """Phase 2: Active Episodic Memory (semantic recall within a conversation)."""

    async def recall_relevant(
        self,
        *,
        conversation_id: UUID,
        query: str,
        top_k: int | None = None,
        exclude_assistant_message_ids: Optional[Sequence[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        ...

    def format_context(self, *, episodes: List[Dict[str, Any]]) -> str | None:
        ...

    async def schedule_index_episode(
        self,
        *,
        conversation_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        user_message: str,
        assistant_message: str,
    ) -> bool:
        ...


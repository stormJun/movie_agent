from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID


class ConversationEpisodeStorePort(Protocol):
    """Phase 2: store for per-conversation episodic memories (semantic recall).

    An "episode" is a completed (user_message, assistant_message) pair indexed
    for later semantic recall within the same conversation.
    """

    async def upsert_episode(
        self,
        *,
        conversation_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        user_message: str,
        assistant_message: str,
        embedding: List[float],
        created_at: datetime,
    ) -> bool:
        ...

    async def list_episodes(
        self,
        *,
        conversation_id: UUID,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        ...

    async def search_episodes(
        self,
        *,
        conversation_id: UUID,
        query_embedding: List[float],
        limit: int,
        scan_limit: int = 200,
        exclude_assistant_message_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """Return episodes with a `similarity` score (higher is better)."""
        ...

    async def close(self) -> None:
        ...

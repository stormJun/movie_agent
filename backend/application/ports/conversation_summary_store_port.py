from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID


class ConversationSummaryStorePort(Protocol):
    """Conversation summary store for Phase 1 (sliding window + summary).

    Notes:
    - Summary uses a cursor (covered_through_created_at, covered_through_message_id)
      because message ids are UUIDv4 and cannot be used for time ordering.
    - Implementations may read from both `conversation_summaries` and `messages`.
    """

    async def get_summary(self, *, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        ...

    async def save_summary_upsert(
        self,
        *,
        conversation_id: UUID,
        summary: str,
        covered_through_created_at: datetime,
        covered_through_message_id: UUID,
        covered_message_count: int,
        expected_version: int | None = None,
    ) -> bool:
        ...

    async def count_completed_messages(self, *, conversation_id: UUID) -> int:
        ...

    async def list_messages_since(
        self,
        *,
        conversation_id: UUID,
        since_created_at: datetime | None,
        since_message_id: UUID | None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        ...

    async def list_recent_messages(
        self,
        *,
        conversation_id: UUID,
        limit: int = 6,
    ) -> List[Dict[str, Any]]:
        """Return newest-first messages (completed only)."""
        ...

    async def close(self) -> None:
        ...


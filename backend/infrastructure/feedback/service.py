from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.feedback_port import FeedbackPort
from infrastructure.persistence.postgres.feedback_store import (
    InMemoryFeedbackStore,
    PostgresFeedbackStore,
)


class PostgresFeedbackService(FeedbackPort):
    """Persist feedback into Postgres (no cache coupling)."""

    def __init__(self, *, store: PostgresFeedbackStore) -> None:
        self._store = store

    async def process_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str,
    ) -> Dict[str, str]:
        await self._store.insert_feedback(
            message_id=message_id,
            query=query,
            is_positive=is_positive,
            thread_id=thread_id,
            agent_type=agent_type,
            metadata=None,
        )
        action = "反馈已记录（positive）" if is_positive else "反馈已记录（negative）"
        return {"status": "success", "action": action}

    async def close(self) -> None:
        await self._store.close()


class InMemoryFeedbackService(FeedbackPort):
    def __init__(self, *, store: Optional[InMemoryFeedbackStore] = None) -> None:
        self._store = store or InMemoryFeedbackStore()

    async def process_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str,
    ) -> Dict[str, str]:
        await self._store.insert_feedback(
            message_id=message_id,
            query=query,
            is_positive=is_positive,
            thread_id=thread_id,
            agent_type=agent_type,
            metadata=None,
        )
        action = "反馈已记录（in_memory）"
        return {"status": "success", "action": action}

    async def close(self) -> None:
        close = getattr(self._store, "close", None)
        if callable(close):
            await close()


def build_feedback_port(*, dsn: str | None) -> FeedbackPort:
    """Factory used by server DI."""
    if dsn:
        return PostgresFeedbackService(store=PostgresFeedbackStore(dsn=dsn))
    return InMemoryFeedbackService()


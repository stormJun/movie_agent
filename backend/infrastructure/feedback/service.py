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
        request_id: str | None = None,
    ) -> Dict[str, str]:
        op, state = await self._store.insert_feedback(
            message_id=message_id,
            query=query,
            is_positive=is_positive,
            thread_id=thread_id,
            agent_type=agent_type,
            metadata={"request_id": request_id} if request_id else None,
        )

        # Best-effort: also attach explicit user feedback to Langfuse as a Score.
        # This powers the "Scores" view and lets us filter traces by quality.
        # NOTE: "cancel" is represented in Postgres by deleting the row. Langfuse
        # doesn't have a strong delete semantic here, so we only record when set.
        if request_id and state in {"positive", "negative"}:
            try:
                from infrastructure.observability.langfuse_handler import (
                    LANGFUSE_ENABLED,
                    _get_langfuse_client,
                    flush_langfuse,
                )

                if LANGFUSE_ENABLED:
                    langfuse = _get_langfuse_client()
                    if langfuse:
                        langfuse.score(
                            trace_id=request_id,
                            name="user_feedback",
                            # Langfuse boolean scores must be 1/0 (float).
                            value=1.0 if state == "positive" else 0.0,
                            data_type="BOOLEAN",
                            comment=query,
                            # Extra fields (ScoreBody allows extra) help debugging in the UI.
                            message_id=message_id,
                            thread_id=thread_id,
                            agent_type=agent_type,
                        )
                        await flush_langfuse()
            except Exception:
                # Observability must be best-effort and never block the main flow.
                pass

        if op == "cleared":
            action = "反馈已取消"
        elif op == "updated":
            action = "反馈已更新（positive）" if state == "positive" else "反馈已更新（negative）"
        else:
            action = "反馈已记录（positive）" if state == "positive" else "反馈已记录（negative）"
        return {"status": "success", "action": action, "feedback": state}

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
        request_id: str | None = None,
    ) -> Dict[str, str]:
        op, state = await self._store.insert_feedback(
            message_id=message_id,
            query=query,
            is_positive=is_positive,
            thread_id=thread_id,
            agent_type=agent_type,
            metadata={"request_id": request_id} if request_id else None,
        )

        if request_id and state in {"positive", "negative"}:
            try:
                from infrastructure.observability.langfuse_handler import (
                    LANGFUSE_ENABLED,
                    _get_langfuse_client,
                    flush_langfuse,
                )

                if LANGFUSE_ENABLED:
                    langfuse = _get_langfuse_client()
                    if langfuse:
                        langfuse.score(
                            trace_id=request_id,
                            name="user_feedback",
                            value=1.0 if state == "positive" else 0.0,
                            data_type="BOOLEAN",
                            comment=query,
                            message_id=message_id,
                            thread_id=thread_id,
                            agent_type=agent_type,
                        )
                        await flush_langfuse()
            except Exception:
                pass
        if op == "cleared":
            action = "反馈已取消（in_memory）"
        elif op == "updated":
            action = f"反馈已更新（{state} / in_memory）"
        else:
            action = f"反馈已记录（{state} / in_memory）"
        return {"status": "success", "action": action, "feedback": state}

    async def close(self) -> None:
        close = getattr(self._store, "close", None)
        if callable(close):
            await close()


def build_feedback_port(*, dsn: str | None) -> FeedbackPort:
    """Factory used by server DI."""
    if dsn:
        return PostgresFeedbackService(store=PostgresFeedbackStore(dsn=dsn))
    return InMemoryFeedbackService()

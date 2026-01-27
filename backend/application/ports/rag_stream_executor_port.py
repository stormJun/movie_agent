from __future__ import annotations

from typing import Any, AsyncGenerator, Protocol

from domain.chat.entities.rag_run import RagRunSpec


class RAGStreamExecutorPort(Protocol):
    async def stream(
        self,
        *,
        plan: list[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        user_id: str | None = None,
        request_id: str | None = None,
        conversation_id: Any | None = None,
        user_message_id: Any | None = None,
        incognito: bool = False,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
        extracted_entities: dict[str, Any] | None = None,
        query_intent: str | None = None,
        media_type_hint: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        ...

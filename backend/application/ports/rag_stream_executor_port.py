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
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
        extracted_entities: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        ...

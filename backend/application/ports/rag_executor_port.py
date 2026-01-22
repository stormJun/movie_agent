from __future__ import annotations

from typing import Protocol

from domain.chat.entities.rag_run import RagRunResult, RagRunSpec


class RAGExecutorPort(Protocol):
    async def run(
        self,
        *,
        plan: list[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        memory_context: str | None = None,
    ) -> tuple[RagRunResult, list[RagRunResult]]:
        ...

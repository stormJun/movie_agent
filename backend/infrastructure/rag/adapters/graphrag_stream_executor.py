from __future__ import annotations

from typing import Any, AsyncGenerator

from application.ports.rag_stream_executor_port import RAGStreamExecutorPort
from domain.chat.entities.rag_run import RagRunSpec
from infrastructure.rag.rag_manager import RagManager
from infrastructure.streaming.chat_stream_executor import ChatStreamExecutor


class GraphragStreamExecutor(RAGStreamExecutorPort):
    def __init__(self, rag_manager: RagManager) -> None:
        self._executor = ChatStreamExecutor(rag_manager=rag_manager)

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
        async for event in self._executor.stream(
            plan=plan,
            message=message,
            session_id=session_id,
            kb_prefix=kb_prefix,
            debug=debug,
            memory_context=memory_context,
            summary=summary,
            episodic_context=episodic_context,
            history=history,
            extracted_entities=extracted_entities,
        ):
            yield event

from __future__ import annotations

from typing import Any

from application.ports.rag_executor_port import RAGExecutorPort
from domain.chat.entities.rag_run import RagRunResult, RagRunSpec
from infrastructure.rag.rag_manager import RagManager


class GraphragExecutor(RAGExecutorPort):
    def __init__(self, rag_manager: RagManager) -> None:
        self._rag_manager = rag_manager

    async def run(
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
    ) -> tuple[RagRunResult, list[RagRunResult]]:
        infra_result, infra_runs = await self._rag_manager.run_plan_blocking(
            plan=plan,
            message=message,
            session_id=session_id,
            kb_prefix=kb_prefix,
            debug=debug,
            user_id=user_id,
            request_id=request_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            incognito=incognito,
            memory_context=memory_context,
            summary=summary,
            episodic_context=episodic_context,
            history=history,
            extracted_entities=extracted_entities,
            query_intent=query_intent,
            media_type_hint=media_type_hint,
            filters=filters,
        )
        return infra_result, list(infra_runs)

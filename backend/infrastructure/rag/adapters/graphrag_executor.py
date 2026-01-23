from __future__ import annotations

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
        memory_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> tuple[RagRunResult, list[RagRunResult]]:
        infra_result, infra_runs = await self._rag_manager.run_plan_blocking(
            plan=plan,
            message=message,
            session_id=session_id,
            kb_prefix=kb_prefix,
            debug=debug,
            memory_context=memory_context,
            history=history,
        )
        return infra_result, list(infra_runs)

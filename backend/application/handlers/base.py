from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from application.ports.rag_executor_port import RAGExecutorPort
from application.ports.rag_stream_executor_port import RAGStreamExecutorPort
from domain.chat.entities.rag_run import RagRunSpec


class KnowledgeBaseHandler(ABC):
    name: str
    kb_prefix: str

    def __init__(
        self,
        *,
        executor: RAGExecutorPort,
        stream_executor: RAGStreamExecutorPort,
    ) -> None:
        self._executor = executor
        self._stream_executor = stream_executor

    def preprocess(self, message: str) -> str:
        return message

    @abstractmethod
    def build_plan(self, *, message: str, agent_type: str) -> list[RagRunSpec]:
        raise NotImplementedError

    async def process(
        self,
        *,
        message: str,
        session_id: str,
        agent_type: str,
        debug: bool,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        processed = self.preprocess(message)
        plan = self.build_plan(message=processed, agent_type=agent_type)
        aggregated, runs = await self._executor.run(
            plan=plan,
            message=processed,
            session_id=session_id,
            kb_prefix=self.kb_prefix,
            debug=debug,
            memory_context=memory_context,
            summary=summary,
            episodic_context=episodic_context,
            history=history,
        )
        response: dict[str, Any] = {"answer": aggregated.answer}
        if aggregated.reference:
            response["reference"] = aggregated.reference
        if aggregated.retrieval_results is not None:
            response["retrieval_results"] = aggregated.retrieval_results
        if debug:
            response["rag_runs"] = [run.__dict__ for run in runs]
        return response

    async def process_stream(
        self,
        *,
        message: str,
        session_id: str,
        agent_type: str,
        debug: bool,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        processed = self.preprocess(message)
        plan = self.build_plan(message=processed, agent_type=agent_type)
        async for event in self._stream_executor.stream(
            plan=plan,
            message=processed,
            session_id=session_id,
            kb_prefix=self.kb_prefix,
            debug=debug,
            memory_context=memory_context,
            summary=summary,
            episodic_context=episodic_context,
            history=history,
            **kwargs,
        ):
            yield event

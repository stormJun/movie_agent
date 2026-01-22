from __future__ import annotations

from application.handlers.base import KnowledgeBaseHandler
from application.ports.rag_executor_port import RAGExecutorPort
from application.ports.rag_stream_executor_port import RAGStreamExecutorPort
from domain.chat.entities.rag_run import RagRunSpec
from domain.knowledge_bases.edu.planner import EduKnowledgeBasePlanner


class EduKnowledgeBaseHandler(KnowledgeBaseHandler):
    name = "edu"
    kb_prefix = "edu"

    def __init__(
        self,
        *,
        executor: RAGExecutorPort,
        stream_executor: RAGStreamExecutorPort,
        planner: EduKnowledgeBasePlanner | None = None,
    ) -> None:
        super().__init__(executor=executor, stream_executor=stream_executor)
        self._planner = planner or EduKnowledgeBasePlanner()

    def build_plan(self, *, message: str, agent_type: str) -> list[RagRunSpec]:
        return self._planner.build_plan(message=message, agent_type=agent_type)

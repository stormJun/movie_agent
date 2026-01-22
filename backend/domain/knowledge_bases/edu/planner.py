from __future__ import annotations

from domain.chat.entities.rag_run import RagRunSpec


class EduKnowledgeBasePlanner:
    def build_plan(self, *, message: str, agent_type: str) -> list[RagRunSpec]:
        return [RagRunSpec(agent_type=agent_type, timeout_s=30.0)]

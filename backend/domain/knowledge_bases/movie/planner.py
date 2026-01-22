from __future__ import annotations

from domain.chat.entities.rag_run import RagRunSpec


class MovieKnowledgeBasePlanner:
    PARALLEL_TRIGGERS = (
        "recommend",
        "compare",
        "top",
        "list",
        "summary",
        "difference",
    )

    def build_plan(self, *, message: str, agent_type: str) -> list[RagRunSpec]:
        if self._should_use_parallel(message):
            return [
                RagRunSpec(agent_type="hybrid_agent", timeout_s=25.0),
                RagRunSpec(agent_type="graph_agent", timeout_s=25.0),
                RagRunSpec(agent_type="naive_rag_agent", timeout_s=25.0),
                RagRunSpec(agent_type="fusion_agent", timeout_s=60.0),
            ]
        return [RagRunSpec(agent_type=agent_type, timeout_s=30.0)]

    def _should_use_parallel(self, message: str) -> bool:
        text = message.lower()
        return any(trigger in text for trigger in self.PARALLEL_TRIGGERS)

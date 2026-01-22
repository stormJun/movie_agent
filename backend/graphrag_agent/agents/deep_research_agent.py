from __future__ import annotations

from typing import Any, Dict

from graphrag_agent.agents.base import BaseAgent
from graphrag_agent.search.tool.hybrid_tool import HybridSearchTool


class DeepResearchAgent(BaseAgent):
    """DeepResearch retrieval-only Agent (v3).

    In v3, "deep research" no longer runs multi-round thinking/LLM chains inside the Agent.
    This Agent is kept as a retrieval strategy wrapper.
    """

    def __init__(
        self,
        use_deeper_tool: bool = True,
        kb_prefix: str | None = None,
        agent_mode: str = "retrieve_only",
    ) -> None:
        _ = use_deeper_tool  # legacy knob; kept for backward compatibility
        self.retrieval_tool = HybridSearchTool(kb_prefix=kb_prefix, use_llm=False)
        super().__init__(
            kb_prefix=kb_prefix,
            agent_mode=agent_mode,
        )

    def retrieve_with_trace(self, query: str, thread_id: str = "default") -> Dict[str, Any]:
        _ = thread_id
        payload = self.retrieval_tool.retrieve_only({"query": query})
        if not isinstance(payload, dict):
            return {
                "context": "",
                "retrieval_results": [],
                "reference": {},
                "error": "unexpected retrieve_only payload",
            }

        context = str(payload.get("context") or "").strip()
        retrieval_results = payload.get("retrieval_results")
        reference = payload.get("reference")

        return {
            "context": context,
            "retrieval_results": retrieval_results if isinstance(retrieval_results, list) else [],
            "reference": reference if isinstance(reference, dict) else {},
        }

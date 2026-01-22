from __future__ import annotations

from typing import Any, Dict

from graphrag_agent.agents.base import BaseAgent
from graphrag_agent.search.tool.naive_search_tool import NaiveSearchTool


class NaiveRagAgent(BaseAgent):
    """Naive vector retrieval-only Agent (v3)."""

    def __init__(self, kb_prefix: str | None = None, agent_mode: str = "retrieve_only"):
        self.search_tool = NaiveSearchTool(kb_prefix=kb_prefix)
        super().__init__(kb_prefix=kb_prefix, agent_mode=agent_mode)

    def retrieve_with_trace(self, query: str, thread_id: str = "default") -> Dict[str, Any]:
        _ = thread_id
        payload = self.search_tool.retrieve_only({"query": query})
        if not isinstance(payload, dict):
            return {
                "context": "",
                "retrieval_results": [],
                "reference": {},
                "error": "unexpected retrieve_only payload",
            }

        context = str(payload.get("context") or "").strip()
        return {
            "context": context,
            "retrieval_results": payload.get("retrieval_results", []) or [],
            "reference": payload.get("reference", {}) or {},
        }

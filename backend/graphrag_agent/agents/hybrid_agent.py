from __future__ import annotations

from typing import Any, Dict

from graphrag_agent.agents.base import BaseAgent
from graphrag_agent.search.tool.hybrid_tool import HybridSearchTool


class HybridAgent(BaseAgent):
    """Hybrid retrieval-only Agent (v3)."""

    def __init__(self, kb_prefix: str | None = None, agent_mode: str = "retrieve_only"):
        self.search_tool = HybridSearchTool(kb_prefix=kb_prefix)
        super().__init__(kb_prefix=kb_prefix, agent_mode=agent_mode)

    def retrieve_with_trace(self, query: str, thread_id: str = "default") -> Dict[str, Any]:
        _ = thread_id
        import time

        execution_log = []

        keywords = self.search_tool.extract_keywords(query)
        if not isinstance(keywords, dict):
            keywords = {}

        payload = self.search_tool.retrieve_only(
            {
                "query": query,
                "low_level_keywords": keywords.get("low_level", []) or [],
                "high_level_keywords": keywords.get("high_level", []) or [],
            }
        )
        if not isinstance(payload, dict):
            return {
                "context": "",
                "retrieval_results": [],
                "reference": {},
                "error": "unexpected retrieve_only payload",
            }

        # Collect hybrid tool's execution_log
        if hasattr(self.search_tool, "execution_log"):
            tool_log = list(self.search_tool.execution_log) if self.search_tool.execution_log else []
            execution_log.extend(tool_log)

        low = str(payload.get("low_level_content") or "").strip()
        high = str(payload.get("high_level_content") or "").strip()
        context = "\n\n".join([p for p in (low, high) if p]).strip()
        return {
            "context": context,
            "retrieval_results": payload.get("retrieval_results", []) or [],
            "reference": payload.get("reference", {}) or {},
            "execution_log": execution_log,
        }

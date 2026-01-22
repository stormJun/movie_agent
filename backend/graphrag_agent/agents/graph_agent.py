from __future__ import annotations

from typing import Any, Dict, List

from graphrag_agent.agents.base import BaseAgent

_INSTALL_HINT = (
    "Optional dependencies required. "
    "Install one of: `pip install 'graphrag-agent[search,langchain,neo4j]'` or "
    "`pip install 'graphrag-agent[full]'`."
)

try:
    from graphrag_agent.search.retrieval_adapter import (
        results_from_documents,
        results_to_payload,
    )
    from graphrag_agent.search.tool.global_search_tool import GlobalSearchTool
    from graphrag_agent.search.tool.local_search_tool import LocalSearchTool
except ModuleNotFoundError as exc:
    # Do not wrap internal missing modules; that indicates a packaging bug.
    if exc.name and exc.name.startswith("graphrag_agent"):
        raise
    raise ImportError(f"{_INSTALL_HINT} Missing: {exc.name}") from exc


class GraphAgent(BaseAgent):
    """GraphRAG retrieval-only Agent (v3).

    Responsibilities:
    - run local/global retrieval
    - return structured evidence (`context` + `retrieval_results` + `reference`)

    Non-responsibilities (removed in v3):
    - answer generation, streaming, LangGraph execution/checkpointer
    """

    def __init__(self, kb_prefix: str | None = None, agent_mode: str = "retrieve_only"):
        self.local_tool = LocalSearchTool(kb_prefix=kb_prefix)
        self.global_tool = GlobalSearchTool(kb_prefix=kb_prefix)
        super().__init__(kb_prefix=kb_prefix, agent_mode=agent_mode)

    def _build_reference_from_retrieval_payload(
        self, retrieval_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        chunks: set[str] = set()
        entities: set[str] = set()
        relationships: set[str] = set()

        for item in retrieval_results or []:
            metadata = item.get("metadata") or {}
            source_type = str(metadata.get("source_type") or "").strip()
            source_id = str(metadata.get("source_id") or "").strip()
            if not source_type or not source_id:
                continue
            if source_type == "chunk":
                chunks.add(source_id)
            elif source_type == "entity":
                entities.add(source_id)
            elif source_type == "relationship":
                relationships.add(source_id)

        return {
            "chunks": [{"chunk_id": cid} for cid in sorted(chunks)],
            "entities": [{"id": eid} for eid in sorted(entities)],
            "relationships": [{"id": rid} for rid in sorted(relationships)],
        }

    def retrieve_with_trace(self, query: str, thread_id: str = "default") -> Dict[str, Any]:
        _ = thread_id

        docs = []
        retriever = getattr(self.local_tool, "retriever", None)
        if retriever is not None:
            if hasattr(retriever, "get_relevant_documents"):
                docs = retriever.get_relevant_documents(query)
            elif hasattr(retriever, "invoke"):
                docs = retriever.invoke(query)

        local_payload = results_to_payload(results_from_documents(docs, source="local_search"))
        local_context_parts: List[str] = []
        for doc in docs or []:
            text = getattr(doc, "page_content", "") or ""
            if text:
                local_context_parts.append(text)
        local_context = "\n\n---\n\n".join(local_context_parts).strip()

        global_payload = self.global_tool.retrieve_only({"query": query})
        global_context = str(global_payload.get("context") or "").strip()
        global_retrieval = global_payload.get("retrieval_results", [])

        # Merge & dedupe by (source_id, granularity) and keep max score
        merged: Dict[tuple[str, str], Dict[str, Any]] = {}
        for group in (local_payload, global_retrieval):
            if not isinstance(group, list):
                continue
            for item in group:
                if not isinstance(item, dict):
                    continue
                metadata = item.get("metadata") or {}
                source_id = str(metadata.get("source_id") or "").strip()
                granularity = str(item.get("granularity") or "").strip()
                if not source_id or not granularity:
                    continue
                key = (source_id, granularity)
                existing = merged.get(key)
                if existing is None:
                    merged[key] = item
                    continue
                try:
                    score_new = float(item.get("score", 0.0))
                    score_old = float(existing.get("score", 0.0))
                except Exception:
                    score_new = 0.0
                    score_old = 0.0
                if score_new > score_old:
                    merged[key] = item

        retrieval_results = list(merged.values())
        reference = self._build_reference_from_retrieval_payload(retrieval_results)

        context = "\n\n".join([p for p in (local_context, global_context) if p]).strip()
        return {
            "context": context,
            "retrieval_results": retrieval_results,
            "reference": reference,
        }

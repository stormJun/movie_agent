from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool

from graphrag_agent.ports.models import get_embeddings_model, get_llm_model
from graphrag_agent.ports.neo4jdb import get_graph
from graphrag_agent.search.retrieval_adapter import (
    merge_retrieval_results,
    results_from_documents,
    results_from_entities,
    results_from_relationships,
    results_to_payload,
)
from graphrag_agent.search.tool.reasoning.chain_of_exploration import ChainOfExplorationSearcher


class ChainOfExplorationTool:
    """将ChainOfExplorationSearcher封装为LangChain Tool。"""

    def __init__(self, max_steps: int = 5, exploration_width: int = 3, kb_prefix: str | None = None):
        self.max_steps = max_steps
        self.exploration_width = exploration_width
        self.llm = get_llm_model()
        self.embeddings = get_embeddings_model()
        self.graph = get_graph()
        self.searcher = ChainOfExplorationSearcher(
            self.graph, self.llm, self.embeddings, kb_prefix=kb_prefix
        )

    def _normalize_input(self, query_input: Any) -> Dict[str, Any]:
        if isinstance(query_input, dict):
            return dict(query_input)
        return {"query": str(query_input)}

    def explore(
        self,
        query: str,
        *,
        start_entities: Optional[List[str]] = None,
        max_steps: Optional[int] = None,
        exploration_width: Optional[int] = None,
    ) -> Dict[str, Any]:
        """执行图谱探索并返回统一结构。"""
        if not query:
            raise ValueError("query不能为空")

        start_entities = start_entities or []
        results = self.searcher.explore(
            query=query,
            starting_entities=start_entities,
            max_steps=max_steps or self.max_steps,
            exploration_width=exploration_width or self.exploration_width,
        )

        entity_results = results_from_entities(
            results.get("entities", []), source="chain_exploration"
        )
        relation_results = results_from_relationships(
            results.get("relationships", []), source="chain_exploration"
        )
        content_results = results_from_documents(
            results.get("content", []),
            source="chain_exploration",
            granularity="Chunk",
        )

        merged_results = merge_retrieval_results(
            entity_results, relation_results, content_results
        )

        summary = {
            "exploration_path": results.get("exploration_path", []),
            "statistics": results.get("statistics", {}),
            "communities": results.get("communities", []),
        }

        return {
            "query": query,
            "start_entities": start_entities,
            "summary": summary,
            "raw_result": results,
            "retrieval_results": results_to_payload(merged_results),
        }

    def retrieve_only(self, query_input: Any) -> Dict[str, Any]:
        """
        仅做探索/检索，返回标准化检索结果（不生成最终答案）。

        Returns:
          {
            "query": str,
            "context": str,
            "summary": Dict[str, Any],
            "retrieval_results": List[Dict],
          }
        """
        payload = self._normalize_input(query_input)
        query = str(payload.get("query") or payload.get("input") or "").strip()
        if not query:
            raise ValueError("query不能为空")

        start_entities = payload.get("start_entities") or payload.get("entities") or []
        if not isinstance(start_entities, list):
            start_entities = []

        result = self.explore(
            query,
            start_entities=[str(e) for e in start_entities if e],
            max_steps=payload.get("max_steps"),
            exploration_width=payload.get("exploration_width"),
        )

        retrieval_results = result.get("retrieval_results")
        retrieval_results = retrieval_results if isinstance(retrieval_results, list) else []

        # Build a lightweight context from evidence snippets so the RAG executor can synthesize.
        snippets: list[str] = []
        for item in retrieval_results:
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence") or item.get("text") or item.get("content")
            if isinstance(evidence, str) and evidence.strip():
                snippets.append(evidence.strip())
        context = "\n\n---\n\n".join(snippets).strip()

        return {
            "query": query,
            "context": context,
            "summary": result.get("summary") if isinstance(result.get("summary"), dict) else {},
            "retrieval_results": retrieval_results,
        }

    def get_tool(self) -> BaseTool:
        """返回LangChain兼容的探索工具。"""

        chain_tool = self

        class ChainExplorationLC(BaseTool):
            name: str = "chain_of_exploration"
            description: str = (
                "图谱路径探索工具：给定查询与起始实体，沿关系链探索相关实体与证据。"
                "返回结构化的探索摘要与标准化检索结果。"
            )

            def _run(
                self_tool, query: Any, start_entities: Optional[List[str]] = None, **kwargs: Any
            ) -> Dict[str, Any]:
                if isinstance(query, dict):
                    # 支持传入完整payload
                    payload = query
                    query_text = payload.get("query", "")
                    start = payload.get("start_entities") or payload.get("entities") or []
                    return chain_tool.explore(
                        query_text,
                        start_entities=start,
                        max_steps=payload.get("max_steps"),
                        exploration_width=payload.get("exploration_width"),
                    )
                return chain_tool.explore(
                    str(query),
                    start_entities=start_entities,
                    max_steps=kwargs.get("max_steps"),
                    exploration_width=kwargs.get("exploration_width"),
                )

            def _arun(self_tool, *args: Any, **kwargs: Any) -> Any:
                raise NotImplementedError("异步执行未实现")

        return ChainExplorationLC()

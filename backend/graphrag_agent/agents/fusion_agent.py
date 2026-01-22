from __future__ import annotations

from typing import Any, Dict

from graphrag_agent.agents.base import BaseAgent
from graphrag_agent.agents.multi_agent.executor.retrieval_executor import (
    RetrievalExecutor,
)
from graphrag_agent.agents.multi_agent.executor.worker_coordinator import WorkerCoordinator
from graphrag_agent.agents.multi_agent.integration.legacy_facade import MultiAgentFacade
from graphrag_agent.agents.multi_agent.integration.multi_agent_factory import (
    MultiAgentFactory,
)
from graphrag_agent.agents.multi_agent.orchestrator import OrchestratorConfig
from graphrag_agent.agents.multi_agent.planner.retrieve_only_planner import (
    RetrieveOnlyPlanner,
)
from graphrag_agent.agents.multi_agent.reporter.noop_reporter import NoopReporter
from graphrag_agent.search.tool_registry import EXTRA_TOOL_FACTORIES, TOOL_REGISTRY


class FusionGraphRAGAgent(BaseAgent):
    """Fusion (multi-agent stack) retrieval-only Agent (v3).

    Notes:
    - In v3 we only keep the "retrieve_only" capability.
    - Planning is deterministic (RetrieveOnlyPlanner) and report generation is disabled.
    """

    def __init__(
        self,
        kb_prefix: str | None = None,
        agent_mode: str = "retrieve_only",
    ) -> None:
        # Unify with other agents: inherit shared logging/metrics behavior from BaseAgent.
        # Fusion retrieval itself does not require embeddings from ports, so disable
        # eager embeddings resolution to keep tests light.
        super().__init__(
            kb_prefix=kb_prefix,
            agent_mode=agent_mode,
            enable_embeddings=False,
        )
        self.multi_agent = MultiAgentFacade(
            bundle=self._build_bundle(),
        )

    @staticmethod
    def _build_tool_registry_with_kb_prefix(
        kb_prefix: str, *, prefer_retrieve_only: bool = False
    ) -> Dict[str, Any]:
        """
        multi_agent 的 TOOL_REGISTRY 是“零参工厂”，这里注入 kb_prefix 以确保检索命中正确 KB。
        """

        injected: Dict[str, Any] = {}
        for tool_name, factory in TOOL_REGISTRY.items():
            def _make_factory(_factory=factory):  # type: ignore[misc]
                def _create():
                    # retrieve_only 下尽量禁用工具侧 LLM 行为（如果工具支持 use_llm 参数）
                    kwargs: Dict[str, Any] = {"kb_prefix": kb_prefix}
                    if prefer_retrieve_only:
                        kwargs["use_llm"] = False
                    try:
                        return _factory(**kwargs)
                    except TypeError:
                        try:
                            return _factory(kb_prefix=kb_prefix)
                        except TypeError:
                            return _factory()

                return _create

            injected[tool_name] = _make_factory()
        return injected

    def _build_bundle(self):
        tool_registry = self._build_tool_registry_with_kb_prefix(
            self.kb_prefix, prefer_retrieve_only=True
        )
        retrieval_executor = RetrievalExecutor(
            tool_registry=tool_registry,
            extra_tool_factories=EXTRA_TOOL_FACTORIES,
            prefer_retrieve_only=True,
        )
        worker = WorkerCoordinator(executors=[retrieval_executor])

        planner = RetrieveOnlyPlanner(task_type="hybrid_search")
        reporter = NoopReporter()
        orchestrator_config = OrchestratorConfig(auto_generate_report=False)
        return MultiAgentFactory.create_default_bundle(
            planner=planner,
            worker=worker,
            reporter=reporter,
            orchestrator_config=orchestrator_config,
        )

    @staticmethod
    def _build_reference_from_retrieval_payload(
        retrieval_results: list[dict[str, Any]] | None,
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
        payload = self.multi_agent.process_query(query.strip(), report_type=None)
        execution_records = payload.get("execution_records", []) or []

        retrieval_results: list[dict[str, Any]] = []
        context_parts: list[str] = []

        for record in execution_records:
            tool_calls = (record.get("tool_calls") or []) if isinstance(record, dict) else []
            for call in tool_calls:
                result = call.get("result") if isinstance(call, dict) else None
                if isinstance(result, dict):
                    rr = result.get("retrieval_results")
                    if isinstance(rr, list):
                        for item in rr:
                            if isinstance(item, dict):
                                retrieval_results.append(item)

        for item in retrieval_results:
            evidence = item.get("evidence")
            if isinstance(evidence, str) and evidence.strip():
                context_parts.append(evidence.strip())

        context = "\n\n---\n\n".join(context_parts[:30]).strip()
        reference = self._build_reference_from_retrieval_payload(retrieval_results)

        return {
            "context": context,
            "retrieval_results": retrieval_results,
            "reference": reference,
        }

    def close(self) -> None:
        # multi_agent stack currently holds no external handles here
        return None

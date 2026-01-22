import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest
from unittest.mock import patch

from graphrag_agent.agents.fusion_agent import FusionGraphRAGAgent
from graphrag_agent.agents.multi_agent.executor.retrieval_executor import (
    RetrievalExecutor,
)
from graphrag_agent.agents.multi_agent.planner.retrieve_only_planner import (
    RetrieveOnlyPlanner,
)


class TestFusionAgentRetrieveOnly(unittest.TestCase):
    def test_retrieve_only_disables_report_and_non_retrieval_execs(self) -> None:
        agent = FusionGraphRAGAgent(agent_mode="retrieve_only", kb_prefix="movie")
        bundle = agent.multi_agent.bundle

        self.assertFalse(bundle.orchestrator.config.auto_generate_report)
        self.assertIsInstance(bundle.planner, RetrieveOnlyPlanner)
        self.assertEqual(len(bundle.worker.executors), 1)
        self.assertIsInstance(bundle.worker.executors[0], RetrievalExecutor)

        # v3 strict: legacy ask/ask_with_trace are physically removed.
        self.assertFalse(hasattr(agent, "ask"))
        self.assertFalse(hasattr(agent, "ask_with_trace"))

    def test_tool_registry_passes_use_llm_false_in_retrieve_only(self) -> None:
        calls = []

        def _dummy_factory(*args, **kwargs):
            calls.append(kwargs)
            return object()

        with patch("graphrag_agent.agents.fusion_agent.TOOL_REGISTRY", {"hybrid_search": _dummy_factory}):
            registry = FusionGraphRAGAgent._build_tool_registry_with_kb_prefix(
                "movie",
                prefer_retrieve_only=True,
            )
            registry["hybrid_search"]()

        self.assertTrue(calls)
        self.assertEqual(calls[0].get("kb_prefix"), "movie")
        self.assertEqual(calls[0].get("use_llm"), False)

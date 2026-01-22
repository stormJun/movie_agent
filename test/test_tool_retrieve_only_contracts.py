import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest
from typing import Any
from unittest.mock import patch


class TestToolRetrieveOnlyContracts(unittest.TestCase):
    def test_chain_exploration_tool_has_retrieve_only(self) -> None:
        from graphrag_agent.search.tool.chain_exploration_tool import (
            ChainOfExplorationTool,
        )

        tool = ChainOfExplorationTool.__new__(ChainOfExplorationTool)

        def _fake_explore(*args: Any, **kwargs: Any) -> dict:
            return {
                "summary": {"exploration_path": ["a->b"]},
                "retrieval_results": [
                    {"score": 1.0, "evidence": "ev1"},
                    {"score": 0.5, "evidence": "ev2"},
                ],
            }

        tool.explore = _fake_explore  # type: ignore[assignment]

        payload = tool.retrieve_only({"query": "q", "start_entities": ["a"]})
        self.assertIn("context", payload)
        self.assertIn("retrieval_results", payload)
        self.assertIsInstance(payload["retrieval_results"], list)

    def test_hypothesis_tool_retrieve_only(self) -> None:
        from graphrag_agent.search.tool.hypothesis_tool import (
            HypothesisGeneratorTool,
        )

        tool = HypothesisGeneratorTool.__new__(HypothesisGeneratorTool)
        tool.generate = lambda q: ["h1", "h2"]  # type: ignore[assignment]

        payload = tool.retrieve_only({"query": "q"})
        self.assertEqual(payload["hypotheses"], ["h1", "h2"])
        self.assertEqual(payload["retrieval_results"], [])

    def test_validation_tool_retrieve_only(self) -> None:
        from graphrag_agent.search.tool.validation_tool import AnswerValidationTool

        tool = AnswerValidationTool.__new__(AnswerValidationTool)
        tool.validate = lambda q, a, reference_keywords=None: {  # type: ignore[assignment]
            "query": q,
            "answer": a,
            "validation": {"ok": True},
        }

        payload = tool.retrieve_only({"query": "q", "answer": "a"})
        self.assertEqual(payload["retrieval_results"], [])
        self.assertEqual(payload["validation"], {"ok": True})


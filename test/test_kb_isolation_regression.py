import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

from infrastructure.rag.rag_manager import RagManager
from infrastructure.rag.specs import RagRunSpec


class _StubAgent:
    def __init__(self, *, context: str):
        self._context = context

    def retrieve_with_trace(self, message: str, thread_id: str = "default") -> Dict[str, Any]:
        return {
            "context": self._context,
            "retrieval_results": [{"score": 1.0, "granularity": "Chunk", "metadata": {"source_id": "s1"}}],
            "reference": {},
        }


class TestKBIsolationRegression(unittest.IsolatedAsyncioTestCase):
    async def test_kb_prefix_is_forwarded_when_no_worker_name(self) -> None:
        mgr = RagManager()
        calls: List[Tuple[str, str]] = []

        def _get_agent(agent_type: str, *args: Any, **kwargs: Any) -> _StubAgent:
            calls.append((agent_type, str(kwargs.get("kb_prefix") or "")))
            return _StubAgent(context=f"ctx:{kwargs.get('kb_prefix')}")

        with patch("infrastructure.rag.rag_manager.agent_manager.get_agent", side_effect=_get_agent):
            await mgr.run_retrieval_for_spec(
                spec=RagRunSpec(agent_type="hybrid_agent", timeout_s=0.2),
                message="q",
                session_id="s1",
                kb_prefix="movie",
                debug=False,
            )
            await mgr.run_retrieval_for_spec(
                spec=RagRunSpec(agent_type="hybrid_agent", timeout_s=0.2),
                message="q",
                session_id="s1",
                kb_prefix="edu",
                debug=False,
            )

        self.assertEqual(calls, [("hybrid_agent", "movie"), ("hybrid_agent", "edu")])

    async def test_worker_name_overrides_kb_prefix_for_isolation(self) -> None:
        mgr = RagManager()
        calls: List[Tuple[str, str]] = []

        def _get_agent(agent_type: str, *args: Any, **kwargs: Any) -> _StubAgent:
            calls.append((agent_type, str(kwargs.get("kb_prefix") or "")))
            return _StubAgent(context=f"ctx:{kwargs.get('kb_prefix')}")

        # Note: run_retrieval_for_spec should honor spec.worker_name ("movie:...") even if kb_prefix arg is "edu".
        with patch("infrastructure.agents.rag_factory.rag_agent_manager.get_agent", side_effect=_get_agent):
            result = await mgr.run_retrieval_for_spec(
                spec=RagRunSpec(agent_type="hybrid_agent", worker_name="movie:hybrid_agent", timeout_s=0.2),
                message="q",
                session_id="s1",
                kb_prefix="edu",
                debug=False,
            )

        self.assertEqual(calls, [("hybrid_agent", "movie")])
        self.assertEqual(result.agent_type, "hybrid_agent")


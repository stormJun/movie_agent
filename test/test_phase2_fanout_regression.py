import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import asyncio
import time
import unittest
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import patch

from infrastructure.rag.rag_manager import RagManager
from infrastructure.rag.specs import RagRunSpec
from infrastructure.streaming.chat_stream_executor import ChatStreamExecutor


class _StubAgent:
    def __init__(self, *, result: Dict[str, Any] | None = None, delay_s: float = 0.0, raise_exc: bool = False):
        self._result = result or {}
        self._delay_s = delay_s
        self._raise_exc = raise_exc

    def retrieve_with_trace(self, message: str, thread_id: str = "default") -> Dict[str, Any]:
        if self._delay_s:
            time.sleep(self._delay_s)
        if self._raise_exc:
            raise RuntimeError("boom")
        return dict(self._result)


async def _fake_answer_stream(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    **_: Any,
) -> AsyncGenerator[str, None]:
    # Minimal deterministic stream for tests (no external LLM).
    yield f"Q={question}\n"
    yield f"CTX={context}\n"


class TestPhase2FanoutRegression(unittest.IsolatedAsyncioTestCase):
    async def test_fanout_failure_isolated_and_stream_completes(self) -> None:
        mgr = RagManager()
        executor = ChatStreamExecutor(rag_manager=mgr)
        plan = [
            RagRunSpec(agent_type="a", timeout_s=0.2),
            RagRunSpec(agent_type="b", timeout_s=0.2),
        ]

        def _get_agent(agent_type: str, *args: Any, **kwargs: Any) -> _StubAgent:
            if agent_type == "a":
                return _StubAgent(result={"context": "ctx-a", "retrieval_results": [{"score": 1.0}]})
            return _StubAgent(raise_exc=True)

        events: List[dict[str, Any]] = []
        with patch("infrastructure.rag.rag_manager.agent_manager.get_agent", side_effect=_get_agent):
            with patch(
                "infrastructure.streaming.chat_stream_executor.generate_rag_answer_stream",
                side_effect=_fake_answer_stream,
            ):
                async for ev in executor.stream(
                    plan=plan, message="hello", session_id="s1", kb_prefix="movie", debug=False
                ):
                    events.append(ev)

        # Ensure we emit retrieval progress for both agents, then generation, then done.
        stages = [e.get("content", {}).get("stage") for e in events if e.get("status") == "progress"]
        self.assertIn("retrieval", stages)
        self.assertIn("generation", stages)
        self.assertEqual(events[-1], {"status": "done"})

        # Ensure at least one retrieval progress event carries an error from the failed agent.
        retrieval_errors = [
            e.get("content", {}).get("error")
            for e in events
            if e.get("status") == "progress" and e.get("content", {}).get("stage") == "retrieval"
        ]
        self.assertTrue(any(err for err in retrieval_errors))

        # Ensure token stream happens even when one retrieval failed.
        tokens = [e.get("content") for e in events if e.get("status") == "token"]
        self.assertTrue(tokens)

    async def test_fanout_timeout_degrades_and_stream_completes(self) -> None:
        mgr = RagManager()
        executor = ChatStreamExecutor(rag_manager=mgr)
        plan = [
            RagRunSpec(agent_type="fast", timeout_s=0.2),
            RagRunSpec(agent_type="slow", timeout_s=0.01),
        ]

        def _get_agent(agent_type: str, *args: Any, **kwargs: Any) -> _StubAgent:
            if agent_type == "fast":
                return _StubAgent(result={"context": "ctx-fast", "retrieval_results": [{"score": 1.0}]})
            return _StubAgent(result={"context": "ctx-slow", "retrieval_results": [{"score": 0.1}]}, delay_s=0.1)

        events: List[dict[str, Any]] = []
        with patch("infrastructure.rag.rag_manager.agent_manager.get_agent", side_effect=_get_agent):
            with patch(
                "infrastructure.streaming.chat_stream_executor.generate_rag_answer_stream",
                side_effect=_fake_answer_stream,
            ):
                async for ev in executor.stream(
                    plan=plan, message="hello", session_id="s1", kb_prefix="movie", debug=False
                ):
                    events.append(ev)

        self.assertEqual(events[-1], {"status": "done"})

        retrieval_errors = [
            e.get("content", {}).get("error")
            for e in events
            if e.get("status") == "progress" and e.get("content", {}).get("stage") == "retrieval"
        ]
        self.assertTrue(any(isinstance(err, str) and "timeout" in err for err in retrieval_errors))

    async def test_run_plan_retrieval_context_excludes_failed_runs(self) -> None:
        mgr = RagManager()
        plan = [
            RagRunSpec(agent_type="ok", timeout_s=0.2),
            RagRunSpec(agent_type="bad", timeout_s=0.2),
        ]

        def _get_agent(agent_type: str, *args: Any, **kwargs: Any) -> _StubAgent:
            if agent_type == "ok":
                return _StubAgent(result={"context": "ctx-ok", "retrieval_results": [{"score": 1.0}]})
            return _StubAgent(raise_exc=True)

        with patch("infrastructure.rag.rag_manager.agent_manager.get_agent", side_effect=_get_agent):
            runs, aggregated, combined_context = await mgr.run_plan_retrieval(
                plan=plan,
                message="hello",
                session_id="s1",
                kb_prefix="movie",
                debug=False,
            )

        self.assertEqual(len(runs), 2)
        self.assertIn("ctx-ok", combined_context)
        # Failed run should not contribute to combined_context.
        self.assertNotIn("ctx-bad", combined_context)
        # Aggregation should still succeed (even if one run errored).
        self.assertIsNotNone(aggregated)

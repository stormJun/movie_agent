#!/usr/bin/env python3
"""
Lightweight Phase 2 performance sampling.

This is intentionally "manual" (not a CI assertion): real latency depends on Neo4j/LLM.
We provide a stubbed mode to measure orchestration overhead deterministically.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from infrastructure.rag.rag_manager import RagManager
from infrastructure.rag.specs import RagRunSpec


class _StubAgent:
    def __init__(self, *, context: str, delay_s: float) -> None:
        self._context = context
        self._delay_s = delay_s

    def retrieve_with_trace(self, message: str, thread_id: str = "default") -> Dict[str, Any]:
        if self._delay_s:
            time.sleep(self._delay_s)
        return {
            "context": self._context,
            "retrieval_results": [
                {"score": 1.0, "granularity": "Chunk", "metadata": {"source_id": "s1"}, "evidence": "ev"}
            ],
            "reference": {},
        }


async def _fake_answer_stream(*, question: str, context: str, tokens: int) -> AsyncGenerator[str, None]:
    for _ in range(tokens):
        yield "x"


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = int(round((p / 100.0) * (len(values) - 1)))
    return values[max(0, min(idx, len(values) - 1))]


async def _run_once(*, fanout: int, retrieval_delay_s: float, tokens: int) -> float:
    mgr = RagManager()
    plan = [RagRunSpec(agent_type=f"agent{i}", timeout_s=max(0.05, retrieval_delay_s * 2)) for i in range(fanout)]

    def _get_agent(agent_type: str, *args: Any, **kwargs: Any) -> _StubAgent:
        return _StubAgent(context=f"ctx:{agent_type}", delay_s=retrieval_delay_s)

    start = time.perf_counter()

    with patch("infrastructure.rag.rag_manager.agent_manager.get_agent", side_effect=_get_agent):
        with patch(
            "infrastructure.rag.rag_manager.generate_rag_answer_stream",
            side_effect=lambda **kw: _fake_answer_stream(tokens=tokens, **kw),
        ):
            async for _ in mgr.run_plan_stream(
                plan=plan,
                message="hello",
                session_id="bench",
                kb_prefix="movie",
                debug=False,
            ):
                pass

    return time.perf_counter() - start


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--fanout", type=int, default=3)
    parser.add_argument("--retrieval-delay-s", type=float, default=0.02)
    parser.add_argument("--tokens", type=int, default=128)
    args = parser.parse_args()

    durations: List[float] = []
    for _ in range(max(1, args.iterations)):
        durations.append(
            await _run_once(
                fanout=max(0, args.fanout),
                retrieval_delay_s=max(0.0, args.retrieval_delay_s),
                tokens=max(0, args.tokens),
            )
        )

    p50 = _percentile(durations, 50)
    p95 = _percentile(durations, 95)
    p99 = _percentile(durations, 99)
    mean = statistics.mean(durations)
    print(
        "Phase2 bench (stubbed): "
        f"iterations={len(durations)} fanout={args.fanout} retrieval_delay_s={args.retrieval_delay_s} tokens={args.tokens}\n"
        f"p50={p50:.4f}s p95={p95:.4f}s p99={p99:.4f}s mean={mean:.4f}s"
    )


if __name__ == "__main__":
    asyncio.run(main())

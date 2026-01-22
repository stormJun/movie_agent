import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest

from domain.chat.entities.rag_run import RagRunResult
from domain.chat.services.rag_aggregator import aggregate_run_results


class TestRagLayerAggregator(unittest.TestCase):
    def test_picks_preferred_agent_type(self):
        results = [
            RagRunResult(agent_type="graph_agent", answer="不知道"),
            RagRunResult(agent_type="hybrid_agent", answer="答案 A"),
            RagRunResult(agent_type="naive_rag_agent", answer="答案 B"),
        ]
        aggregated = aggregate_run_results(results=results)
        self.assertEqual(aggregated.agent_type, "hybrid_agent")
        self.assertEqual(aggregated.answer, "答案 A")

    def test_merges_context(self):
        results = [
            RagRunResult(agent_type="hybrid_agent", context="ctx-a", answer=""),
            RagRunResult(agent_type="graph_agent", context="ctx-b", answer=""),
        ]
        aggregated = aggregate_run_results(results=results)
        self.assertIn("### hybrid_agent", aggregated.context or "")
        self.assertIn("ctx-a", aggregated.context or "")
        self.assertIn("### graph_agent", aggregated.context or "")
        self.assertIn("ctx-b", aggregated.context or "")

    def test_merges_reference_and_dedupes(self):
        results = [
            RagRunResult(
                agent_type="hybrid_agent",
                answer="答案",
                reference={
                    "chunks": [{"chunk_id": "movie:c1"}],
                    "entities": [{"id": "movie:e1"}],
                    "relationships": [],
                },
            ),
            RagRunResult(
                agent_type="graph_agent",
                answer="补充",
                reference={
                    "chunks": [{"chunk_id": "movie:c1"}, {"chunk_id": "movie:c2"}],
                    "entities": [{"id": "movie:e1"}, {"id": "movie:e2"}],
                    "relationships": [{"id": "movie:r1"}],
                },
            ),
        ]
        aggregated = aggregate_run_results(results=results)
        self.assertEqual(
            aggregated.reference,
            {
                "chunks": [{"chunk_id": "movie:c1"}, {"chunk_id": "movie:c2"}],
                "entities": [{"id": "movie:e1"}, {"id": "movie:e2"}],
                "relationships": [{"id": "movie:r1"}],
            },
        )

    def test_dedupes_retrieval_results_by_source_id_and_granularity(self):
        base = {
            "result_id": "r",
            "granularity": "Chunk",
            "evidence": "t",
            "metadata": {"source_id": "movie:c1", "source_type": "chunk"},
            "source": "hybrid_search",
            "created_at": "2025-01-01T00:00:00",
        }
        results = [
            RagRunResult(
                agent_type="hybrid_agent",
                answer="答案",
                retrieval_results=[{**base, "score": 0.2}],
            ),
            RagRunResult(
                agent_type="graph_agent",
                answer="补充",
                retrieval_results=[{**base, "score": 0.9}],
            ),
        ]
        aggregated = aggregate_run_results(results=results)
        self.assertEqual(len(aggregated.retrieval_results or []), 1)
        self.assertEqual((aggregated.retrieval_results or [])[0]["score"], 0.9)


if __name__ == "__main__":
    unittest.main()

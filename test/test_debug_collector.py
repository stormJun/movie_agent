import unittest


class TestDebugDataCollector(unittest.TestCase):
    def test_add_event_variants(self) -> None:
        from infrastructure.debug.debug_collector import DebugDataCollector

        c = DebugDataCollector("req1", "u1", "s1")

        c.add_event("execution_log", {"node": "x", "input": {}, "output": {}})
        self.assertEqual(len(c.execution_log), 1)
        self.assertIn("timestamp", c.execution_log[0])

        c.add_event("progress", {"stage": "retrieval", "completed": 1, "total": 2, "error": None})
        self.assertEqual(len(c.progress_events), 1)
        self.assertIn("timestamp", c.progress_events[0])

        c.add_event("error", {"message": "boom"})
        self.assertEqual(len(c.error_events), 1)
        self.assertEqual(c.error_events[0]["message"], "boom")

        c.add_event("route_decision", {"kb_prefix": "movie"})
        self.assertEqual(c.route_decision, {"kb_prefix": "movie"})

        c.add_event("rag_runs", [{"agent_type": "a"}, {"agent_type": "b"}])
        self.assertEqual(len(c.rag_runs), 2)

        c.add_event("combined_context", {"text": "ctx", "total_chars": 3, "truncated": False})
        self.assertEqual(c.combined_context, {"text": "ctx", "total_chars": 3, "truncated": False})

    def test_performance_metrics_uses_duration_ms(self) -> None:
        from infrastructure.debug.debug_collector import DebugDataCollector

        c = DebugDataCollector("req1", "u1", "s1")
        c.add_event(
            "execution_log",
            {"node": "route_decision", "node_type": "routing", "duration_ms": 12},
        )
        c.add_event(
            "execution_log",
            {"node": "rag_retrieval_stage_done", "node_type": "retrieval", "duration_ms": 345},
        )
        c.add_event(
            "execution_log",
            {"node": "answer_done", "node_type": "generation", "duration_ms": 678},
        )

        metrics = c.to_dict().get("performance_metrics") or {}
        self.assertEqual(metrics.get("routing_duration_ms"), 12)
        self.assertEqual(metrics.get("retrieval_duration_ms"), 345)
        self.assertEqual(metrics.get("generation_duration_ms"), 678)
        self.assertEqual(metrics.get("node_count"), 3)


if __name__ == "__main__":
    unittest.main()

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

        c.add_event("error", {"message": "boom"})
        self.assertEqual(len(c.error_events), 1)
        self.assertEqual(c.error_events[0]["message"], "boom")

        c.add_event("route_decision", {"kb_prefix": "movie"})
        self.assertEqual(c.route_decision, {"kb_prefix": "movie"})

        c.add_event("rag_runs", [{"agent_type": "a"}, {"agent_type": "b"}])
        self.assertEqual(len(c.rag_runs), 2)


if __name__ == "__main__":
    unittest.main()


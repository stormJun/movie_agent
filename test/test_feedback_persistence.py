import unittest


class TestFeedbackPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_in_memory_feedback_service_inserts_row(self):
        from infrastructure.feedback.service import InMemoryFeedbackService
        from infrastructure.persistence.postgres.feedback_store import InMemoryFeedbackStore

        store = InMemoryFeedbackStore()
        service = InMemoryFeedbackService(store=store)

        result = await service.process_feedback(
            message_id="m1",
            query="q1",
            is_positive=True,
            thread_id="t1",
            request_id="r1",
            agent_type="graph_agent",
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result.get("feedback"), "positive")
        self.assertEqual(len(store._by_key), 1)
        row = store._by_key[("t1", "m1")]
        self.assertEqual(row["message_id"], "m1")
        self.assertEqual(row["query"], "q1")
        self.assertTrue(row["is_positive"])
        self.assertEqual(row["metadata"], {"request_id": "r1"})

    async def test_in_memory_feedback_service_toggles_off_on_second_same_click(self):
        from infrastructure.feedback.service import InMemoryFeedbackService
        from infrastructure.persistence.postgres.feedback_store import InMemoryFeedbackStore

        store = InMemoryFeedbackStore()
        service = InMemoryFeedbackService(store=store)

        await service.process_feedback(
            message_id="m1",
            query="q1",
            is_positive=False,
            thread_id="t1",
            agent_type="graph_agent",
        )
        result = await service.process_feedback(
            message_id="m1",
            query="q1",
            is_positive=False,
            thread_id="t1",
            agent_type="graph_agent",
        )
        self.assertEqual(result.get("feedback"), "none")
        self.assertEqual(len(store._by_key), 0)


if __name__ == "__main__":
    unittest.main()

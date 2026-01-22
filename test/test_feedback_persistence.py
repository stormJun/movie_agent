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
            agent_type="graph_agent",
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(store._rows), 1)
        self.assertEqual(store._rows[0]["message_id"], "m1")
        self.assertEqual(store._rows[0]["query"], "q1")
        self.assertTrue(store._rows[0]["is_positive"])


if __name__ == "__main__":
    unittest.main()


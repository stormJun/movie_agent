import sys
import unittest
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from fastapi.testclient import TestClient

from server.main import app


class _StubFeedbackService:
    async def process_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str = "graph_agent",
        request_id: str | None = None,
    ):
        _ = (message_id, query, is_positive, thread_id, agent_type, request_id)
        return {"status": "success", "action": "ok", "feedback": "positive"}


class TestFeedbackRoutesSplit(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        from server.api.rest import dependencies as deps

        app.dependency_overrides[deps.get_feedback_service] = lambda: _StubFeedbackService()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides = {}

    async def test_admin_feedback_route(self):
        resp = self.client.post(
            "/api/v1/feedback",
            json={
                "message_id": "m1",
                "thread_id": "t1",
                "query": "q",
                "is_positive": True,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json().get("status"), "success")

    async def test_miniprogram_feedback_route(self):
        resp = self.client.post(
            "/api/v1/mp/feedback",
            json={
                "message_id": "m1",
                "thread_id": "t1",
                "query": "q",
                "is_positive": True,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json().get("status"), "success")


if __name__ == "__main__":
    unittest.main()

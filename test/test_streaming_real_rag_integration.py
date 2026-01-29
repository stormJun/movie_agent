import os
import sys
import json
import unittest
from pathlib import Path


_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _parse_sse_events(raw_text: str) -> list[dict]:
    events: list[dict] = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        events.append(json.loads(payload))
    return events


@unittest.skipUnless(
    os.getenv("RUN_REAL_RAG_TESTS", "").strip() == "1",
    "Set RUN_REAL_RAG_TESTS=1 (and provide Neo4j/LLM env) to run real RAG integration tests.",
)
class TestStreamingRealRagIntegration(unittest.TestCase):
    def test_chat_stream_emits_progress_and_tokens(self) -> None:
        # Import here so the skip guard is evaluated before heavy imports.
        from fastapi.testclient import TestClient

        from infrastructure.config.settings import (
            NEO4J_PASSWORD,
            NEO4J_URI,
            NEO4J_USERNAME,
            OPENAI_API_KEY,
            OPENAI_LLM_MODEL,
        )
        from server.main import app

        # Hard-skip if env is incomplete even when RUN_REAL_RAG_TESTS=1.
        if not (NEO4J_URI and NEO4J_USERNAME and NEO4J_PASSWORD):
            self.skipTest("Neo4j env not configured (NEO4J_URI/USERNAME/PASSWORD).")
        if not (OPENAI_API_KEY and OPENAI_LLM_MODEL):
            self.skipTest("LLM env not configured (OPENAI_API_KEY/OPENAI_LLM_MODEL).")

        client = TestClient(app)
        resp = client.post(
            "/api/v1/chat/stream",
            json={
                # Include movie-domain keywords so routing hits heuristic (no LLM router required).
                "user_id": "u1",
                "message": "recommend 电影 豆瓣 评分高的 科幻",
                "session_id": "real-rag-stream-1",
                "kb_prefix": None,
                "debug": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("content-type"), "text/event-stream; charset=utf-8")

        events = _parse_sse_events(resp.text)
        self.assertTrue(events)
        self.assertEqual(events[0]["status"], "start")
        self.assertEqual(events[-1]["status"], "done")

        progress = [e for e in events if e.get("status") == "progress"]
        self.assertTrue(progress)
        for e in progress:
            content = e.get("content")
            self.assertIsInstance(content, dict)
            for k in ("stage", "completed", "total", "error"):
                self.assertIn(k, content)

        tokens = [e for e in events if e.get("status") == "token"]
        self.assertTrue(tokens)

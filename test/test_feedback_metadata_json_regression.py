import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import unittest
from uuid import uuid4


class _FakeConn:
    def __init__(self) -> None:
        self.last_query = None
        self.last_args = None

    async def fetchrow(self, query: str, *args):
        self.last_query = query
        self.last_args = args
        return {"id": uuid4()}


class _Acquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self):
        return _Acquire(self._conn)


class TestFeedbackMetadataJsonRegression(unittest.IsolatedAsyncioTestCase):
    async def test_postgres_feedback_store_serializes_metadata_dict(self):
        # Regression: asyncpg expects JSONB bind args as str by default; passing a
        # raw dict raises DataError ("expected str, got dict").
        from infrastructure.persistence.postgres.feedback_store import PostgresFeedbackStore

        conn = _FakeConn()
        store = PostgresFeedbackStore(dsn="postgresql://unused")
        store._pool = _FakePool(conn)  # type: ignore[assignment]

        await store.insert_feedback(
            message_id="m1",
            query="q1",
            is_positive=False,
            thread_id="t1",
            agent_type="hybrid_agent",
            metadata={"request_id": "r1"},
        )

        self.assertIsNotNone(conn.last_query)
        self.assertIn("$6::jsonb", conn.last_query)
        self.assertIsInstance(conn.last_args[5], str)
        self.assertIn("request_id", conn.last_args[5])


if __name__ == "__main__":
    unittest.main()


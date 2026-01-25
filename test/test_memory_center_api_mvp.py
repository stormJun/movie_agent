import sys
import unittest
from pathlib import Path
from uuid import UUID, uuid4

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from fastapi.testclient import TestClient

from domain.memory import MemoryItem
from server.main import app


class _StubConversationStore:
    def __init__(self, *, conv_id: UUID, user_id: str) -> None:
        self._conv_id = conv_id
        self._user_id = user_id

    async def list_conversations(self, *, user_id: str, limit: int = 50, offset: int = 0):
        _ = (limit, offset)
        if user_id != self._user_id:
            return []
        return [{"id": self._conv_id, "session_id": "s1"}]


class _StubSummaryStore:
    async def get_summary(self, *, conversation_id: UUID):
        if not conversation_id:
            return None
        return {"summary": "recap", "updated_at": "2026-01-25T00:00:00Z"}


class _StubMemoryStore:
    async def search(self, *, user_id: str, query: str, top_k: int):
        _ = (query, top_k)
        return [
            MemoryItem(id="m1", text="User likes sci-fi", score=0.9, tags=("Genre: Sci-Fi",), metadata={})
        ]

    async def get_all(self, *, user_id: str, limit: int = 100, offset: int = 0):
        _ = (user_id, limit, offset)
        return [
            MemoryItem(id="m1", text="User likes sci-fi", score=0.9, tags=("Genre: Sci-Fi",), metadata={})
        ]

    async def add(self, *, user_id: str, text: str, tags=None, metadata=None):
        _ = (user_id, text, tags, metadata)
        return "m_new"

    async def delete(self, *, user_id: str, memory_id: str) -> bool:
        _ = user_id
        return memory_id == "m1"

    async def close(self) -> None:
        return None


class _StubWatchlistStore:
    async def list_items(self, *, user_id: str, limit: int = 50, offset: int = 0):
        _ = (user_id, limit, offset)
        return []

    async def count_items(self, *, user_id: str) -> int:
        _ = user_id
        return 0

    async def add_item(self, *, user_id: str, title: str, year=None, metadata=None):
        raise NotImplementedError

    async def delete_item(self, *, user_id: str, item_id):
        raise NotImplementedError

    async def close(self) -> None:
        return None


class _StubMemoryFacade:
    def __init__(self, *, summary_store, memory_store) -> None:
        from application.memory_center.memory_facade_service import MemoryFacadeService

        self._svc = MemoryFacadeService(
            summary_store=summary_store,
            memory_store=memory_store,
            watchlist_store=_StubWatchlistStore(),
        )

    async def get_dashboard(self, *, conversation_id: UUID, user_id: str):
        return await self._svc.get_dashboard(conversation_id=conversation_id, user_id=user_id)

    async def delete_memory_item(self, *, user_id: str, memory_id: str) -> bool:
        return await self._svc.delete_memory_item(user_id=user_id, memory_id=memory_id)


class TestMemoryCenterApiMvp(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.conv_id = uuid4()
        self.user_id = "u1"

        from server.api.rest import dependencies as deps

        app.dependency_overrides[deps.get_conversation_store] = lambda: _StubConversationStore(
            conv_id=self.conv_id, user_id=self.user_id
        )
        app.dependency_overrides[deps.get_memory_facade_service] = lambda: _StubMemoryFacade(
            summary_store=_StubSummaryStore(), memory_store=_StubMemoryStore()
        )

        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides = {}

    async def test_dashboard(self):
        resp = self.client.get(
            "/api/v1/memory/dashboard",
            params={"conversation_id": str(self.conv_id), "user_id": self.user_id},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["summary"]["content"], "recap")
        self.assertEqual(len(data["taste_profile"]), 1)
        self.assertEqual(data["taste_profile"][0]["id"], "m1")

    async def test_delete_item(self):
        resp = self.client.delete(
            "/api/v1/memory/items/m1",
            params={"user_id": self.user_id},
        )
        self.assertEqual(resp.status_code, 204, resp.text)

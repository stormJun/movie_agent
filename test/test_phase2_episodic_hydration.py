import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from infrastructure.chat_history.episodic_memory import ConversationEpisodicMemory
from infrastructure.chat_history.episodic_task_manager import EpisodicTaskManager
from infrastructure.chat_history import episodic_memory as episodic_mod


class _DummyEmbeddings:
    def embed_query(self, text: str):
        # Stable embedding for tests.
        return [1.0, 0.0, 0.0]


class _IdsOnlyEpisodeStore:
    async def search_episodes(
        self,
        *,
        conversation_id: UUID,
        query_embedding: List[float],
        limit: int,
        scan_limit: int = 200,
        exclude_assistant_message_ids: Optional[List[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        _ = (query_embedding, limit, scan_limit, exclude_assistant_message_ids)
        # Simulate Milvus: ids as strings, no full message content.
        return [
            {
                "assistant_message_id": self._a_id,
                "user_message_id": self._u_id,
                "created_at": 0,
                "similarity": 0.9,
            }
        ]

    async def upsert_episode(self, **kwargs: Any) -> bool:  # pragma: no cover
        _ = kwargs
        return True

    async def list_episodes(self, **kwargs: Any) -> List[Dict[str, Any]]:  # pragma: no cover
        _ = kwargs
        return []

    async def close(self) -> None:  # pragma: no cover
        return None

    def __init__(self, *, u_id: UUID, a_id: UUID) -> None:
        self._u_id = str(u_id)
        self._a_id = str(a_id)


class _StubConversationStore:
    async def get_messages_by_ids(
        self,
        *,
        conversation_id: UUID,
        message_ids: List[UUID],
    ) -> List[Dict[str, Any]]:
        _ = conversation_id
        out: List[Dict[str, Any]] = []
        for mid in message_ids:
            if mid == self._u_id:
                out.append({"id": mid, "role": "user", "content": "u1", "completed": True})
            elif mid == self._a_id:
                out.append({"id": mid, "role": "assistant", "content": "A1", "completed": True})
        return out

    def __init__(self, *, u_id: UUID, a_id: UUID) -> None:
        self._u_id = u_id
        self._a_id = a_id


class TestPhase2EpisodicHydration(unittest.IsolatedAsyncioTestCase):
    async def test_hydrates_messages_from_conversation_store(self) -> None:
        conv_id = uuid4()
        u_id = uuid4()
        a_id = uuid4()

        # Patch embedding model factory used by episodic_memory module.
        prev = episodic_mod.get_embeddings_model
        episodic_mod.get_embeddings_model = lambda: _DummyEmbeddings()
        try:
            store = _IdsOnlyEpisodeStore(u_id=u_id, a_id=a_id)
            conv_store = _StubConversationStore(u_id=u_id, a_id=a_id)
            m = ConversationEpisodicMemory(
                store=store,  # type: ignore[arg-type]
                task_manager=EpisodicTaskManager(max_concurrent=1),
                conversation_store=conv_store,  # type: ignore[arg-type]
                top_k=1,
                scan_limit=10,
                min_score=0.2,
                recall_mode="always",
                max_context_chars=200,
            )
            episodes = await m.recall_relevant(conversation_id=conv_id, query="q")
            self.assertEqual(len(episodes), 1)
            self.assertEqual(episodes[0].get("user_message"), "u1")
            self.assertEqual(episodes[0].get("assistant_message"), "A1")
        finally:
            episodic_mod.get_embeddings_model = prev


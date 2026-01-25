import sys
import unittest
from pathlib import Path
from uuid import UUID, uuid4

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from infrastructure.chat_history.episodic_memory import ConversationEpisodicMemory
from infrastructure.chat_history.episodic_task_manager import EpisodicTaskManager
from infrastructure.chat_history import episodic_memory as episodic_mod
from infrastructure.persistence.postgres.conversation_episode_store import (
    InMemoryConversationEpisodeStore,
)


class _DummyEmbeddings:
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping

    def embed_query(self, text: str):
        # Deterministic embedding for tests.
        return list(self._mapping.get(text, [0.0, 0.0, 1.0]))


class TestChatHistoryEpisodicMemoryPhase2(unittest.IsolatedAsyncioTestCase):
    async def test_recall_and_exclude(self) -> None:
        store = InMemoryConversationEpisodeStore()
        tasks = EpisodicTaskManager(max_concurrent=1)
        conv_id = uuid4()

        # Patch embedding model factory used by episodic_memory module.
        prev = episodic_mod.get_embeddings_model
        episodic_mod.get_embeddings_model = lambda: _DummyEmbeddings(
            {
                # index text
                "u1\nA1": [1.0, 0.0, 0.0],
                "u2\nA2": [0.0, 1.0, 0.0],
                # query
                "q": [1.0, 0.0, 0.0],
            }
        )
        try:
            m = ConversationEpisodicMemory(
                store=store,
                task_manager=tasks,
                top_k=2,
                scan_limit=10,
                min_score=0.2,
                recall_mode="always",
                max_context_chars=500,
            )

            u1_id = uuid4()
            a1_id = uuid4()
            await m._index_episode(  # type: ignore[attr-defined]
                conversation_id=conv_id,
                user_message_id=u1_id,
                assistant_message_id=a1_id,
                user_message="u1",
                assistant_message="A1",
            )
            u2_id = uuid4()
            a2_id = uuid4()
            await m._index_episode(  # type: ignore[attr-defined]
                conversation_id=conv_id,
                user_message_id=u2_id,
                assistant_message_id=a2_id,
                user_message="u2",
                assistant_message="A2",
            )

            episodes = await m.recall_relevant(conversation_id=conv_id, query="q")
            self.assertEqual(len(episodes), 1)
            self.assertEqual(episodes[0]["assistant_message_id"], a1_id)

            episodes2 = await m.recall_relevant(
                conversation_id=conv_id,
                query="q",
                exclude_assistant_message_ids=[a1_id],
            )
            self.assertEqual(episodes2, [])

            ctx = m.format_context(episodes=episodes)
            self.assertIsInstance(ctx, str)
            self.assertIn("【相关历史】", ctx or "")
            self.assertIn("u1", ctx or "")
        finally:
            episodic_mod.get_embeddings_model = prev


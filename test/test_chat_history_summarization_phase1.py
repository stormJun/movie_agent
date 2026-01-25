import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from infrastructure.chat_history import ConversationSummarizer, SummaryTaskManager
from infrastructure.chat_history import summarizer as summarizer_mod
from infrastructure.persistence.postgres.conversation_store import InMemoryConversationStore
from infrastructure.persistence.postgres.conversation_summary_store import (
    InMemoryConversationSummaryStore,
)


class _DummyResp:
    def __init__(self, content: str) -> None:
        self.content = content


class _DummyLLM:
    async def ainvoke(self, messages):
        # The summarizer should invoke chat models with structured messages
        # (system/human roles preserved), not a flattened string.
        if not isinstance(messages, list):
            raise TypeError("expected list of chat messages")
        return _DummyResp(f"summary (messages={len(messages)})")


class TestChatHistorySummarizationPhase1(unittest.IsolatedAsyncioTestCase):
    async def test_summary_updates_only_for_messages_outside_recent_window(self) -> None:
        store = InMemoryConversationStore()
        conversation_id = await store.get_or_create_conversation_id(user_id="u1", session_id="s1")
        summary_store = InMemoryConversationSummaryStore(conversation_store=store)

        # Patch the LLM factory used by the summarizer module (it imports get_llm_model by value).
        prev = summarizer_mod.get_llm_model
        summarizer_mod.get_llm_model = lambda: _DummyLLM()
        try:
            task_manager = SummaryTaskManager()
            summarizer = ConversationSummarizer(
                store=summary_store,
                task_manager=task_manager,
                min_messages=4,
                update_delta=3,
                window_size=2,
            )

            # Build 6 completed messages with deterministic timestamps.
            base = datetime(2026, 1, 1, 0, 0, 0)
            for i in range(6):
                await store.append_message(
                    conversation_id=conversation_id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"m{i+1}",
                    completed=True,
                )
                store._messages[conversation_id][-1]["created_at"] = base + timedelta(seconds=i)  # type: ignore[attr-defined]

            # Add one partial assistant message; it should be ignored by Phase 1.
            await store.append_message(
                conversation_id=conversation_id,
                role="assistant",
                content="partial",
                completed=False,
            )
            store._messages[conversation_id][-1]["created_at"] = base + timedelta(seconds=2, milliseconds=500)  # type: ignore[attr-defined]

            await summarizer.try_trigger_update(conversation_id=conversation_id)
            row = await summary_store.get_summary(conversation_id=conversation_id)
            self.assertIsNotNone(row)

            # With window_size=2, the window start is message 5, so eligible messages are 1..4.
            self.assertEqual(int(row["covered_message_count"]), 4)
            self.assertEqual(int(row["summary_version"]), 1)

            # Append 2 more completed messages: eligible is only messages 5..6 (len=2), < update_delta => no update.
            for i in range(2):
                await store.append_message(
                    conversation_id=conversation_id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"m{7+i}",
                    completed=True,
                )
                store._messages[conversation_id][-1]["created_at"] = base + timedelta(seconds=6 + i)  # type: ignore[attr-defined]

            await summarizer.try_trigger_update(conversation_id=conversation_id)
            row2 = await summary_store.get_summary(conversation_id=conversation_id)
            self.assertEqual(int(row2["covered_message_count"]), 4)
            self.assertEqual(int(row2["summary_version"]), 1)

            # Append 2 more messages: now eligible 5..8 (len=4) >= update_delta => update advances cursor.
            for i in range(2):
                await store.append_message(
                    conversation_id=conversation_id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"m{9+i}",
                    completed=True,
                )
                store._messages[conversation_id][-1]["created_at"] = base + timedelta(seconds=8 + i)  # type: ignore[attr-defined]

            await summarizer.try_trigger_update(conversation_id=conversation_id)
            row3 = await summary_store.get_summary(conversation_id=conversation_id)
            self.assertEqual(int(row3["covered_message_count"]), 8)
            self.assertEqual(int(row3["summary_version"]), 2)
        finally:
            summarizer_mod.get_llm_model = prev


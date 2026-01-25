import sys
import unittest
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from application.chat.handlers.chat_handler import ChatHandler
from application.chat.handlers.stream_handler import StreamHandler
from application.chat.memory_service import MemoryService
from application.ports.conversation_store_port import ConversationStorePort
from domain.chat.entities.route_decision import RouteDecision
from domain.chat.entities.rag_run import RagRunResult, RagRunSpec
from domain.memory import MemoryItem
from domain.memory.policy import MemoryPolicy


class _StubConversationStore(ConversationStorePort):
    async def get_or_create_conversation_id(self, *, user_id: str, session_id: str):
        return f"{user_id}:{session_id}"

    async def append_message(
        self,
        *,
        conversation_id,
        role: str,
        content: str,
        citations=None,
        debug=None,
        completed: bool = True,
    ):
        return "m1"

    async def list_messages(self, *, conversation_id, limit=None, before=None, desc: bool = False):
        return []

    async def clear_messages(self, *, conversation_id):
        return 0


class _RouterGeneral:
    def route(
        self,
        *,
        message: str,
        session_id: str,
        requested_kb: Optional[str],
        agent_type: str,
    ) -> RouteDecision:
        return RouteDecision(
            requested_kb_prefix=(requested_kb or ""),
            routed_kb_prefix="general",
            kb_prefix="general",
            confidence=1.0,
            method="stub",
            reason="",
            worker_name="",
        )


class _RouterRag:
    def route(
        self,
        *,
        message: str,
        session_id: str,
        requested_kb: Optional[str],
        agent_type: str,
    ) -> RouteDecision:
        return RouteDecision(
            requested_kb_prefix=(requested_kb or ""),
            routed_kb_prefix="movie",
            kb_prefix="movie",
            confidence=1.0,
            method="stub",
            reason="",
            worker_name="movie:hybrid_agent:retrieve_only",
        )


class _MemoryStore:
    async def search(self, *, user_id: str, query: str, top_k: int):
        return [
            MemoryItem(id="m1", text="用户喜欢科幻电影", score=0.9),
            MemoryItem(id="m2", text="用户不喜欢恐怖片", score=0.8),
        ]

    async def add(self, *, user_id: str, text: str, tags=None, metadata=None):
        return "id1"

    async def close(self) -> None:
        return None


class _StubCompletion:
    def __init__(self) -> None:
        self.last_memory_context: str | None = None

    async def generate(
        self,
        *,
        message: str,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        _ = (history, summary, episodic_context)
        self.last_memory_context = memory_context
        return "ok"


class _StubExecutor:
    def __init__(self) -> None:
        self.last_memory_context: str | None = None

    async def run(
        self,
        *,
        plan: list[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> tuple[RagRunResult, list[RagRunResult]]:
        _ = (history, summary, episodic_context)
        self.last_memory_context = memory_context
        return RagRunResult(agent_type="rag_executor", answer="ok"), []


class _StubStreamExecutor:
    def __init__(self) -> None:
        self.last_memory_context: str | None = None

    async def stream(
        self,
        *,
        plan: list[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        _ = (history, summary, episodic_context)
        self.last_memory_context = memory_context
        yield {"status": "token", "content": "ok"}
        yield {"status": "done"}


class TestMem0MemoryPlumbing(unittest.IsolatedAsyncioTestCase):
    async def test_general_path_injects_memory_context(self) -> None:
        completion = _StubCompletion()
        memory = MemoryService(
            store=_MemoryStore(),
            policy=MemoryPolicy(top_k=5, min_score=0.0, max_chars=500),
            write_enabled=False,
        )
        h = ChatHandler(
            router=_RouterGeneral(),
            executor=_StubExecutor(),
            stream_executor=_StubStreamExecutor(),  # type: ignore[arg-type]
            completion=completion,
            conversation_store=_StubConversationStore(),
            memory_service=memory,
        )
        resp = await h.handle(
            user_id="u1",
            message="hello",
            session_id="s1",
            kb_prefix=None,
            debug=False,
        )
        self.assertEqual(resp["answer"], "ok")
        self.assertIsInstance(completion.last_memory_context, str)
        self.assertIn("用户长期记忆", completion.last_memory_context or "")

    async def test_rag_path_forwards_memory_context_to_executor(self) -> None:
        executor = _StubExecutor()
        memory = MemoryService(
            store=_MemoryStore(),
            policy=MemoryPolicy(top_k=5, min_score=0.0, max_chars=500),
            write_enabled=False,
        )
        h = ChatHandler(
            router=_RouterRag(),
            executor=executor,
            stream_executor=_StubStreamExecutor(),  # type: ignore[arg-type]
            completion=_StubCompletion(),
            conversation_store=_StubConversationStore(),
            memory_service=memory,
        )
        await h.handle(
            user_id="u1",
            message="recommend",
            session_id="s1",
            kb_prefix=None,
            debug=False,
        )
        self.assertIsInstance(executor.last_memory_context, str)
        self.assertIn("用户长期记忆", executor.last_memory_context or "")

    async def test_stream_forwards_memory_context_to_stream_executor(self) -> None:
        executor = _StubStreamExecutor()
        memory = MemoryService(
            store=_MemoryStore(),
            policy=MemoryPolicy(top_k=5, min_score=0.0, max_chars=500),
            write_enabled=False,
        )
        h = StreamHandler(
            router=_RouterRag(),
            executor=_StubExecutor(),  # type: ignore[arg-type]
            stream_executor=executor,  # type: ignore[arg-type]
            completion=_StubCompletion(),  # type: ignore[arg-type]
            conversation_store=_StubConversationStore(),
            memory_service=memory,
        )
        events = []
        async for e in h.handle(
            user_id="u1",
            message="recommend",
            session_id="s1",
            kb_prefix=None,
            debug=False,
        ):
            events.append(e)
        self.assertTrue(events)
        self.assertIsInstance(executor.last_memory_context, str)
        self.assertIn("用户长期记忆", executor.last_memory_context or "")

    async def test_kb_handler_branch_keeps_memory_context(self) -> None:
        from application.handlers.base import KnowledgeBaseHandler

        class _KBHandler(KnowledgeBaseHandler):
            name = "movie"
            kb_prefix = "movie"

            def build_plan(self, *, message: str, agent_type: str) -> list[RagRunSpec]:
                _ = message
                _ = agent_type
                return [RagRunSpec(agent_type="hybrid_agent")]

        class _KBFactory:
            def __init__(self, handler: KnowledgeBaseHandler):
                self._h = handler

            def get(self, kb_prefix: str):
                return self._h if kb_prefix == "movie" else None

        class _RouterMovie:
            def route(self, *, message: str, session_id: str, requested_kb: Optional[str], agent_type: str) -> RouteDecision:
                return RouteDecision(
                    requested_kb_prefix=(requested_kb or ""),
                    routed_kb_prefix="movie",
                    kb_prefix="movie",
                    confidence=1.0,
                    method="stub",
                    reason="",
                    worker_name="movie:hybrid_agent:retrieve_only",
                )

        executor = _StubExecutor()
        kb_handler = _KBHandler(
            executor=executor,
            stream_executor=_StubStreamExecutor(),
        )
        memory = MemoryService(
            store=_MemoryStore(),
            policy=MemoryPolicy(top_k=5, min_score=0.0, max_chars=500),
            write_enabled=False,
        )
        h = ChatHandler(
            router=_RouterMovie(),
            executor=_StubExecutor(),
            stream_executor=_StubStreamExecutor(),  # type: ignore[arg-type]
            completion=_StubCompletion(),
            conversation_store=_StubConversationStore(),
            memory_service=memory,
            kb_handler_factory=_KBFactory(kb_handler),  # type: ignore[arg-type]
            enable_kb_handlers=True,
        )
        await h.handle(
            user_id="u1",
            message="recommend",
            session_id="s1",
            kb_prefix="movie",
            debug=False,
        )
        self.assertIsInstance(executor.last_memory_context, str)
        self.assertIn("用户长期记忆", executor.last_memory_context or "")

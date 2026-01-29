import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import json
import unittest
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi.testclient import TestClient

from application.chat.handlers.chat_handler import ChatHandler
from application.chat.handlers.stream_handler import StreamHandler
from application.ports.conversation_store_port import ConversationStorePort
from domain.chat.entities.route_decision import RouteDecision
from domain.chat.entities.rag_run import RagRunResult, RagRunSpec
from server.api.rest.dependencies import get_chat_handler, get_stream_handler
from server.main import app


class _StubRouter:
    def route(
        self,
        *,
        message: str,
        session_id: str,
        requested_kb: Optional[str],
    ) -> RouteDecision:
        _ = session_id
        kb = (requested_kb or "").strip()
        if not kb:
            if "movie" in message.lower():
                kb = "movie"
            elif "edu" in message.lower():
                kb = "edu"
            else:
                kb = "general"

        # Router owns agent selection; in tests we keep it deterministic.
        worker_name = f"{kb}:hybrid_agent:retrieve_only" if kb not in {"", "general"} else ""
        return RouteDecision(
            requested_kb_prefix=(requested_kb or ""),
            routed_kb_prefix=kb,
            kb_prefix=kb,
            confidence=0.99,
            method="stub",
            reason="test",
            worker_name=worker_name,
        )


class _StubCompletion:
    async def generate(
        self,
        *,
        message: str,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: List[Dict[str, Any]] | None = None,
    ) -> str:
        _ = (history, memory_context, summary, episodic_context)
        return f"GEN:{message}"


async def _stub_general_answer_stream(
    *,
    question: str,
    memory_context: str | None = None,
    summary: str | None = None,
    episodic_context: str | None = None,
    history: List[Dict[str, Any]] | None = None,
) -> AsyncGenerator[str, None]:
    _ = (memory_context, summary, episodic_context, history)
    yield f"GEN_STREAM:{question}"


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
        request_id: str | None = None,
    ):
        return "m1"

    async def update_message(
        self,
        *,
        conversation_id,
        message_id,
        content=None,
        citations=None,
        debug=None,
        completed=None,
    ):
        _ = (conversation_id, message_id, content, citations, debug, completed)
        return True

    async def list_messages(self, *, conversation_id, limit=None, before=None, desc: bool = False):
        return []

    async def clear_messages(self, *, conversation_id):
        return 0


class _StubExecutor:
    async def run(
        self,
        *,
        plan: List[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        user_id: str | None = None,
        request_id: str | None = None,
        conversation_id: Any | None = None,
        user_message_id: Any | None = None,
        incognito: bool = False,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: List[Dict[str, Any]] | None = None,
        extracted_entities: Dict[str, Any] | None = None,
        query_intent: str | None = None,
        media_type_hint: str | None = None,
        filters: Dict[str, Any] | None = None,
    ) -> tuple[RagRunResult, List[RagRunResult]]:
        _ = (
            history,
            memory_context,
            summary,
            episodic_context,
            extracted_entities,
            query_intent,
            media_type_hint,
            filters,
            user_id,
            request_id,
            conversation_id,
            user_message_id,
            incognito,
        )
        run = RagRunResult(
            agent_type=(plan[0].agent_type if plan else "none"),
            answer="",
            context=f"ctx:{kb_prefix}",
            retrieval_results=[
                {
                    "score": 1.0,
                    "granularity": "Chunk",
                    "metadata": {"source_id": f"{kb_prefix}:s1"},
                    "evidence": f"ev:{kb_prefix}",
                }
            ],
            reference={"chunks": [{"chunk_id": f"{kb_prefix}:c1"}]},
        )
        aggregated = RagRunResult(
            agent_type="rag_executor",
            answer=f"RAG:{kb_prefix}:{message}",
            context=run.context,
            retrieval_results=run.retrieval_results,
            reference=run.reference,
        )
        return aggregated, [run]


class _StubStreamExecutor:
    async def stream(
        self,
        *,
        plan: List[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        user_id: str | None = None,
        request_id: str | None = None,
        conversation_id: Any | None = None,
        user_message_id: Any | None = None,
        incognito: bool = False,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: List[Dict[str, Any]] | None = None,
        extracted_entities: Dict[str, Any] | None = None,
        query_intent: str | None = None,
        media_type_hint: str | None = None,
        filters: Dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        _ = (
            history,
            memory_context,
            summary,
            episodic_context,
            extracted_entities,
            query_intent,
            media_type_hint,
            filters,
            user_id,
            request_id,
            conversation_id,
            user_message_id,
            incognito,
        )
        # Mimic Phase2 behavior: emit progress, tokens, then done.
        yield {
            "status": "progress",
            "content": {
                "stage": "generation",
                "completed": 0,
                "total": len(plan),
                "error": None,
                "agent_type": "",
                "retrieval_count": None,
            },
        }
        if debug:
            # Backward-compat variant: infrastructure sometimes yields {"execution_log": {...}}
            # (normalize_stream_event() maps it to status=execution_log).
            yield {"execution_log": {"node": "stub_exec", "input": {"kb_prefix": kb_prefix}}}
            yield {
                "status": "rag_runs",
                "content": [{"agent_type": "stub_agent", "retrieval_count": 0, "error": None}],
            }
        yield {"status": "token", "content": f"S:{kb_prefix}:"}
        yield {"status": "token", "content": message}
        yield {"status": "done"}


class _StubKBHandler:
    def __init__(self, kb_prefix: str):
        self._kb_prefix = kb_prefix

    async def process(
        self,
        *,
        message: str,
        session_id: str,
        agent_type: str,
        debug: bool,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: List[Dict[str, Any]] | None = None,
        extracted_entities: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        _ = (memory_context, summary, episodic_context, history, extracted_entities, kwargs)
        return {
            "answer": f"KB:{self._kb_prefix}:{message}",
            "reference": {"chunks": [{"chunk_id": f"{self._kb_prefix}:c1"}]},
            "retrieval_results": [
                {
                    "score": 1.0,
                    "granularity": "Chunk",
                    "metadata": {"source_id": f"{self._kb_prefix}:s1"},
                    "evidence": f"ev:{self._kb_prefix}",
                }
            ],
        }

    async def process_stream(
        self,
        *,
        message: str,
        session_id: str,
        agent_type: str,
        debug: bool,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: List[Dict[str, Any]] | None = None,
        extracted_entities: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        _ = (memory_context, summary, episodic_context, history, extracted_entities, kwargs)
        yield {
            "status": "progress",
            "content": {"stage": "retrieval", "completed": 0, "total": 1, "error": None},
        }
        yield {"status": "token", "content": f"KB_STREAM:{self._kb_prefix}:"}
        yield {"status": "token", "content": message}
        yield {"status": "done"}


class _StubKBHandlerFactory:
    def get(self, kb_prefix: str):
        # Phase 3: only edu still uses the legacy KB handler path.
        # movie is routed to the new retrieval_subgraph (Plan->Execute->Reflect->Merge).
        if kb_prefix in {"edu"}:
            return _StubKBHandler(kb_prefix)
        return None


async def _stub_retrieval_runner(
    *,
    spec: RagRunSpec,
    message: str,
    session_id: str,
    kb_prefix: str,
    debug: bool,
) -> RagRunResult:
    _ = (session_id, debug)
    # Minimal fake retrieval result to drive retrieval_subgraph + generation.
    return RagRunResult(
        agent_type=spec.agent_type,
        answer="",
        context=f"ctx:{kb_prefix}:{spec.agent_type}",
        retrieval_results=[
            {
                "score": 1.0,
                "granularity": "Chunk",
                "metadata": {"source_id": f"{kb_prefix}:s1"},
                "evidence": f"ev:{kb_prefix}",
            }
        ],
        reference={"chunks": [{"chunk_id": f"{kb_prefix}:c1"}]},
        execution_log=[],
    )


def _stub_rag_answer(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    summary: str | None = None,
    episodic_context: str | None = None,
    history: List[Dict[str, Any]] | None = None,
) -> str:
    _ = (memory_context, summary, episodic_context, history)
    return f"RAG_ANS:{question}::{context}"


async def _stub_rag_answer_stream(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    summary: str | None = None,
    episodic_context: str | None = None,
    history: List[Dict[str, Any]] | None = None,
) -> AsyncGenerator[str, None]:
    _ = (memory_context, summary, episodic_context, history)
    yield f"RAG_STREAM:{question}::{context}"


def _parse_sse_events(raw_text: str) -> List[dict]:
    events: List[dict] = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        events.append(json.loads(payload))
    return events


def _assert_progress_contract(testcase: unittest.TestCase, events: List[dict]) -> None:
    """P0 contract for React: progress.content always has stage/completed/total/error."""
    progress = [e for e in events if isinstance(e, dict) and e.get("status") == "progress"]
    testcase.assertTrue(progress)
    for e in progress:
        content = e.get("content")
        testcase.assertIsInstance(content, dict)
        for k in ("stage", "completed", "total", "error"):
            testcase.assertIn(k, content)


class TestPhase2ApiE2E(unittest.TestCase):
    def setUp(self) -> None:
        router = _StubRouter()
        kb_factory = _StubKBHandlerFactory()
        conversation_store = _StubConversationStore()
        stream_exec = _StubStreamExecutor()
        self._chat_handler = ChatHandler(
            router=router,
            executor=_StubExecutor(),
            stream_executor=stream_exec,  # type: ignore[arg-type]
            completion=_StubCompletion(),
            conversation_store=conversation_store,
            kb_handler_factory=kb_factory,  # type: ignore[arg-type]
            enable_kb_handlers=True,
            retrieval_runner=_stub_retrieval_runner,
            rag_answer_fn=_stub_rag_answer,
            rag_answer_stream_fn=_stub_rag_answer_stream,
        )
        self._stream_handler = StreamHandler(
            router=router,
            executor=_StubExecutor(),  # type: ignore[arg-type]
            stream_executor=stream_exec,  # type: ignore[arg-type]
            completion=_StubCompletion(),  # type: ignore[arg-type]
            conversation_store=conversation_store,
            kb_handler_factory=kb_factory,  # type: ignore[arg-type]
            enable_kb_handlers=True,
            general_answer_stream_fn=_stub_general_answer_stream,
            retrieval_runner=_stub_retrieval_runner,
            rag_answer_fn=_stub_rag_answer,
            rag_answer_stream_fn=_stub_rag_answer_stream,
        )

        app.dependency_overrides[get_chat_handler] = lambda: self._chat_handler
        app.dependency_overrides[get_stream_handler] = lambda: self._stream_handler
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_chat_general_path(self) -> None:
        resp = self.client.post(
            "/api/v1/chat",
            json={
                "user_id": "u1",
                "message": "hello",
                "session_id": "s1",
                "kb_prefix": None,
                "debug": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["answer"], "GEN:hello")
        self.assertEqual(body["debug"], True)
        self.assertEqual(body["route_decision"]["kb_prefix"], "general")

    def test_chat_kb_handler_movie_path(self) -> None:
        resp = self.client.post(
            "/api/v1/chat",
            json={
                "user_id": "u1",
                "message": "recommend",
                "session_id": "s1",
                "kb_prefix": "movie",
                "debug": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # movie should go through retrieval_subgraph (not the legacy KB handler).
        self.assertTrue(isinstance(body.get("answer"), str) and body["answer"].startswith("RAG_ANS:recommend::"))
        self.assertEqual(body["route_decision"]["kb_prefix"], "movie")
        self.assertIn("retrieval_results", body)

    def test_chat_kb_handler_edu_path(self) -> None:
        resp = self.client.post(
            "/api/v1/chat",
            json={
                "user_id": "u1",
                "message": "question",
                "session_id": "s1",
                "kb_prefix": "edu",
                "debug": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["answer"], "KB:edu:question")
        self.assertEqual(body["route_decision"]["kb_prefix"], "edu")

    def test_chat_stream_general_sse(self) -> None:
        resp = self.client.post(
            "/api/v1/chat/stream",
            json={
                "user_id": "u1",
                "message": "hello",
                "session_id": "s1",
                "kb_prefix": None,
                "debug": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("content-type"), "text/event-stream; charset=utf-8")

        events = _parse_sse_events(resp.text)
        self.assertTrue(events)
        self.assertEqual(events[0]["status"], "start")
        # Non-debug streaming should still expose progress events so the UI can
        # visualize execution stages.
        self.assertTrue(any(e.get("status") == "progress" for e in events))
        _assert_progress_contract(self, events)
        self.assertEqual(events[-1]["status"], "done")

    def test_chat_stream_movie_sse_uses_retrieval_subgraph(self) -> None:
        resp = self.client.post(
            "/api/v1/chat/stream",
            json={
                "user_id": "u1",
                "message": "hello",
                "session_id": "s1",
                "kb_prefix": "movie",
                "debug": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        events = _parse_sse_events(resp.text)
        self.assertEqual(events[0]["status"], "start")
        self.assertTrue(any(e.get("status") == "progress" for e in events))
        _assert_progress_contract(self, events)
        tokens = [e.get("content") for e in events if e.get("status") == "token"]
        self.assertTrue(any(isinstance(t, str) and t.startswith("RAG_STREAM:") for t in tokens))
        self.assertEqual(events[-1]["status"], "done")

    def test_chat_stream_edu_sse_uses_kb_handler(self) -> None:
        resp = self.client.post(
            "/api/v1/chat/stream",
            json={
                "user_id": "u1",
                "message": "hello",
                "session_id": "s1",
                "kb_prefix": "edu",
                "debug": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        events = _parse_sse_events(resp.text)
        self.assertTrue(any(e.get("status") == "progress" for e in events))
        _assert_progress_contract(self, events)
        tokens = [e.get("content") for e in events if e.get("status") == "token"]
        self.assertTrue(any(isinstance(t, str) and t.startswith("KB_STREAM:edu:") for t in tokens))

    def test_chat_stream_debug_separates_debug_data(self) -> None:
        resp = self.client.post(
            "/api/v1/chat/stream",
            json={
                "user_id": "u1",
                "message": "hello",
                "session_id": "s1",
                "kb_prefix": None,
                "debug": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        events = _parse_sse_events(resp.text)
        self.assertTrue(events)
        self.assertEqual(events[0]["status"], "start")
        request_id = events[0].get("request_id")
        self.assertIsInstance(request_id, str)
        self.assertTrue(request_id)

        # Cache-only debug events must NOT be forwarded in the SSE stream.
        forwarded_statuses = {e.get("status") for e in events if isinstance(e, dict)}
        self.assertNotIn("execution_log", forwarded_statuses)
        self.assertNotIn("route_decision", forwarded_statuses)
        self.assertNotIn("rag_runs", forwarded_statuses)

        self.assertEqual(events[-1]["status"], "done")
        self.assertEqual(events[-1].get("request_id"), request_id)

        debug_resp = self.client.get(
            f"/api/v1/debug/{request_id}",
            params={"user_id": "u1", "session_id": "s1"},
        )
        self.assertEqual(debug_resp.status_code, 200)
        debug_body = debug_resp.json()
        self.assertEqual(debug_body.get("request_id"), request_id)
        self.assertEqual(debug_body.get("user_id"), "u1")
        self.assertEqual(debug_body.get("session_id"), "s1")
        self.assertIsInstance(debug_body.get("execution_log"), list)
        self.assertTrue(debug_body.get("execution_log"))
        self.assertIsInstance(debug_body.get("progress_events"), list)
        self.assertTrue(debug_body.get("route_decision"))
        self.assertIsInstance(debug_body.get("rag_runs"), list)

        # Ownership enforcement.
        wrong_user = self.client.get(
            f"/api/v1/debug/{request_id}",
            params={"user_id": "u2", "session_id": "s1"},
        )
        self.assertEqual(wrong_user.status_code, 403)

        # Cleanup (avoid leaking cache across tests).
        cleared = self.client.delete(f"/api/v1/debug/{request_id}", params={"user_id": "u1"})
        self.assertEqual(cleared.status_code, 200)

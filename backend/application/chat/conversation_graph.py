from __future__ import annotations

import dataclasses
import time
from typing import Any, AsyncGenerator, Callable, Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.constants import CONF, CONFIG_KEY_STREAM_WRITER
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from application.handlers.factory import KnowledgeBaseHandlerFactory
from application.chat.memory_service import MemoryService
from application.ports.chat_completion_port import ChatCompletionPort
from application.ports.conversation_episodic_memory_port import ConversationEpisodicMemoryPort
from application.ports.conversation_store_port import ConversationStorePort
from application.ports.conversation_summarizer_port import ConversationSummarizerPort
from application.ports.rag_executor_port import RAGExecutorPort
from application.ports.rag_stream_executor_port import RAGStreamExecutorPort
from application.ports.router_port import RouterPort
from domain.chat.entities.rag_run import RagRunSpec


def _resolve_agent_type(*, agent_type: str, worker_name: str) -> str:
    raw = (worker_name or "").strip()
    if not raw:
        return agent_type
    parts = [p.strip() for p in raw.split(":")]
    # worker_name v2: {kb_prefix}:{agent_type}:{agent_mode}
    if len(parts) >= 2:
        candidate = parts[1]
        return candidate or agent_type
    return raw


class ConversationState(TypedDict, total=False):
    """Phase 3: LangGraph state for /chat and /chat/stream."""

    # Request inputs.
    stream: bool
    user_id: str
    message: str
    session_id: str
    requested_kb_prefix: str | None
    debug: bool
    incognito: bool
    agent_type: str
    conversation_id: Any
    current_user_message_id: Any

    # Derived routing.
    kb_prefix: str
    worker_name: str
    route_decision: dict[str, Any]
    routing_ms: int
    resolved_agent_type: str
    use_retrieval: bool

    # Recall / context.
    memory_context: str | None
    conversation_summary: str | None
    history: list[dict[str, Any]]
    episodic_memory: list[dict[str, Any]] | None
    episodic_context: str | None

    # Non-streaming answer payload.
    response: dict[str, Any]


def _get_stream_writer(config: RunnableConfig) -> Callable[[Any], None]:
    """Access LangGraph StreamWriter from config (Python 3.10 safe).

    `langgraph.config.get_stream_writer()` relies on async contextvar propagation
    (Python >= 3.11). We instead read the writer function from `config`.
    """
    try:
        writer = config.get(CONF, {}).get(CONFIG_KEY_STREAM_WRITER)
    except Exception:
        writer = None
    return writer if callable(writer) else (lambda _chunk: None)


class ConversationGraphRunner:
    def __init__(
        self,
        *,
        router: RouterPort,
        executor: RAGExecutorPort,
        stream_executor: RAGStreamExecutorPort,
        completion: ChatCompletionPort,
        conversation_store: ConversationStorePort,
        memory_service: MemoryService | None = None,
        conversation_summarizer: ConversationSummarizerPort | None = None,
        episodic_memory: ConversationEpisodicMemoryPort | None = None,
        kb_handler_factory: KnowledgeBaseHandlerFactory | None = None,
        enable_kb_handlers: bool = False,
    ) -> None:
        self._router = router
        self._executor = executor
        self._stream_executor = stream_executor
        self._completion = completion
        self._conversation_store = conversation_store
        self._memory_service = memory_service
        self._conversation_summarizer = conversation_summarizer
        self._episodic_memory = episodic_memory
        self._kb_handler_factory = kb_handler_factory
        self._enable_kb_handlers = enable_kb_handlers

        self._graph = self._build_graph()

    def _build_graph(self):
        g = StateGraph(ConversationState)
        g.add_node("route", self._route_node)
        g.add_node("recall", self._recall_node)
        g.add_node("execute", self._execute_node)

        g.add_edge(START, "route")
        g.add_edge("route", "recall")
        g.add_edge("recall", "execute")
        g.add_edge("execute", END)
        return g.compile()

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        # Cast for LangGraph (it accepts dict-like inputs).
        return await self._graph.ainvoke(dict(state))

    async def astream_custom(self, state: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        async for chunk in self._graph.astream(dict(state), stream_mode="custom"):
            if isinstance(chunk, dict):
                yield chunk
            else:
                # Defensive fallback: surface as token-ish content.
                yield {"status": "token", "content": str(chunk)}

    async def _route_node(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        message = str(state.get("message") or "")
        session_id = str(state.get("session_id") or "")
        requested_kb = state.get("requested_kb_prefix")
        agent_type = str(state.get("agent_type") or "hybrid_agent")
        debug = bool(state.get("debug"))

        t0 = time.monotonic()
        decision = self._router.route(
            message=message,
            session_id=session_id,
            requested_kb=str(requested_kb) if requested_kb is not None else None,
            agent_type=agent_type,
        )
        routing_ms = int((time.monotonic() - t0) * 1000)

        decision_dict = (
            dataclasses.asdict(decision)
            if dataclasses.is_dataclass(decision)
            else getattr(decision, "__dict__", {})
        )
        resolved_agent_type = _resolve_agent_type(
            agent_type=agent_type, worker_name=getattr(decision, "worker_name", "")
        )
        kb_prefix = (getattr(decision, "kb_prefix", "") or "").strip() or "general"
        use_retrieval = kb_prefix not in {"", "general"}
        worker_name = str(getattr(decision, "worker_name", "") or "")

        # Frontend debug drawer expects a `selected_agent` field; keep it stable
        # even though our internal RouteDecision uses `worker_name` + `agent_type`.
        route_payload = dict(decision_dict)
        # Ensure the payload always carries the requested agent type, even when the
        # router decision object doesn't expose it.
        route_payload.setdefault("agent_type", agent_type)
        route_payload.setdefault("selected_agent", resolved_agent_type)
        # Some UIs expect `reasoning`; map from `reason` when available.
        if "reasoning" not in route_payload and "reason" in route_payload:
            route_payload["reasoning"] = route_payload.get("reason")

        if debug:
            writer = _get_stream_writer(config)
            # Keep the same cache-only event types as the SSE layer.
            writer(
                {
                    "execution_log": {
                        "node": "route_decision",
                        "node_type": "routing",
                        "duration_ms": routing_ms,
                        "input": {
                            "requested_kb_prefix": requested_kb,
                            "agent_type": agent_type,
                            "message_preview": message[:200],
                        },
                        "output": route_payload,
                    }
                }
            )
            writer({"status": "route_decision", "content": route_payload})

        return {
            "kb_prefix": kb_prefix,
            "worker_name": worker_name,
            "route_decision": route_payload,
            "routing_ms": routing_ms,
            "resolved_agent_type": resolved_agent_type,
            "use_retrieval": use_retrieval,
        }

    async def _recall_node(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        message = str(state.get("message") or "")
        debug = bool(state.get("debug"))
        incognito = bool(state.get("incognito"))

        conversation_id = state.get("conversation_id")
        current_user_message_id = state.get("current_user_message_id")

        t0 = time.monotonic()

        memory_context: str | None = None
        if not incognito and self._memory_service is not None:
            try:
                memory_context = await self._memory_service.recall_context(
                    user_id=str(state.get("user_id") or ""),
                    query=message,
                )
            except Exception:
                memory_context = None

        conversation_summary: str | None = None
        if not incognito and self._conversation_summarizer is not None and isinstance(conversation_id, UUID):
            try:
                conversation_summary = await self._conversation_summarizer.get_summary_text(
                    conversation_id=conversation_id
                )
            except Exception:
                conversation_summary = None

        raw_history = []
        try:
            raw_history = await self._conversation_store.list_messages(
                conversation_id=conversation_id, limit=8, desc=True
            )
        except Exception:
            raw_history = []

        # Recent history window (completed only); exclude current user message by id.
        history_context: list[dict[str, Any]] = []
        if isinstance(raw_history, list):
            raw_history.reverse()
            for m in raw_history:
                if not isinstance(m, dict):
                    continue
                if not m.get("completed", True):
                    continue
                if current_user_message_id is not None and m.get("id") == current_user_message_id:
                    continue
                history_context.append(m)

        episodic_memory: list[dict[str, Any]] | None = None
        episodic_context: str | None = None
        if not incognito and self._episodic_memory is not None and isinstance(conversation_id, UUID):
            try:
                exclude_ids: list[UUID] = []
                for m in history_context:
                    mid = m.get("id")
                    if isinstance(mid, UUID):
                        exclude_ids.append(mid)
                episodic_memory = await self._episodic_memory.recall_relevant(
                    conversation_id=conversation_id,
                    query=message,
                    exclude_assistant_message_ids=exclude_ids,
                )
                episodic_context = self._episodic_memory.format_context(episodes=episodic_memory)
            except Exception:
                episodic_memory = None
                episodic_context = None

        if debug:
            writer = _get_stream_writer(config)
            writer(
                {
                    "status": "conversation_summary",
                    "content": {
                        "text": conversation_summary or "",
                        "chars": len(conversation_summary or ""),
                        "present": bool((conversation_summary or "").strip()),
                    },
                }
            )
            writer({"status": "episodic_memory", "content": episodic_memory or []})
            writer(
                {
                    "execution_log": {
                        "node": "recall",
                        "node_type": "routing",
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                        "input": {"message_preview": message[:200]},
                        "output": {
                            "history_count": len(history_context),
                            "has_memory_context": bool((memory_context or "").strip()),
                            "has_summary": bool((conversation_summary or "").strip()),
                            "episodic_count": len(episodic_memory or []),
                        },
                    }
                }
            )

        return {
            "memory_context": memory_context,
            "conversation_summary": conversation_summary,
            "history": history_context,
            "episodic_memory": episodic_memory,
            "episodic_context": episodic_context,
        }

    async def _execute_node(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        stream = bool(state.get("stream"))
        debug = bool(state.get("debug"))

        kb_prefix = str(state.get("kb_prefix") or "general")
        resolved_agent_type = str(state.get("resolved_agent_type") or state.get("agent_type") or "hybrid_agent")
        message = str(state.get("message") or "")
        session_id = str(state.get("session_id") or "")

        memory_context = state.get("memory_context")
        conversation_summary = state.get("conversation_summary")
        episodic_context = state.get("episodic_context")
        history = state.get("history")

        use_retrieval = bool(state.get("use_retrieval"))
        worker_name = str(state.get("worker_name") or "")

        # Extract entities from routing decision for enrichment
        route_decision = state.get("route_decision", {})
        extracted_entities = route_decision.get("extracted_entities")

        # Optional KB handler dispatch.
        kb_handler = None
        if self._enable_kb_handlers and self._kb_handler_factory is not None:
            kb_handler = self._kb_handler_factory.get(kb_prefix)

        if stream:
            writer = _get_stream_writer(config)

            if kb_handler is not None:
                async for ev in kb_handler.process_stream(
                    message=message,
                    session_id=session_id,
                    agent_type=resolved_agent_type,
                    debug=debug,
                    memory_context=memory_context,
                    summary=conversation_summary,
                    episodic_context=episodic_context,
                    history=history,
                    extracted_entities=extracted_entities,
                ):
                    writer(ev)
                return {}

            plan: list[RagRunSpec] = []
            if use_retrieval:
                plan = [RagRunSpec(agent_type=resolved_agent_type, worker_name=worker_name)]

            async for ev in self._stream_executor.stream(
                plan=plan,
                message=message,
                session_id=session_id,
                kb_prefix=kb_prefix,
                debug=debug,
                memory_context=memory_context,
                summary=conversation_summary,
                episodic_context=episodic_context,
                history=history,
                extracted_entities=extracted_entities,
            ):
                writer(ev)
            return {}

        # Non-streaming path.
        if kb_handler is not None:
            resp = await kb_handler.process(
                message=message,
                session_id=session_id,
                agent_type=resolved_agent_type,
                debug=debug,
                memory_context=memory_context,
                summary=conversation_summary,
                episodic_context=episodic_context,
                history=history,
            )
            return {"response": resp}

        if not use_retrieval:
            answer = await self._completion.generate(
                message=message,
                memory_context=memory_context,
                summary=conversation_summary,
                episodic_context=episodic_context,
                history=history,
            )
            return {"response": {"answer": answer}}

        plan = [RagRunSpec(agent_type=resolved_agent_type, worker_name=worker_name)]
        aggregated, runs = await self._executor.run(
            plan=plan,
            message=message,
            session_id=session_id,
            kb_prefix=kb_prefix,
            debug=debug,
            memory_context=memory_context,
            summary=conversation_summary,
            episodic_context=episodic_context,
            history=history,
        )
        resp: dict[str, Any] = {"answer": aggregated.answer}
        if aggregated.reference:
            resp["reference"] = aggregated.reference
        if aggregated.retrieval_results is not None:
            resp["retrieval_results"] = aggregated.retrieval_results
        if debug:
            resp["rag_runs"] = [run.__dict__ for run in runs]
        return {"response": resp}

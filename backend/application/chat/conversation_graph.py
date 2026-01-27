from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import Any, AsyncGenerator, Callable, Optional, cast
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
from domain.chat.entities.route_decision import RouteDecision
from infrastructure.llm.completion import (
    generate_general_answer_stream,
    generate_rag_answer,
    generate_rag_answer_stream,
)


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
    request_id: str | None
    requested_kb_prefix: str | None
    debug: bool
    incognito: bool
    agent_type: str
    conversation_id: Any
    current_user_message_id: Any

    # Derived routing.
    kb_prefix: str
    worker_name: str
    route_decision: RouteDecision
    routing_ms: int
    resolved_agent_type: str
    use_retrieval: bool

    # Recall / context.
    memory_context: str | None
    conversation_summary: str | None
    history: list[dict[str, Any]]
    episodic_memory: list[dict[str, Any]] | None
    episodic_context: str | None

    # Retrieval subgraph I/O (Phase 4). Kept as first-class state keys so a
    # retrieval subgraph can run as a LangGraph node (expandable in Studio).
    query: str
    user_message_id: Any
    # Subgraph outputs.
    plan: list[dict[str, Any]] | None
    records: list[dict[str, Any]] | None
    runs: list[dict[str, Any]] | None
    merged: dict[str, Any] | None
    reflection: dict[str, Any] | None
    stop_reason: str | None

    # Optional KB handler override.
    use_kb_handler: bool

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
        # Test hooks (avoid real LLM/network calls in unit tests).
        retrieval_runner: Any | None = None,
        rag_answer_fn: Any | None = None,
        rag_answer_stream_fn: Any | None = None,
        general_answer_stream_fn: Any | None = None,
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
        self._retrieval_runner = retrieval_runner
        self._rag_answer_fn = rag_answer_fn
        self._rag_answer_stream_fn = rag_answer_stream_fn
        self._general_answer_stream_fn = general_answer_stream_fn

        self._graph = self._build_graph()

    def _build_graph(self):
        g = StateGraph(ConversationState)
        g.add_node("route", self._route_node)
        g.add_node("recall", self._recall_node)
        g.add_node("prepare_retrieval", self._prepare_retrieval_node)
        from infrastructure.rag.retrieval_subgraph import retrieval_subgraph_compiled

        # First-class subgraph: shows up as an expandable node in LangGraph Studio.
        g.add_node("retrieval_subgraph", retrieval_subgraph_compiled)
        g.add_node("generate", self._generate_node)

        g.add_edge(START, "route")
        g.add_edge("route", "recall")
        g.add_edge("recall", "prepare_retrieval")

        def _after_prepare(state: ConversationState) -> str:
            # Skip retrieval when:
            # - KB handlers are enabled and a handler exists for this kb_prefix
            # - or kb_prefix is general (no KB retrieval)
            if bool(state.get("use_kb_handler")) or (not bool(state.get("use_retrieval"))):
                return "generate"
            return "retrieval_subgraph"

        g.add_conditional_edges(
            "prepare_retrieval",
            _after_prepare,
            {
                "retrieval_subgraph": "retrieval_subgraph",
                "generate": "generate",
            },
        )
        g.add_edge("retrieval_subgraph", "generate")
        g.add_edge("generate", END)
        return g.compile()

    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        # Cast for LangGraph (it accepts dict-like inputs).
        config: RunnableConfig | None = None
        if callable(getattr(self, "_retrieval_runner", None)):
            config = {CONF: {"retrieval_runner": self._retrieval_runner, "enrichment_enabled": False}}
        return await self._graph.ainvoke(dict(state), config=config)

    async def astream_custom(self, state: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        """流式输出：支持子图事件冒泡（subgraphs=True）"""
        config: RunnableConfig | None = None
        if callable(getattr(self, "_retrieval_runner", None)):
            config = {CONF: {"retrieval_runner": self._retrieval_runner, "enrichment_enabled": False}}
        async for chunk in self._graph.astream(
            dict(state),
            config=config,
            stream_mode="custom",      # 自定义事件模式（支持 writer 发送的事件）
            subgraphs=True,            # 支持子图事件冒泡（返回 (ns, payload) 元组）
        ):
            # 当 subgraphs=True 时，LangGraph 返回 `(ns, payload)` 元组
            if isinstance(chunk, tuple) and len(chunk) == 2:
                _ns, payload = chunk
                if isinstance(payload, dict):
                    yield payload
                else:
                    yield {"status": "token", "content": str(payload)}
                continue
            if isinstance(chunk, tuple) and len(chunk) == 3:
                _ns, _mode, payload = chunk
                if isinstance(payload, dict):
                    yield payload
                else:
                    yield {"status": "token", "content": str(payload)}
                continue
            if isinstance(chunk, dict):
                yield chunk
                continue
            # Defensive fallback: surface as token-ish content.
            yield {"status": "token", "content": str(chunk)}

    async def _route_node(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        """路由节点：LLM 路由判定知识库、抽取实体、推荐 agent"""
        message = str(state.get("message") or "")
        session_id = str(state.get("session_id") or "")
        requested_kb = state.get("requested_kb_prefix")
        agent_type = str(state.get("agent_type") or "hybrid_agent")
        debug = bool(state.get("debug"))

        # ===== 1. 调用 Router 进行路由决策 =====
        t0 = time.monotonic()
        decision = self._router.route(
            message=message,
            session_id=session_id,
            requested_kb=str(requested_kb) if requested_kb is not None else None,
            agent_type=agent_type,
        )
        routing_ms = int((time.monotonic() - t0) * 1000)

        # ===== 2. 解析 agent_type（从 worker_name）=====
        resolved_agent_type = _resolve_agent_type(
            agent_type=agent_type, worker_name=decision.worker_name
        )
        kb_prefix = (decision.kb_prefix or "").strip() or "general"
        use_retrieval = kb_prefix not in {"", "general"}
        worker_name = str(decision.worker_name or "")

        # ===== 3. 准备 route_payload（用于 debug 前端展示）=====
        # Frontend debug drawer expects a `selected_agent` field; keep it stable
        # even though our internal RouteDecision uses `worker_name` + `agent_type`.
        # We still need a dict for the debug payload / frontend compatibility.
        route_payload = dataclasses.asdict(decision)
        # Ensure the payload always carries the requested agent type, even when the
        # router decision object doesn't expose it.
        route_payload.setdefault("agent_type", agent_type)
        route_payload.setdefault("selected_agent", resolved_agent_type)
        # Some UIs expect `reasoning`; map from `reason` when available.
        if "reasoning" not in route_payload and "reason" in route_payload:
            route_payload["reasoning"] = route_payload.get("reason")

        # ===== 4. 发送 debug 事件（仅 debug=True 时）=====
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
            "route_decision": decision,  # Pass the dataclass object, not the dict
            "routing_ms": routing_ms,
            "resolved_agent_type": resolved_agent_type,
            "use_retrieval": use_retrieval,
        }

    async def _recall_node(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        """召回节点：组装上下文（memory、summary、history、episodic）"""
        message = str(state.get("message") or "")
        debug = bool(state.get("debug"))
        incognito = bool(state.get("incognito"))

        conversation_id = state.get("conversation_id")
        current_user_message_id = state.get("current_user_message_id")

        t0 = time.monotonic()

        # ===== 1. 召回向量记忆（mem0）=====
        memory_context: str | None = None
        if not incognito and self._memory_service is not None:
            try:
                memory_context = await self._memory_service.recall_context(
                    user_id=str(state.get("user_id") or ""),
                    query=message,
                )
            except Exception:
                memory_context = None

        # ===== 2. 召回对话摘要 =====
        conversation_summary: str | None = None
        if not incognito and self._conversation_summarizer is not None and isinstance(conversation_id, UUID):
            try:
                conversation_summary = await self._conversation_summarizer.get_summary_text(
                    conversation_id=conversation_id
                )
            except Exception:
                conversation_summary = None

        # ===== 3. 召回对话历史（最近 8 条）=====
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

        # ===== 4. 召回情景记忆（episodic memory）=====
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

        # ===== 5. 发送 debug 事件（仅 debug=True 时）=====
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

    async def _prepare_retrieval_node(
        self, state: ConversationState, config: RunnableConfig
    ) -> dict[str, Any]:
        """检索准备节点：为 retrieval_subgraph 准备输入（State 映射）"""
        _ = config
        kb_prefix = str(state.get("kb_prefix") or "general")

        # ===== 1. 检查是否启用 KB Handler（Handler 自带编排逻辑，跳过检索子图）=====
        if self._enable_kb_handlers and self._kb_handler_factory is not None:
            handler = self._kb_handler_factory.get(kb_prefix)
            if handler is not None:
                return {"use_kb_handler": True}

        # ===== 2. 获取 route_decision（用于 enrichment/debug）=====
        route_decision = state.get("route_decision")
        if not isinstance(route_decision, RouteDecision):
            # Defensive: allow dict-like legacy objects.
            route_decision = cast(Any, route_decision)

        # ===== 3. 填充 RetrievalState 字段（子图直接运行在 ConversationState 上）=====
        # First-Class Subgraph 设计：子图作为独立节点，共享父图的 State
        return {
            "use_kb_handler": False,
            "query": str(state.get("message") or ""),
            "user_message_id": state.get("current_user_message_id"),
            "kb_prefix": kb_prefix,
            "route_decision": route_decision,
            "debug": bool(state.get("debug")),
            "session_id": str(state.get("session_id") or ""),
            "user_id": str(state.get("user_id") or "") if state.get("user_id") is not None else None,
            "request_id": str(state.get("request_id") or "") if state.get("request_id") is not None else None,
            "conversation_id": state.get("conversation_id"),
            "incognito": bool(state.get("incognito")),
            "resolved_agent_type": str(state.get("resolved_agent_type") or ""),
        }

    async def _generate_node(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        """生成节点：负责答案生成（支持 KB Handler / 通用闲聊 / RAG 检索三种模式）"""
        stream = bool(state.get("stream"))
        debug = bool(state.get("debug"))
        incognito = bool(state.get("incognito"))

        kb_prefix = str(state.get("kb_prefix") or "general")
        message = str(state.get("message") or "")
        session_id = str(state.get("session_id") or "")
        request_id = state.get("request_id")
        user_id = state.get("user_id")
        conversation_id = state.get("conversation_id")
        user_message_id = state.get("current_user_message_id")

        memory_context = state.get("memory_context")
        conversation_summary = state.get("conversation_summary")
        episodic_context = state.get("episodic_context")
        history = state.get("history")

        # ===== 分支 1：KB Handler 模式（Handler 自带完整编排逻辑）=====
        if bool(state.get("use_kb_handler")) and self._kb_handler_factory is not None:
            kb_handler = self._kb_handler_factory.get(kb_prefix)
            if kb_handler is not None:
                # Preserve router hints for enrichment/debug inside KB handlers.
                route_decision = state.get("route_decision")
                extracted_entities = None
                query_intent: str | None = None
                media_type_hint: str | None = None
                filters: dict[str, Any] | None = None
                if isinstance(route_decision, RouteDecision):
                    extracted_entities = route_decision.extracted_entities
                    query_intent = route_decision.query_intent
                    media_type_hint = route_decision.media_type_hint
                    filters = route_decision.filters
                elif isinstance(route_decision, dict):
                    extracted_entities = route_decision.get("extracted_entities")
                    query_intent = route_decision.get("query_intent")
                    media_type_hint = route_decision.get("media_type_hint")
                    raw_filters = route_decision.get("filters")
                    if isinstance(raw_filters, dict):
                        filters = raw_filters

                if stream:
                    writer = _get_stream_writer(config)
                    async for ev in kb_handler.process_stream(
                        message=message,
                        session_id=session_id,
                        agent_type=str(state.get("resolved_agent_type") or state.get("agent_type") or "hybrid_agent"),
                        debug=debug,
                        user_id=str(user_id) if user_id is not None else None,
                        request_id=str(request_id) if request_id is not None else None,
                        conversation_id=conversation_id,
                        user_message_id=user_message_id,
                        incognito=incognito,
                        memory_context=memory_context,
                        summary=conversation_summary,
                        episodic_context=episodic_context,
                        history=history,
                        extracted_entities=extracted_entities,
                        query_intent=query_intent,
                        media_type_hint=media_type_hint,
                        filters=filters,
                    ):
                        writer(ev)
                    return {}

                resp = await kb_handler.process(
                    message=message,
                    session_id=session_id,
                    agent_type=str(state.get("resolved_agent_type") or state.get("agent_type") or "hybrid_agent"),
                    debug=debug,
                    user_id=str(user_id) if user_id is not None else None,
                    request_id=str(request_id) if request_id is not None else None,
                    conversation_id=conversation_id,
                    user_message_id=user_message_id,
                    incognito=incognito,
                    memory_context=memory_context,
                    summary=conversation_summary,
                    episodic_context=episodic_context,
                    history=history,
                    extracted_entities=extracted_entities,
                    query_intent=query_intent,
                    media_type_hint=media_type_hint,
                    filters=filters,
                )
                return {"response": resp}

        # ===== 分支 2：通用闲聊模式（无检索，直接生成答案）=====
        if not bool(state.get("use_retrieval")):
            if stream:
                writer = _get_stream_writer(config)
                gen_stream = (
                    self._general_answer_stream_fn
                    if callable(getattr(self, "_general_answer_stream_fn", None))
                    else generate_general_answer_stream
                )
                generation_start = time.monotonic()
                generated_chars = 0
                chunk_count = 0
                if debug:
                    # Keep debug payload shape stable for the DebugCollector/UI:
                    # always include a rag_runs list, even when no retrieval is performed.
                    writer(
                        {
                            "status": "rag_runs",
                            "content": [
                                {"agent_type": "none", "retrieval_count": 0, "error": None}
                            ],
                        }
                    )
                writer(
                    {
                        "status": "progress",
                        "content": {
                            "stage": "generation",
                            "completed": 0,
                            "total": 1,
                            "error": None,
                            "agent_type": "",
                            "retrieval_count": None,
                        },
                    }
                )
                try:
                    async for chunk in gen_stream(
                        question=message,
                        memory_context=memory_context,
                        summary=conversation_summary,
                        episodic_context=episodic_context,
                        history=history,
                    ):
                        if not chunk:
                            continue
                        generated_chars += len(chunk)
                        chunk_count += 1
                        writer({"status": "token", "content": chunk})
                except Exception as e:
                    writer({"status": "error", "message": f"生成答案失败: {e}"})
                    writer(
                        {
                            "status": "progress",
                            "content": {
                                "stage": "generation",
                                "completed": 1,
                                "total": 1,
                                "error": str(e),
                                "agent_type": "",
                                "retrieval_count": None,
                            },
                        }
                    )
                    if debug:
                        writer(
                            {
                                "execution_log": {
                                    "node": "answer_error",
                                    "node_type": "generation",
                                    "duration_ms": int((time.monotonic() - generation_start) * 1000),
                                    "input": {"message": message, "kb_prefix": kb_prefix},
                                    "output": {"error": str(e)},
                                }
                            }
                        )
                else:
                    writer(
                        {
                            "status": "progress",
                            "content": {
                                "stage": "generation",
                                "completed": 1,
                                "total": 1,
                                "error": None,
                                "agent_type": "",
                                "retrieval_count": None,
                            },
                        }
                    )
                    if debug:
                        writer(
                            {
                                "execution_log": {
                                    "node": "answer_done",
                                    "node_type": "generation",
                                    "duration_ms": int((time.monotonic() - generation_start) * 1000),
                                    "input": {"message": message, "kb_prefix": kb_prefix},
                                    "output": {"generated_chars": generated_chars, "chunk_count": chunk_count},
                                }
                            }
                        )
                writer({"status": "done"})
                return {}

            answer = await self._completion.generate(
                message=message,
                memory_context=memory_context,
                summary=conversation_summary,
                episodic_context=episodic_context,
                history=history,
            )
            return {"response": {"answer": answer}}

        # ===== 分支 3：RAG 检索模式（基于 retrieval_subgraph 的 merged 结果生成答案）=====
        merged = state.get("merged")

        context = ""
        reference: dict[str, Any] = {}
        retrieval_results: list[dict[str, Any]] | None = None
        if merged is not None:
            if hasattr(merged, "context"):
                context = str(getattr(merged, "context") or "")
                reference = dict(getattr(merged, "reference") or {})
                rr = getattr(merged, "retrieval_results", None)
                if isinstance(rr, list):
                    retrieval_results = rr
            elif isinstance(merged, dict):
                context = str(merged.get("context") or "")
                reference = dict(merged.get("reference") or {})
                rr = merged.get("retrieval_results")
                if isinstance(rr, list):
                    retrieval_results = rr

        if stream:
            writer = _get_stream_writer(config)
            rag_stream = (
                self._rag_answer_stream_fn
                if callable(getattr(self, "_rag_answer_stream_fn", None))
                else generate_rag_answer_stream
            )
            generation_start = time.monotonic()
            generated_chars = 0
            chunk_count = 0
            error_message: str | None = None
            writer(
                {
                    "status": "progress",
                    "content": {
                        "stage": "generation",
                        "completed": 0,
                        "total": 1,
                        "error": None,
                        "agent_type": "",
                        "retrieval_count": None,
                    },
                }
            )
            try:
                async for chunk in rag_stream(
                    question=message,
                    context=context,
                    memory_context=memory_context,
                    summary=conversation_summary,
                    episodic_context=episodic_context,
                    history=history,
                ):
                    if not chunk:
                        continue
                    generated_chars += len(chunk)
                    chunk_count += 1
                    writer({"status": "token", "content": chunk})
            except Exception as e:
                error_message = str(e)
                writer({"status": "error", "message": f"生成答案失败: {e}"})
            finally:
                writer(
                    {
                        "status": "progress",
                        "content": {
                            "stage": "generation",
                            "completed": 1,
                            "total": 1,
                            "error": error_message,
                            "agent_type": "",
                            "retrieval_count": None,
                        },
                    }
                )
                if debug:
                    writer(
                        {
                            "execution_log": {
                                "node": "answer_done" if error_message is None else "answer_error",
                                "node_type": "generation",
                                "duration_ms": int((time.monotonic() - generation_start) * 1000),
                                "input": {"message_preview": message[:200], "context_chars": len(context)},
                                "output": {
                                    "generated_chars": generated_chars,
                                    "chunk_count": chunk_count,
                                    "error": error_message,
                                },
                            }
                        }
                    )
                writer({"status": "done"})
            return {}

        answer_error: str | None = None
        rag_fn = self._rag_answer_fn if callable(getattr(self, "_rag_answer_fn", None)) else generate_rag_answer
        try:
            answer = await asyncio.to_thread(
                rag_fn,
                question=message,
                context=context,
                memory_context=memory_context,
                summary=conversation_summary,
                episodic_context=episodic_context,
                history=history,
            )
        except Exception as e:
            answer_error = f"answer generation failed: {e}"
            answer = f"生成答案失败: {e}"

        resp: dict[str, Any] = {"answer": answer}
        if reference:
            resp["reference"] = reference
        if retrieval_results is not None:
            resp["retrieval_results"] = retrieval_results
        if answer_error:
            resp["error"] = answer_error

        if debug:
            # Ensure JSON-serializable for API response.
            runs = state.get("runs") or []
            if isinstance(runs, list):
                resp["rag_runs"] = [getattr(r, "__dict__", r) for r in runs]
            else:
                resp["rag_runs"] = []
            raw_plan = state.get("plan") or []
            if isinstance(raw_plan, list):
                resp["plan"] = [
                    dataclasses.asdict(p) if hasattr(p, "__dataclass_fields__") else p for p in raw_plan
                ]
            else:
                resp["plan"] = []

            raw_records = state.get("records") or []
            if isinstance(raw_records, list):
                resp["records"] = [
                    dataclasses.asdict(r) if hasattr(r, "__dataclass_fields__") else r for r in raw_records
                ]
            else:
                resp["records"] = []

            reflection = state.get("reflection")
            resp["reflection"] = (
                dataclasses.asdict(reflection)
                if hasattr(reflection, "__dataclass_fields__")
                else reflection
            )

        return {"response": resp}

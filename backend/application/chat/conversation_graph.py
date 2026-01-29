"""
ConversationGraphRunner：对话图编排器（Phase 3 Unified LangGraph）

核心功能：
1. 路由（route）：LLM 路由判定知识库、抽取实体、推荐 agent_type
2. 构建上下文（build_context）：组装上下文（memory、summary、history、episodic）
3. 检索（retrieval_subgraph）：First-Class Subgraph 执行 Plan → Execute → Reflect → Merge
4. 生成（generate）：基于检索上下文流式生成答案

架构特点：
- State 是不可变的（TypedDict），节点返回更新部分
- 支持流式输出（stream_mode="custom" + writer）
- 子图事件自动冒泡（subgraphs=True）
- 支持 KB Handler 插件机制
"""

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
    """
    从 worker_name 中解析 agent_type（Router 推荐的 agent）

    worker_name 格式（v2）: {kb_prefix}:{agent_type}:{agent_mode}
    例如：movie:hybrid_agent:default

    返回：解析后的 agent_type（例如 hybrid_agent）
    """
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
    """
    对话图 State（Phase 3：/chat 和 /chat/stream 共享）

    State 是不可变的，每个节点返回需要更新的字段（部分更新）
    """

    # ===== 1. 请求输入（Request inputs）=====
    stream: bool
    user_id: str
    message: str
    session_id: str
    request_id: str | None
    requested_kb_prefix: str | None
    debug: bool
    incognito: bool
    conversation_id: Any
    current_user_message_id: Any

    # ===== 2. 路由决策（Derived routing）=====
    # 由 route 节点填充
    kb_prefix: str
    route_decision: RouteDecision
    resolved_agent_type: str
    use_retrieval: bool

    # ===== 3. 上下文构建（Build context）=====
    # 由 build_context 节点填充
    memory_context: str | None
    conversation_summary: str | None
    history: list[dict[str, Any]]
    episodic_memory: list[dict[str, Any]] | None
    episodic_context: str | None

    # ===== 4. 检索子图 I/O（Retrieval subgraph I/O）=====
    # First-Class State Keys：子图作为 LangGraph 节点直接运行（Studio 可展开）
    # 由 prepare_retrieval 节点填充输入，retrieval_subgraph 填充输出
    query: str
    user_message_id: Any
    # Subgraph outputs.
    plan: list[dict[str, Any]] | None
    records: list[dict[str, Any]] | None
    runs: list[dict[str, Any]] | None
    merged: dict[str, Any] | None
    reflection: dict[str, Any] | None
    stop_reason: str | None

    # ===== 5. KB Handler 插件（Optional KB handler override）=====
    # 如果启用 KB Handler，跳过 retrieval_subgraph
    use_kb_handler: bool

    # ===== 6. 非流式响应（Non-streaming answer payload）=====
    # 仅用于 /chat（非流式）端点
    response: dict[str, Any]


def _get_stream_writer(config: RunnableConfig) -> Callable[[Any], None]:
    """
    从 config 中提取 writer 函数（Python 3.10 兼容）

    LangGraph 的 writer 用于发送自定义事件（stream_mode="custom"）
    官方 get_stream_writer() 依赖 Python 3.11+ 的 async contextvar
    我们直接从 config 读取，兼容 Python 3.10
    """
    try:
        writer = config.get(CONF, {}).get(CONFIG_KEY_STREAM_WRITER)
    except Exception:
        writer = None
    return writer if callable(writer) else (lambda _chunk: None)


class ConversationGraphRunner:
    """
    对话图运行器：Phase 3 Unified LangGraph 的核心编排器

    图结构：
    START → route → build_context → prepare_retrieval → [retrieval_subgraph] → generate → END
                                         ↓
                                   (跳过子图)
                                         ↓
                                     generate → END

    关键方法：
    - _build_graph(): 构建对话图
    - astream_custom(): 流式执行（支持子图事件冒泡）
    - _route_node(): LLM 路由
    - _build_context_node(): 上下文构建（召回 + 组装）
    - _prepare_retrieval_node(): State 映射
    - _generate_node(): 答案生成
    """
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

    def _build_langgraph_config(self) -> RunnableConfig | None:
        """构建 LangGraph 的运行时 config（主要用于注入测试 hook）。"""
        if callable(getattr(self, "_retrieval_runner", None)):
            # `enrichment_enabled` 由 retrieval_subgraph 内部开关决定；这里仅用于测试避免外部依赖。
            return {CONF: {"retrieval_runner": self._retrieval_runner, "enrichment_enabled": False}}
        return None

    @staticmethod
    def _normalize_stream_chunk(chunk: Any) -> dict[str, Any]:
        """
        统一处理 LangGraph astream(subgraphs=True) 的返回格式差异。

        - 可能是 dict（我们 writer 发送的自定义事件）
        - 可能是二元组 (ns, payload)
        - 可能是三元组 (ns, mode, payload)
        - 其他情况：兜底当作 token 输出
        """
        if isinstance(chunk, tuple) and len(chunk) == 2:
            _ns, payload = chunk
            if isinstance(payload, dict):
                return payload
            return {"status": "token", "content": str(payload)}
        if isinstance(chunk, tuple) and len(chunk) == 3:
            _ns, _mode, payload = chunk
            if isinstance(payload, dict):
                return payload
            return {"status": "token", "content": str(payload)}
        if isinstance(chunk, dict):
            return chunk
        return {"status": "token", "content": str(chunk)}

    @staticmethod
    def _extract_router_hints(
        route_decision: RouteDecision | dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, str | None, str | None, dict[str, Any] | None]:
        """
        从 route_decision 中提取 enrichment/检索所需的提示字段（兼容 dataclass/dict）。

        返回：(extracted_entities, query_intent, media_type_hint, filters)
        """
        extracted_entities: dict[str, Any] | None = None
        query_intent: str | None = None
        media_type_hint: str | None = None
        filters: dict[str, Any] | None = None

        if isinstance(route_decision, RouteDecision):
            extracted_entities = (
                route_decision.extracted_entities
                if isinstance(route_decision.extracted_entities, dict)
                else None
            )
            query_intent = str(route_decision.query_intent or "").strip() or None
            media_type_hint = str(route_decision.media_type_hint or "").strip() or None
            filters = route_decision.filters if isinstance(route_decision.filters, dict) else None
            return extracted_entities, query_intent, media_type_hint, filters

        if isinstance(route_decision, dict):
            ee = route_decision.get("extracted_entities")
            if isinstance(ee, dict):
                extracted_entities = ee
            qi = route_decision.get("query_intent")
            if isinstance(qi, str) and qi.strip():
                query_intent = qi.strip()
            mt = route_decision.get("media_type_hint")
            if isinstance(mt, str) and mt.strip():
                media_type_hint = mt.strip()
            rf = route_decision.get("filters")
            if isinstance(rf, dict):
                filters = rf

        return extracted_entities, query_intent, media_type_hint, filters

    @staticmethod
    def _extract_merged_payload(
        merged: Any,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]] | None]:
        """从 merger 输出中提取 (context, reference, retrieval_results)，兼容对象/字典两种形态。"""
        context = ""
        reference: dict[str, Any] = {}
        retrieval_results: list[dict[str, Any]] | None = None

        if merged is None:
            return context, reference, retrieval_results

        if hasattr(merged, "context"):
            context = str(getattr(merged, "context") or "")
            reference = dict(getattr(merged, "reference") or {})
            rr = getattr(merged, "retrieval_results", None)
            if isinstance(rr, list):
                retrieval_results = rr
            return context, reference, retrieval_results

        if isinstance(merged, dict):
            context = str(merged.get("context") or "")
            reference = dict(merged.get("reference") or {})
            rr = merged.get("retrieval_results")
            if isinstance(rr, list):
                retrieval_results = rr

        return context, reference, retrieval_results

    def _build_graph(self):
        """
        构建对话图（LangGraph StateGraph）

        图结构：
        - route: LLM 路由（判定 kb_prefix、抽取实体、推荐 agent）
        - build_context: 构建上下文（memory、summary、history、episodic）
        - prepare_retrieval: State 映射（ConversationState → RetrievalState）
        - retrieval_subgraph: 检索子图（First-Class Subgraph）
        - generate: 答案生成（RAG / general）

        条件边：
        - prepare_retrieval → retrieval_subgraph：需要检索
        - prepare_retrieval → generate：跳过检索（KB Handler / general KB）
        """
        g = StateGraph(ConversationState)
        g.add_node("route", self._route_node)
        g.add_node("build_context", self._build_context_node)
        g.add_node("prepare_retrieval", self._prepare_retrieval_node)
        from infrastructure.rag.retrieval_subgraph import retrieval_subgraph_compiled

        # First-class subgraph: shows up as an expandable node in LangGraph Studio.
        g.add_node("retrieval_subgraph", retrieval_subgraph_compiled)
        g.add_node("generate", self._generate_node)

        g.add_edge(START, "route")
        g.add_edge("route", "build_context")
        g.add_edge("build_context", "prepare_retrieval")

        def _after_prepare(state: ConversationState) -> str:
            """
            条件边逻辑：决定是否进入检索子图

            跳过检索的情况：
            - 启用了 KB Handler（Handler 自带编排逻辑）
            - kb_prefix 是 general（通用闲聊，无需检索）
            """
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
        """
        非流式执行：用于 /chat 端点

        返回完整的 State（包含 response 字段）
        """
        # Cast for LangGraph (it accepts dict-like inputs).
        config = self._build_langgraph_config()
        return await self._graph.ainvoke(dict(state), config=config)

    async def astream_custom(self, state: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        """
        流式执行：用于 /chat/stream 端点

        特性：
        - 支持子图事件冒泡（subgraphs=True）
        - 自定义事件模式（stream_mode="custom"）
        - 实时推送 token/progress/debug 事件

        事件格式：
        - token: {"status": "token", "content": "..."}
        - progress: {"status": "progress", "content": {"stage": "...", ...}}
        - debug: {"execution_log": {...}, "status": "...", "content": {...}}
        - done: {"status": "done"}
        """
        config = self._build_langgraph_config()
        async for chunk in self._graph.astream(
            dict(state),
            config=config,
            stream_mode="custom",      # 自定义事件模式（支持 writer 发送的事件）
            subgraphs=True,            # 支持子图事件冒泡（返回 (ns, payload) 元组）
        ):
            yield self._normalize_stream_chunk(chunk)

    async def _route_node(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        """路由节点：LLM 路由判定知识库、抽取实体、推荐 agent"""
        message = str(state.get("message") or "")
        session_id = str(state.get("session_id") or "")
        requested_kb = state.get("requested_kb_prefix")
        debug = bool(state.get("debug"))

        # ===== 1. 调用 Router 进行路由决策 =====
        t0 = time.monotonic()
        decision = self._router.route(
            message=message,
            session_id=session_id,
            requested_kb=str(requested_kb) if requested_kb is not None else None,
        )
        routing_ms = int((time.monotonic() - t0) * 1000)

        # ===== 2. 解析 agent_type（从 worker_name）=====
        resolved_agent_type = _resolve_agent_type(agent_type="hybrid_agent", worker_name=decision.worker_name)
        kb_prefix = (decision.kb_prefix or "").strip() or "general"
        use_retrieval = kb_prefix not in {"", "general"}

        # ===== 3. 准备 route_payload（用于 debug 前端展示）=====
        # Frontend debug drawer expects a `selected_agent` field.
        route_payload = dataclasses.asdict(decision)
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
                            "message_preview": message[:200],
                        },
                        "output": route_payload,
                    }
                }
            )
            writer({"status": "route_decision", "content": route_payload})

        return {
            "kb_prefix": kb_prefix,
            "route_decision": decision,  # Pass the dataclass object, not the dict
            "resolved_agent_type": resolved_agent_type,
            "use_retrieval": use_retrieval,
        }

    async def _build_context_node(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        """构建上下文节点：召回并组装上下文（memory、summary、history、episodic（情节记忆））"""
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
                        "node": "build_context",
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

        # ===== 2. 最小化子图输入：只补齐子图需要但父图 state 没有的字段 =====
        # 说明：retrieval_subgraph 是 first-class subgraph，会直接读取父图 state 中已有的
        # user_id/session_id/request_id/route_decision/resolved_agent_type 等字段。
        # 因此这里只设置：use_kb_handler/query/user_message_id（以及必要的类型兜底）。
        route_decision = state.get("route_decision")
        if not isinstance(route_decision, RouteDecision):
            # Defensive: allow dict-like legacy objects.
            route_decision = cast(Any, route_decision)

        return {
            "use_kb_handler": False,
            "query": str(state.get("message") or ""),
            "user_message_id": state.get("current_user_message_id"),
            "route_decision": route_decision,
        }

    @staticmethod
    def _emit_progress(
        writer: Callable[[Any], None],
        *,
        stage: str,
        completed: int,
        total: int,
        error: str | None,
        agent_type: str = "",
        retrieval_count: int | None = None,
    ) -> None:
        """统一 progress 事件的输出格式，避免各分支重复拼 payload。"""
        writer(
            {
                "status": "progress",
                "content": {
                    "stage": stage,
                    "completed": completed,
                    "total": total,
                    "error": error,
                    "agent_type": agent_type,
                    "retrieval_count": retrieval_count,
                },
            }
        )

    @staticmethod
    def _emit_execution_log(
        writer: Callable[[Any], None],
        *,
        node: str,
        node_type: str,
        duration_ms: int,
        input: dict[str, Any],
        output: dict[str, Any],
    ) -> None:
        """统一 execution_log 的输出格式，便于 DebugCollector/UI 做时间线聚合。"""
        writer(
            {
                "execution_log": {
                    "node": node,
                    "node_type": node_type,
                    "duration_ms": duration_ms,
                    "input": input,
                    "output": output,
                }
            }
        )

    async def _generate_with_kb_handler(
        self,
        *,
        state: ConversationState,
        config: RunnableConfig,
        kb_prefix: str,
        message: str,
        session_id: str,
        resolved_agent_type: str,
        debug: bool,
        incognito: bool,
        user_id: Any,
        request_id: Any,
        conversation_id: Any,
        user_message_id: Any,
        memory_context: str | None,
        conversation_summary: str | None,
        episodic_context: str | None,
        history: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        """
        KB Handler 分支：由 handler 自己完成检索/生成（主图只负责透传上下文与路由提示）。

        返回：
        - 命中 handler 且非流式：{"response": ...}
        - 命中 handler 且流式：{}（事件通过 writer 输出）
        - 未命中 handler：None（继续走后续分支）
        """
        if not bool(state.get("use_kb_handler")) or self._kb_handler_factory is None:
            return None
        kb_handler = self._kb_handler_factory.get(kb_prefix)
        if kb_handler is None:
            return None

        # Preserve router hints for enrichment/debug inside KB handlers.
        route_decision = state.get("route_decision")
        extracted_entities, query_intent, media_type_hint, filters = self._extract_router_hints(
            route_decision if isinstance(route_decision, (RouteDecision, dict)) else None
        )

        if bool(state.get("stream")):
            writer = _get_stream_writer(config)
            async for ev in kb_handler.process_stream(
                message=message,
                session_id=session_id,
                agent_type=resolved_agent_type,
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
            agent_type=resolved_agent_type,
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

    async def _generate_general_answer(
        self,
        *,
        message: str,
        memory_context: str | None,
        conversation_summary: str | None,
        episodic_context: str | None,
        history: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """通用闲聊（非流式）：无检索，直接生成答案。"""
        answer = await self._completion.generate(
            message=message,
            memory_context=memory_context,
            summary=conversation_summary,
            episodic_context=episodic_context,
            history=history,
        )
        return {"response": {"answer": answer}}

    async def _generate_general_stream(
        self,
        *,
        message: str,
        kb_prefix: str,
        debug: bool,
        memory_context: str | None,
        conversation_summary: str | None,
        episodic_context: str | None,
        history: list[dict[str, Any]] | None,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """通用闲聊（流式）：输出 token/progress/（debug 时）execution_log。"""
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
            writer({"status": "rag_runs", "content": [{"agent_type": "none", "retrieval_count": 0, "error": None}]})

        self._emit_progress(writer, stage="generation", completed=0, total=1, error=None, agent_type="", retrieval_count=None)

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
            err = str(e)
            writer({"status": "error", "message": f"生成答案失败: {e}"})
            self._emit_progress(writer, stage="generation", completed=1, total=1, error=err, agent_type="", retrieval_count=None)
            if debug:
                self._emit_execution_log(
                    writer,
                    node="answer_error",
                    node_type="generation",
                    duration_ms=int((time.monotonic() - generation_start) * 1000),
                    input={"message": message, "kb_prefix": kb_prefix},
                    output={"error": err},
                )
        else:
            self._emit_progress(writer, stage="generation", completed=1, total=1, error=None, agent_type="", retrieval_count=None)
            if debug:
                self._emit_execution_log(
                    writer,
                    node="answer_done",
                    node_type="generation",
                    duration_ms=int((time.monotonic() - generation_start) * 1000),
                    input={"message": message, "kb_prefix": kb_prefix},
                    output={"generated_chars": generated_chars, "chunk_count": chunk_count},
                )

        writer({"status": "done"})
        return {}

    async def _generate_rag_stream(
        self,
        *,
        message: str,
        context: str,
        debug: bool,
        memory_context: str | None,
        conversation_summary: str | None,
        episodic_context: str | None,
        history: list[dict[str, Any]] | None,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """RAG（流式）：基于 merged.context 生成答案并输出 token/progress/（debug 时）execution_log。"""
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

        self._emit_progress(writer, stage="generation", completed=0, total=1, error=None, agent_type="", retrieval_count=None)
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
            self._emit_progress(
                writer,
                stage="generation",
                completed=1,
                total=1,
                error=error_message,
                agent_type="",
                retrieval_count=None,
            )
            if debug:
                self._emit_execution_log(
                    writer,
                    node="answer_done" if error_message is None else "answer_error",
                    node_type="generation",
                    duration_ms=int((time.monotonic() - generation_start) * 1000),
                    input={"message_preview": message[:200], "context_chars": len(context)},
                    output={"generated_chars": generated_chars, "chunk_count": chunk_count, "error": error_message},
                )
            writer({"status": "done"})
        return {}

    async def _generate_rag_answer(
        self,
        *,
        state: ConversationState,
        message: str,
        context: str,
        reference: dict[str, Any],
        retrieval_results: list[dict[str, Any]] | None,
        memory_context: str | None,
        conversation_summary: str | None,
        episodic_context: str | None,
        history: list[dict[str, Any]] | None,
        debug: bool,
    ) -> dict[str, Any]:
        """RAG（非流式）：基于 merged.context 生成答案，并在 debug 时附带 plan/runs/records/reflection。"""
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

        resolved_agent_type = str(state.get("resolved_agent_type") or "hybrid_agent")

        # ===== 分支 1：KB Handler 模式（Handler 自带完整编排逻辑）=====
        handler_out = await self._generate_with_kb_handler(
            state=state,
            config=config,
            kb_prefix=kb_prefix,
            message=message,
            session_id=session_id,
            resolved_agent_type=resolved_agent_type,
            debug=debug,
            incognito=incognito,
            user_id=user_id,
            request_id=request_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            memory_context=memory_context,
            conversation_summary=conversation_summary,
            episodic_context=episodic_context,
            history=history,
        )
        if handler_out is not None:
            return handler_out

        # ===== 分支 2：通用闲聊模式（无检索，直接生成答案）=====
        if not bool(state.get("use_retrieval")):
            if stream:
                return await self._generate_general_stream(
                    message=message,
                    kb_prefix=kb_prefix,
                    debug=debug,
                    memory_context=memory_context,
                    conversation_summary=conversation_summary,
                    episodic_context=episodic_context,
                    history=history,
                    config=config,
                )
            return await self._generate_general_answer(
                message=message,
                memory_context=memory_context,
                conversation_summary=conversation_summary,
                episodic_context=episodic_context,
                history=history,
            )

        # ===== 分支 3：RAG 检索模式（基于 retrieval_subgraph 的 merged 结果生成答案）=====
        merged = state.get("merged")
        context, reference, retrieval_results = self._extract_merged_payload(merged)

        if stream:
            return await self._generate_rag_stream(
                message=message,
                context=context,
                debug=debug,
                memory_context=memory_context,
                conversation_summary=conversation_summary,
                episodic_context=episodic_context,
                history=history,
                config=config,
            )
        return await self._generate_rag_answer(
            state=state,
            message=message,
            context=context,
            reference=reference,
            retrieval_results=retrieval_results,
            memory_context=memory_context,
            conversation_summary=conversation_summary,
            episodic_context=episodic_context,
            history=history,
            debug=debug,
        )

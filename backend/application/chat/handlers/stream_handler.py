from __future__ import annotations

import dataclasses
import time
from typing import Any, AsyncGenerator, Optional

from application.handlers.factory import KnowledgeBaseHandlerFactory
from application.chat.memory_service import MemoryService
from application.ports.conversation_store_port import ConversationStorePort
from application.ports.rag_stream_executor_port import RAGStreamExecutorPort
from application.ports.router_port import RouterPort
from domain.chat.entities.rag_run import RagRunSpec


def _resolve_agent_type(*, agent_type: str, worker_name: str) -> str:
    """从 Router 输出推导最终使用的 agent_type。

    RouterGraph 可能返回两种形态的 `worker_name`：
    - "<kb_prefix>:<agent_type>"（推荐：显式、可读）
    - "<agent_type>"（历史/简化形态）

    这里做兼容解析，避免新旧 worker_name 约定不一致导致路由失效。
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


class StreamHandler:
    def __init__(
        self,
        *,
        router: RouterPort,
        executor: RAGStreamExecutorPort,
        conversation_store: ConversationStorePort,
        memory_service: MemoryService | None = None,
        kb_handler_factory: Optional[KnowledgeBaseHandlerFactory] = None,
        enable_kb_handlers: bool = False,
    ) -> None:
        self._router = router
        self._executor = executor
        self._conversation_store = conversation_store
        self._memory_service = memory_service
        self._kb_handler_factory = kb_handler_factory
        self._enable_kb_handlers = enable_kb_handlers

    async def handle(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        kb_prefix: Optional[str] = None,
        debug: bool = False,
        agent_type: str = "hybrid_agent",
    ) -> AsyncGenerator[dict[str, Any], None]:
        conversation_id = await self._conversation_store.get_or_create_conversation_id(
            user_id=user_id,
            session_id=session_id,
        )
        await self._conversation_store.append_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
        )

        tokens: list[str] = []
        completed_normally = False

        async def _track_and_yield(
            source: AsyncGenerator[dict[str, Any], None],
        ) -> AsyncGenerator[dict[str, Any], None]:
            nonlocal completed_normally
            async for event in source:
                if isinstance(event, dict) and event.get("status") == "token":
                    tokens.append(str(event.get("content") or ""))
                if isinstance(event, dict) and event.get("status") == "done":
                    completed_normally = True
                yield event

        # SSE 的 application 层编排职责（不做 IO，只做“调用顺序/分流”）：
        # 1) route：得到 kb_prefix / worker_name（含置信度/降级策略）
        # 2) 可选：命中 KB 专用 handler（Phase2 开关），绕过通用 RAG 执行器
        # 3) 组装 RAG plan（或空 plan 表示 general）并委托给 stream executor 产出事件流
        t0 = time.monotonic()
        decision = self._router.route(
            message=message,
            session_id=session_id,
            requested_kb=kb_prefix,
            agent_type=agent_type,
        )
        routing_ms = int((time.monotonic() - t0) * 1000)

        # Cache-only debug event (not required for streaming UX).
        # Note: RouteDecision is a dataclass; convert to plain dict for JSON.
        if debug:
            # Also emit a trace-friendly execution_log node so performance metrics
            # can attribute routing time (duration_ms) without changing the RouteDecision schema.
            yield {
                "status": "execution_log",
                "content": {
                    "node": "route_decision",
                    "node_type": "routing",
                    "duration_ms": routing_ms,
                    "input": {
                        "requested_kb_prefix": kb_prefix,
                        "agent_type": agent_type,
                    },
                    "output": dataclasses.asdict(decision),
                },
            }
            yield {"status": "route_decision", "content": dataclasses.asdict(decision)}

        resolved_agent_type = _resolve_agent_type(
            agent_type=agent_type,
            worker_name=decision.worker_name,
        )
        # "" / "general" 代表“无需检索”：走纯 LLM 生成（仍走统一 SSE 协议/事件管道）。
        use_retrieval = (decision.kb_prefix or "").strip() not in {"", "general"}

        memory_context: str | None = None
        if self._memory_service is not None:
            memory_context = await self._memory_service.recall_context(
                user_id=user_id,
                query=message,
            )

        if self._enable_kb_handlers and self._kb_handler_factory is not None:
            # 某些 KB 有专用 handler（自定义 plan/fanout/格式化），可以绕过通用 RAG 执行器；
            # 这样能把“领域差异”封装在 handler 内，避免 HTTP 层和通用编排被污染。
            kb_handler = self._kb_handler_factory.get(decision.kb_prefix)
            if kb_handler is not None:
                async for event in _track_and_yield(
                    kb_handler.process_stream(
                        message=message,
                        session_id=session_id,
                        agent_type=resolved_agent_type,
                        debug=debug,
                        memory_context=memory_context,
                    )
                ):
                    yield event
                # Persist assistant message once streaming finishes.
                answer = "".join(tokens).strip()
                if answer:
                    await self._conversation_store.append_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=answer,
                        debug={"partial": not completed_normally} if debug else None,
                    )
                    if self._memory_service is not None and completed_normally:
                        await self._memory_service.maybe_write(
                            user_id=user_id,
                            user_message=message,
                            assistant_message=answer,
                            metadata={"session_id": session_id, "kb_prefix": decision.kb_prefix},
                        )
                return

        # 这里的空 plan 是“刻意设计”：infra 的 ChatStreamExecutor 会把空 plan 当作 general 生成，
        # 从而保证“RAG 与非 RAG”共用同一套 SSE 事件协议/返回通道。
        plan: list[RagRunSpec] = []
        if use_retrieval:
            plan = [
                RagRunSpec(
                    agent_type=resolved_agent_type,
                    worker_name=decision.worker_name,
                )
            ]
        try:
            async for event in _track_and_yield(
                self._executor.stream(
                    plan=plan,
                    message=message,
                    session_id=session_id,
                    kb_prefix=decision.kb_prefix,
                    debug=debug,
                    memory_context=memory_context,
                )
            ):
                yield event
        finally:
            # Persist assistant message once the stream ends (including client aborts).
            answer = "".join(tokens).strip()
            if answer:
                await self._conversation_store.append_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                    debug={"partial": not completed_normally} if debug else None,
                )
                if self._memory_service is not None and completed_normally:
                    await self._memory_service.maybe_write(
                        user_id=user_id,
                        user_message=message,
                        assistant_message=answer,
                        metadata={"session_id": session_id, "kb_prefix": decision.kb_prefix},
                    )

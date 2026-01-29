from __future__ import annotations

import dataclasses
from typing import Any, Optional

from application.chat.conversation_graph import ConversationGraphRunner
from application.chat.memory_service import MemoryService
from application.chat.watchlist_capture_service import WatchlistCaptureService
from application.handlers.factory import KnowledgeBaseHandlerFactory
from application.ports.chat_completion_port import ChatCompletionPort
from application.ports.conversation_episodic_memory_port import ConversationEpisodicMemoryPort
from application.ports.conversation_store_port import ConversationStorePort
from application.ports.conversation_summarizer_port import ConversationSummarizerPort
from application.ports.rag_executor_port import RAGExecutorPort
from application.ports.rag_stream_executor_port import RAGStreamExecutorPort
from application.ports.router_port import RouterPort
from domain.chat.entities.route_decision import RouteDecision


class ChatHandler:
    """
    非流式聊天入口（/api/v1/chat）。

    这里的职责是“编排 + 持久化 + 触发后处理”，核心检索/生成逻辑都在 ConversationGraphRunner（LangGraph 主图）里。

    主链路阶段（非流式）：
    1) 会话/消息持久化：写入 user message
    2) 执行 LangGraph：route -> recall -> retrieval_subgraph(可选) -> generate
    3) 持久化 assistant message（可选 debug/citations）
    4) 触发后处理（best-effort）：summary/episodic/mem0/watchlist
    5) 组装 response：兼容既有 ChatResponse 返回结构
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
        watchlist_capture: WatchlistCaptureService | None = None,
        kb_handler_factory: Optional[KnowledgeBaseHandlerFactory] = None,
        enable_kb_handlers: bool = False,
        # Test hooks (avoid real LLM/network calls in unit tests).
        retrieval_runner: Any | None = None,
        rag_answer_fn: Any | None = None,
        rag_answer_stream_fn: Any | None = None,
        general_answer_stream_fn: Any | None = None,
    ) -> None:
        self._conversation_store = conversation_store
        self._memory_service = memory_service
        self._conversation_summarizer = conversation_summarizer
        self._episodic_memory = episodic_memory
        self._watchlist_capture = watchlist_capture

        self._graph = ConversationGraphRunner(
            router=router,
            executor=executor,
            stream_executor=stream_executor,
            completion=completion,
            conversation_store=conversation_store,
            memory_service=memory_service,
            conversation_summarizer=conversation_summarizer,
            episodic_memory=episodic_memory,
            kb_handler_factory=kb_handler_factory,
            enable_kb_handlers=enable_kb_handlers,
            retrieval_runner=retrieval_runner,
            rag_answer_fn=rag_answer_fn,
            rag_answer_stream_fn=rag_answer_stream_fn,
            general_answer_stream_fn=general_answer_stream_fn,
        )

    async def handle(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        kb_prefix: Optional[str] = None,
        debug: bool = False,
        incognito: bool = False,
        watchlist_auto_capture: bool | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        处理一次非流式聊天请求。

        注意：
        - agent 选择/路由不在这里做（由 router + LangGraph 完成）
        - 后处理均为 best-effort：失败不会影响本次回答返回
        """
        incognito = bool(incognito)

        # 1) 会话准备 + 持久化用户消息（保证后续任何异常都不会丢 user message）
        conversation_id, user_message_id = await self._prepare_conversation(
            user_id=user_id,
            session_id=session_id,
            user_message=message,
        )

        # 2) 执行 LangGraph 主图，得到最终 state（其中包含 response / route_decision 等）
        final_state = await self._run_graph(
            user_id=user_id,
            session_id=session_id,
            user_message=message,
            requested_kb_prefix=kb_prefix,
            debug=bool(debug),
            incognito=incognito,
            request_id=request_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
        )

        # 3) 取出图的最终 response（防御：缺失时给空 answer），并序列化 route_decision 供 debug/存储使用
        graph_response = self._extract_graph_response(final_state)
        answer = str(graph_response.get("answer") or "")
        route_decision_payload = self._serialize_route_decision(final_state)

        watchlist_added: list[dict[str, Any]] = []

        # 4) 持久化 assistant message，并触发后处理（best-effort）
        if answer:
            assistant_message_id = await self._persist_assistant_message(
                conversation_id=conversation_id,
                answer=answer,
                debug=bool(debug),
                reference=graph_response.get("reference"),
                route_decision_payload=route_decision_payload,
                rag_runs=graph_response.get("rag_runs"),
            )

            await self._run_side_effects(
                user_id=user_id,
                session_id=session_id,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                user_message=message,
                answer=answer,
                incognito=incognito,
                requested_kb_prefix=kb_prefix,
                final_state=final_state,
                watchlist_auto_capture=watchlist_auto_capture,
                watchlist_added_out=watchlist_added,
            )

        # 5) 组装 HTTP 返回 payload（保持既有 response contract）
        return self._build_response_payload(
            answer=answer,
            debug=bool(debug),
            graph_response=graph_response,
            final_state=final_state,
            route_decision_payload=route_decision_payload,
            watchlist_added=watchlist_added,
        )

    async def _prepare_conversation(
        self,
        *,
        user_id: str,
        session_id: str,
        user_message: str,
    ) -> tuple[Any, Any]:
        """准备会话并写入 user 消息，返回 (conversation_id, user_message_id)。"""
        conversation_id = await self._conversation_store.get_or_create_conversation_id(
            user_id=user_id,
            session_id=session_id,
        )
        user_message_id = await self._conversation_store.append_message(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
            completed=True,
        )
        return conversation_id, user_message_id

    async def _run_graph(
        self,
        *,
        user_id: str,
        session_id: str,
        user_message: str,
        requested_kb_prefix: Optional[str],
        debug: bool,
        incognito: bool,
        request_id: str | None,
        conversation_id: Any,
        user_message_id: Any,
    ) -> dict[str, Any]:
        """执行 LangGraph 主图（非流式），返回最终 state（dict）。"""
        final = await self._graph.ainvoke(
            {
                "stream": False,
                "user_id": user_id,
                "message": user_message,
                "session_id": session_id,
                "request_id": request_id,
                "requested_kb_prefix": requested_kb_prefix,
                "debug": bool(debug),
                "incognito": bool(incognito),
                "conversation_id": conversation_id,
                "current_user_message_id": user_message_id,
            }
        )
        return final if isinstance(final, dict) else {}

    @staticmethod
    def _extract_graph_response(final_state: dict[str, Any]) -> dict[str, Any]:
        """从 state 中提取 response，保持下游对 answer 字段的基本假设。"""
        resp = final_state.get("response")
        return resp if isinstance(resp, dict) else {"answer": ""}

    @staticmethod
    def _serialize_route_decision(final_state: dict[str, Any]) -> dict[str, Any] | None:
        """将 RouteDecision（dataclass）转为 dict，便于落库/返回给 debug UI。"""
        raw = final_state.get("route_decision")
        if isinstance(raw, RouteDecision):
            return dataclasses.asdict(raw)
        if isinstance(raw, dict):
            return raw
        return None

    async def _persist_assistant_message(
        self,
        *,
        conversation_id: Any,
        answer: str,
        debug: bool,
        reference: Any,
        route_decision_payload: dict[str, Any] | None,
        rag_runs: Any,
    ) -> Any:
        """持久化 assistant message（debug=true 时写入 citations/debug 字段）。"""
        return await self._conversation_store.append_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            citations=reference if debug else None,
            debug={"route_decision": route_decision_payload, "rag_runs": rag_runs} if debug else None,
            completed=True,
        )

    async def _run_side_effects(
        self,
        *,
        user_id: str,
        session_id: str,
        conversation_id: Any,
        user_message_id: Any,
        assistant_message_id: Any,
        user_message: str,
        answer: str,
        incognito: bool,
        requested_kb_prefix: Optional[str],
        final_state: dict[str, Any],
        watchlist_auto_capture: bool | None,
        watchlist_added_out: list[dict[str, Any]],
    ) -> None:
        """
        后处理副作用（best-effort，不影响主链路回答）。

        - summary：Phase 1 对话摘要更新
        - episodic：Phase 2 情节记忆索引
        - mem0：长期记忆写入（可选）
        - watchlist：待看片单自动捕获（可选，且可被请求参数禁用）
        """
        if incognito:
            return

        if self._conversation_summarizer is not None:
            try:
                await self._conversation_summarizer.schedule_update(conversation_id=conversation_id)
            except Exception:
                pass

        if self._episodic_memory is not None:
            try:
                await self._episodic_memory.schedule_index_episode(
                    conversation_id=conversation_id,
                    user_message_id=user_message_id,
                    assistant_message_id=assistant_message_id,
                    user_message=user_message,
                    assistant_message=answer,
                )
            except Exception:
                pass

        if self._memory_service is not None:
            try:
                await self._memory_service.maybe_write(
                    user_id=user_id,
                    user_message=user_message,
                    assistant_message=answer,
                    metadata={"session_id": session_id, "kb_prefix": final_state.get("kb_prefix")},
                )
            except Exception:
                pass

        allow_watchlist = (watchlist_auto_capture is not False) and (not incognito)
        if allow_watchlist and self._watchlist_capture is not None:
            try:
                res = await self._watchlist_capture.maybe_capture(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message_id=user_message_id,
                    assistant_message_id=assistant_message_id,
                    user_message=user_message,
                    assistant_message=answer,
                )
                for it in res.added or []:
                    meta = it.metadata if isinstance(getattr(it, "metadata", None), dict) else {}
                    watchlist_added_out.append(
                        {
                            "id": str(it.id),
                            "title": it.title,
                            "year": it.year,
                            "status": getattr(it, "status", "to_watch"),
                            "source": meta.get("source"),
                            "capture_trigger": meta.get("capture_trigger"),
                            "capture_origin": meta.get("capture_origin"),
                            "capture_evidence": meta.get("capture_evidence"),
                            "conversation_id": meta.get("conversation_id"),
                            "user_message_id": meta.get("user_message_id"),
                            "assistant_message_id": meta.get("assistant_message_id"),
                        }
                    )
            except Exception:
                pass

    @staticmethod
    def _build_response_payload(
        *,
        answer: str,
        debug: bool,
        graph_response: dict[str, Any],
        final_state: dict[str, Any],
        route_decision_payload: dict[str, Any] | None,
        watchlist_added: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """组装最终响应：保持既有 ChatResponse contract，避免前端/测试回归。"""
        out: dict[str, Any] = {"answer": answer, "debug": bool(debug)}
        if watchlist_added:
            out["watchlist_auto_capture"] = {"added": watchlist_added}
        if graph_response.get("reference") is not None:
            out["reference"] = graph_response.get("reference")
        if graph_response.get("retrieval_results") is not None:
            out["retrieval_results"] = graph_response.get("retrieval_results")
        if debug:
            out["route_decision"] = route_decision_payload
            out["rag_runs"] = graph_response.get("rag_runs") or []
            out["episodic_memory"] = final_state.get("episodic_memory")
        return out

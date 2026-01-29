from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Optional

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


class StreamHandler:
    """Phase 3: unified orchestration for the streaming endpoint."""

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
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式处理主入口：负责持久化、编排对话图、后处理"""
        incognito = bool(incognito)

        # ===== 阶段 1：获取/创建会话 =====
        t0 = time.monotonic()
        conversation_id = await self._conversation_store.get_or_create_conversation_id(
            user_id=user_id,
            session_id=session_id,
        )
        if debug:
            yield {
                "execution_log": {
                    "node": "conversation_get_or_create",
                    "node_type": "persistence",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "input": {"user_id": user_id, "session_id": session_id},
                    "output": {"conversation_id": str(conversation_id)},
                }
            }

        # ===== 阶段 2：持久化用户消息 =====
        t0 = time.monotonic()
        current_user_message_id = await self._conversation_store.append_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
            completed=True,
        )
        if debug:
            yield {
                "execution_log": {
                    "node": "persist_user_message",
                    "node_type": "persistence",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "input": {"conversation_id": str(conversation_id), "role": "user"},
                    "output": {"message_id": str(current_user_message_id)},
                }
            }

        # ===== 阶段 3：调用对话图（route → recall → retrieval_subgraph → generate）=====
        tokens: list[str] = []
        completed_normally = False
        pending_done_event: dict[str, Any] | None = None

        try:
            async for event in self._graph.astream_custom(
                {
                    "stream": True,
                    "user_id": user_id,
                    "message": message,
                    "session_id": session_id,
                    "request_id": request_id,
                    "requested_kb_prefix": kb_prefix,
                    "debug": bool(debug),
                    "incognito": incognito,
                    "conversation_id": conversation_id,
                    "current_user_message_id": current_user_message_id,
                }
            ):
                # 累积 token（用于后续持久化）
                if isinstance(event, dict) and event.get("status") == "token":
                    tokens.append(str(event.get("content") or ""))

                # 延迟发 送 done 事件（需要先完成后处理：持久化、watchlist 捕获等）
                if isinstance(event, dict) and event.get("status") == "done":
                    # Delay the terminal "done" until we've persisted messages and
                    # emitted any post-turn UX events (e.g., watchlist auto-capture).
                    completed_normally = True
                    pending_done_event = event
                    break

                # 透传所有事件到 SSE 层
                yield event
        finally:
            # Best-effort persistence on generator close / cancellation.
            if pending_done_event is None and not tokens:
                return

        # ===== 阶段 4：持久化助手消息 =====
        answer = "".join(tokens).strip()
        if not answer:
            if pending_done_event is not None:
                yield pending_done_event
            return

        t0 = time.monotonic()
        assistant_message_id = await self._conversation_store.append_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            debug={"partial": not completed_normally} if debug else None,
            completed=completed_normally,
        )
        if debug:
            yield {
                "execution_log": {
                    "node": "persist_assistant_message",
                    "node_type": "persistence",
                    "duration_ms": int((time.monotonic() - t0) * 1000),
                    "input": {"conversation_id": str(conversation_id), "role": "assistant"},
                    "output": {
                        "message_id": str(assistant_message_id),
                        "completed": bool(completed_normally),
                        "chars": len(answer),
                    },
                }
            }

        # ===== 阶段 5：后处理（仅在正常完成且非隐身模式时执行）=====
        # 5.1 更新对话摘要
        if completed_normally and (not incognito) and self._conversation_summarizer is not None:
            t0 = time.monotonic()
            err: str | None = None
            try:
                await self._conversation_summarizer.schedule_update(conversation_id=conversation_id)
            except Exception as e:
                err = str(e)
            if debug:
                yield {
                    "execution_log": {
                        "node": "summary_schedule_update",
                        "node_type": "postprocess",
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                        "input": {"conversation_id": str(conversation_id)},
                        "output": {"scheduled": err is None, "error": err},
                    }
                }

        # 5.2 索引情景记忆
        if completed_normally and (not incognito) and self._episodic_memory is not None:
            t0 = time.monotonic()
            err: str | None = None
            try:
                await self._episodic_memory.schedule_index_episode(
                    conversation_id=conversation_id,
                    user_message_id=current_user_message_id,
                    assistant_message_id=assistant_message_id,
                    user_message=message,
                    assistant_message=answer,
                )
            except Exception as e:
                err = str(e)
            if debug:
                yield {
                    "execution_log": {
                        "node": "episodic_schedule_index",
                        "node_type": "postprocess",
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                        "input": {"conversation_id": str(conversation_id)},
                        "output": {"scheduled": err is None, "error": err},
                    }
                }

        # 5.3 写入向量记忆（mem0）
        if completed_normally and (not incognito) and self._memory_service is not None:
            t0 = time.monotonic()
            err: str | None = None
            try:
                await self._memory_service.maybe_write(
                    user_id=user_id,
                    user_message=message,
                    assistant_message=answer,
                    metadata={"session_id": session_id, "kb_prefix": kb_prefix or ""},
                )
            except Exception as e:
                err = str(e)
            if debug:
                yield {
                    "execution_log": {
                        "node": "mem0_maybe_write",
                        "node_type": "postprocess",
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                        "input": {"user_id": user_id},
                        "output": {"attempted": True, "error": err},
                    }
                }

        # ===== 阶段 6：Watchlist 自动捕获 =====
        watchlist_added: list[dict[str, Any]] = []
        allow_watchlist = (watchlist_auto_capture is not False) and (not incognito)
        if completed_normally and allow_watchlist and self._watchlist_capture is not None:
            t0 = time.monotonic()
            err: str | None = None
            try:
                res = await self._watchlist_capture.maybe_capture(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    user_message_id=current_user_message_id,
                    assistant_message_id=assistant_message_id,
                    user_message=message,
                    assistant_message=answer,
                )
                for it in res.added or []:
                    meta = it.metadata if isinstance(getattr(it, "metadata", None), dict) else {}
                    watchlist_added.append(
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
            except Exception as e:
                err = str(e)

            if debug:
                yield {
                    "execution_log": {
                        "node": "watchlist_auto_capture",
                        "node_type": "postprocess",
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                        "input": {"user_id": user_id, "conversation_id": str(conversation_id)},
                        "output": {"added_count": len(watchlist_added), "error": err},
                    }
                }

        if watchlist_added:
            yield {"status": "watchlist_auto_capture", "content": {"added": watchlist_added}}

        # ===== 阶段 7：发送延迟的 done 事件 =====
        if pending_done_event is not None:
            yield pending_done_event

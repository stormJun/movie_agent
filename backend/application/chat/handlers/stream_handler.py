from __future__ import annotations

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
        )

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
        current_user_message_id = await self._conversation_store.append_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
            completed=True,
        )

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
                    "requested_kb_prefix": kb_prefix,
                    "debug": bool(debug),
                    "agent_type": agent_type,
                    "conversation_id": conversation_id,
                    "current_user_message_id": current_user_message_id,
                }
            ):
                if isinstance(event, dict) and event.get("status") == "token":
                    tokens.append(str(event.get("content") or ""))

                if isinstance(event, dict) and event.get("status") == "done":
                    # Delay the terminal "done" until we've persisted messages and
                    # emitted any post-turn UX events (e.g., watchlist auto-capture).
                    completed_normally = True
                    pending_done_event = event
                    break

                yield event
        finally:
            # Best-effort persistence on generator close / cancellation.
            if pending_done_event is None and not tokens:
                return

        answer = "".join(tokens).strip()
        if not answer:
            if pending_done_event is not None:
                yield pending_done_event
            return

        assistant_message_id = await self._conversation_store.append_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            debug={"partial": not completed_normally} if debug else None,
            completed=completed_normally,
        )

        if completed_normally and self._conversation_summarizer is not None:
            try:
                await self._conversation_summarizer.schedule_update(conversation_id=conversation_id)
            except Exception:
                pass

        if completed_normally and self._episodic_memory is not None:
            try:
                await self._episodic_memory.schedule_index_episode(
                    conversation_id=conversation_id,
                    user_message_id=current_user_message_id,
                    assistant_message_id=assistant_message_id,
                    user_message=message,
                    assistant_message=answer,
                )
            except Exception:
                pass

        if completed_normally and self._memory_service is not None:
            try:
                await self._memory_service.maybe_write(
                    user_id=user_id,
                    user_message=message,
                    assistant_message=answer,
                    metadata={"session_id": session_id, "kb_prefix": kb_prefix or ""},
                )
            except Exception:
                pass

        watchlist_added: list[dict[str, Any]] = []
        if completed_normally and self._watchlist_capture is not None:
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
            except Exception:
                pass

        if watchlist_added:
            yield {"status": "watchlist_auto_capture", "content": {"added": watchlist_added}}

        if pending_done_event is not None:
            yield pending_done_event

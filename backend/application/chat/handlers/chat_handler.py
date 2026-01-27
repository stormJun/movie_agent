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
    """Phase 3: unified orchestration for the non-streaming endpoint."""

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
        agent_type: str = "hybrid_agent",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        incognito = bool(incognito)
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

        final = await self._graph.ainvoke(
            {
                "stream": False,
                "user_id": user_id,
                "message": message,
                "session_id": session_id,
                "request_id": request_id,
                "requested_kb_prefix": kb_prefix,
                "debug": bool(debug),
                "incognito": incognito,
                "agent_type": agent_type,
                "conversation_id": conversation_id,
                "current_user_message_id": current_user_message_id,
            }
        )

        resp = final.get("response") if isinstance(final, dict) else None
        if not isinstance(resp, dict):
            resp = {"answer": ""}

        route_decision_payload: dict[str, Any] | None = None
        raw_route_decision = final.get("route_decision") if isinstance(final, dict) else None
        if isinstance(raw_route_decision, RouteDecision):
            route_decision_payload = dataclasses.asdict(raw_route_decision)
        elif isinstance(raw_route_decision, dict):
            route_decision_payload = raw_route_decision

        answer = str(resp.get("answer") or "")

        watchlist_added: list[dict[str, Any]] = []

        # Persist assistant message + side effects (best-effort).
        if answer:
            assistant_message_id = await self._conversation_store.append_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
                citations=resp.get("reference") if debug else None,
                debug={
                    "route_decision": route_decision_payload,
                    "rag_runs": resp.get("rag_runs"),
                }
                if debug
                else None,
                completed=True,
            )

            if not incognito and self._conversation_summarizer is not None:
                try:
                    await self._conversation_summarizer.schedule_update(conversation_id=conversation_id)
                except Exception:
                    pass

            if not incognito and self._episodic_memory is not None:
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

            if not incognito and self._memory_service is not None:
                try:
                    await self._memory_service.maybe_write(
                        user_id=user_id,
                        user_message=message,
                        assistant_message=answer,
                        metadata={"session_id": session_id, "kb_prefix": final.get("kb_prefix")},
                    )
                except Exception:
                    pass

            allow_watchlist = (watchlist_auto_capture is not False) and (not incognito)
            if allow_watchlist and self._watchlist_capture is not None:
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

        # Shape to the existing ChatResponse contract.
        out: dict[str, Any] = {"answer": answer, "debug": bool(debug)}
        if watchlist_added:
            out["watchlist_auto_capture"] = {"added": watchlist_added}
        if resp.get("reference") is not None:
            out["reference"] = resp.get("reference")
        if resp.get("retrieval_results") is not None:
            out["retrieval_results"] = resp.get("retrieval_results")
        if debug:
            out["route_decision"] = route_decision_payload
            out["rag_runs"] = resp.get("rag_runs") or []
            out["episodic_memory"] = final.get("episodic_memory")
        return out

from __future__ import annotations

from typing import Any, Optional

from application.chat.conversation_graph import ConversationGraphRunner
from application.chat.memory_service import MemoryService
from application.handlers.factory import KnowledgeBaseHandlerFactory
from application.ports.chat_completion_port import ChatCompletionPort
from application.ports.conversation_episodic_memory_port import ConversationEpisodicMemoryPort
from application.ports.conversation_store_port import ConversationStorePort
from application.ports.conversation_summarizer_port import ConversationSummarizerPort
from application.ports.rag_executor_port import RAGExecutorPort
from application.ports.rag_stream_executor_port import RAGStreamExecutorPort
from application.ports.router_port import RouterPort


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
        kb_handler_factory: Optional[KnowledgeBaseHandlerFactory] = None,
        enable_kb_handlers: bool = False,
    ) -> None:
        self._conversation_store = conversation_store
        self._memory_service = memory_service
        self._conversation_summarizer = conversation_summarizer
        self._episodic_memory = episodic_memory

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
    ) -> dict[str, Any]:
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
                "requested_kb_prefix": kb_prefix,
                "debug": bool(debug),
                "agent_type": agent_type,
                "conversation_id": conversation_id,
                "current_user_message_id": current_user_message_id,
            }
        )

        resp = final.get("response") if isinstance(final, dict) else None
        if not isinstance(resp, dict):
            resp = {"answer": ""}

        answer = str(resp.get("answer") or "")

        # Persist assistant message + side effects (best-effort).
        if answer:
            assistant_message_id = await self._conversation_store.append_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
                citations=resp.get("reference") if debug else None,
                debug={
                    "route_decision": final.get("route_decision"),
                    "rag_runs": resp.get("rag_runs"),
                }
                if debug
                else None,
                completed=True,
            )

            if self._conversation_summarizer is not None:
                try:
                    await self._conversation_summarizer.schedule_update(conversation_id=conversation_id)
                except Exception:
                    pass

            if self._episodic_memory is not None:
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

            if self._memory_service is not None:
                try:
                    await self._memory_service.maybe_write(
                        user_id=user_id,
                        user_message=message,
                        assistant_message=answer,
                        metadata={"session_id": session_id, "kb_prefix": final.get("kb_prefix")},
                    )
                except Exception:
                    pass

        # Shape to the existing ChatResponse contract.
        out: dict[str, Any] = {"answer": answer, "debug": bool(debug)}
        if resp.get("reference") is not None:
            out["reference"] = resp.get("reference")
        if resp.get("retrieval_results") is not None:
            out["retrieval_results"] = resp.get("retrieval_results")
        if debug:
            out["route_decision"] = final.get("route_decision")
            out["rag_runs"] = resp.get("rag_runs") or []
            out["episodic_memory"] = final.get("episodic_memory")
        return out

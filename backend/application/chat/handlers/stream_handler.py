from __future__ import annotations

from typing import Any, AsyncGenerator, Optional

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
                    completed_normally = True
                yield event
        finally:
            answer = "".join(tokens).strip()
            if not answer:
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

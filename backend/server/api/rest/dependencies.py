from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from application.chat.handlers.chat_handler import ChatHandler
from application.chat.handlers.stream_handler import StreamHandler
from application.chat.memory_service import MemoryService
from application.chat.feedback_service import FeedbackService
from application.handlers.factory import KnowledgeBaseHandlerFactory
from application.knowledge_graph.service import KnowledgeGraphService
from config.settings import (
    MEMORY_ENABLE,
    MEMORY_MAX_CHARS,
    MEMORY_MIN_SCORE,
    MEMORY_TOP_K,
    MEMORY_WRITE_ENABLE,
    MEMORY_WRITE_MODE,
    PHASE2_ENABLE_KB_HANDLERS,
)
from domain.memory.policy import MemoryPolicy

if TYPE_CHECKING:
    from infrastructure.chat import AgentHistoryService


@lru_cache(maxsize=1)
def _build_conversation_store():
    from config.database import get_postgres_dsn
    from infrastructure.persistence.postgres.conversation_store import (
        InMemoryConversationStore,
        PostgresConversationStore,
    )

    dsn = get_postgres_dsn()
    if dsn:
        return PostgresConversationStore(dsn=dsn)
    return InMemoryConversationStore()


@lru_cache(maxsize=1)
def _build_example_store():
    from config.database import get_postgres_dsn
    from infrastructure.persistence.postgres.example_store import PostgresExampleStore

    dsn = get_postgres_dsn()
    if dsn:
        return PostgresExampleStore(dsn=dsn)
    # No in-memory fallback for now, or could return a mock
    return PostgresExampleStore(dsn="")  # Will fail if used without DB, but compliant with type



@lru_cache(maxsize=1)
def _build_memory_store():
    from infrastructure.memory.factory import MemoryStoreFactory

    if not MEMORY_ENABLE:
        from infrastructure.memory.null_memory_store import NullMemoryStore

        return NullMemoryStore()
    return MemoryStoreFactory.create()


@lru_cache(maxsize=1)
def _build_memory_service() -> MemoryService | None:
    if not MEMORY_ENABLE:
        return None
    policy = MemoryPolicy(
        top_k=int(MEMORY_TOP_K),
        min_score=float(MEMORY_MIN_SCORE),
        max_chars=int(MEMORY_MAX_CHARS),
    )
    return MemoryService(
        store=_build_memory_store(),
        policy=policy,
        write_enabled=MEMORY_WRITE_ENABLE,
        write_mode=MEMORY_WRITE_MODE,
    )


@lru_cache(maxsize=1)
def _build_handlers() -> tuple[ChatHandler, StreamHandler]:
    from infrastructure.rag.adapters.graphrag_executor import GraphragExecutor
    from infrastructure.rag.adapters.graphrag_stream_executor import (
        GraphragStreamExecutor,
    )
    from infrastructure.llm import LLMChatCompletionAdapter
    from infrastructure.routing import RouterGraphAdapter
    from infrastructure.rag.rag_manager import RagManager

    router = RouterGraphAdapter()
    rag_manager = RagManager()
    conversation_store = _build_conversation_store()
    executor = GraphragExecutor(rag_manager=rag_manager)
    stream_executor = GraphragStreamExecutor(rag_manager=rag_manager)
    completion = LLMChatCompletionAdapter()
    kb_handler_factory = KnowledgeBaseHandlerFactory(
        executor=executor,
        stream_executor=stream_executor,
    )
    memory_service = _build_memory_service()
    return (
        ChatHandler(
            router=router,
            executor=executor,
            completion=completion,
            conversation_store=conversation_store,
            memory_service=memory_service,
            kb_handler_factory=kb_handler_factory,
            enable_kb_handlers=PHASE2_ENABLE_KB_HANDLERS,
        ),
        StreamHandler(
            router=router,
            executor=stream_executor,
            conversation_store=conversation_store,
            memory_service=memory_service,
            kb_handler_factory=kb_handler_factory,
            enable_kb_handlers=PHASE2_ENABLE_KB_HANDLERS,
        ),
    )


def get_chat_handler() -> ChatHandler:
    return _build_handlers()[0]


def get_stream_handler() -> StreamHandler:
    return _build_handlers()[1]


@lru_cache(maxsize=1)
def _build_knowledge_graph_service() -> KnowledgeGraphService:
    from infrastructure.knowledge_graph import Neo4jKnowledgeGraphService

    return KnowledgeGraphService(port=Neo4jKnowledgeGraphService())


def get_knowledge_graph_service() -> KnowledgeGraphService:
    return _build_knowledge_graph_service()


@lru_cache(maxsize=1)
def _build_feedback_service() -> FeedbackService:
    from config.database import get_postgres_dsn
    from infrastructure.feedback import build_feedback_port

    return FeedbackService(port=build_feedback_port(dsn=get_postgres_dsn()))


def get_feedback_service() -> FeedbackService:
    return _build_feedback_service()


@lru_cache(maxsize=1)
def _build_clear_history_service() -> AgentHistoryService:
    # Directly depend on infrastructure for this endpoint.
    from infrastructure.chat import AgentHistoryService

    return AgentHistoryService(conversation_store=_build_conversation_store())


def get_clear_history_service() -> AgentHistoryService:
    return _build_clear_history_service()


def get_conversation_store():
    """获取会话存储实例，用于 conversations API。"""
    return _build_conversation_store()


def get_example_store():
    """获取示例问题存储实例。"""
    return _build_example_store()


async def shutdown_dependencies() -> None:
    """Best-effort shutdown hooks for long-lived adapters (connection pools)."""
    store = _build_conversation_store()
    close = getattr(store, "close", None)
    if callable(close):
        await close()

    example_store = _build_example_store()
    close_ex = getattr(example_store, "close", None)
    if callable(close_ex):
        await close_ex()

    mem = _build_memory_store()
    close_mem = getattr(mem, "close", None)
    if callable(close_mem):
        await close_mem()

    feedback_service = _build_feedback_service()
    port = getattr(feedback_service, "_port", None)
    close_port = getattr(port, "close", None)
    if callable(close_port):
        await close_port()

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from application.chat.handlers.chat_handler import ChatHandler
from application.chat.handlers.stream_handler import StreamHandler
from application.chat.memory_service import MemoryService
from application.chat.feedback_service import FeedbackService
from application.chat.watchlist_capture_service import WatchlistCaptureService
from application.ports.watchlist_store_port import WatchlistStorePort
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
    CHAT_SUMMARY_ENABLE,
    CHAT_SUMMARY_MAX_CHARS,
    CHAT_SUMMARY_MIN_MESSAGES,
    CHAT_SUMMARY_UPDATE_DELTA,
    CHAT_SUMMARY_WINDOW_SIZE,
    EPISODIC_MEMORY_ENABLE,
    EPISODIC_MEMORY_MAX_CONTEXT_CHARS,
    EPISODIC_MEMORY_MIN_SCORE,
    EPISODIC_MEMORY_RECALL_MODE,
    EPISODIC_MEMORY_SCAN_LIMIT,
    EPISODIC_MEMORY_TOP_K,
    EPISODIC_MILVUS_COLLECTION,
    EPISODIC_MILVUS_EMBEDDING_DIM,
    EPISODIC_MILVUS_HOST,
    EPISODIC_MILVUS_PORT,
    EPISODIC_VECTOR_BACKEND,
    WATCHLIST_AUTO_CAPTURE_ENABLE,
    WATCHLIST_AUTO_CAPTURE_MAX_ITEMS,
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
def _build_conversation_summary_store():
    from config.database import get_postgres_dsn
    from infrastructure.persistence.postgres.conversation_summary_store import (
        InMemoryConversationSummaryStore,
        PostgresConversationSummaryStore,
    )

    dsn = get_postgres_dsn()
    if dsn:
        return PostgresConversationSummaryStore(dsn=dsn)
    return InMemoryConversationSummaryStore(conversation_store=_build_conversation_store())


@lru_cache(maxsize=1)
def _build_conversation_episode_store():
    from config.database import get_postgres_dsn
    from infrastructure.persistence.postgres.conversation_episode_store import (
        InMemoryConversationEpisodeStore,
        PostgresConversationEpisodeStore,
    )

    # When episodic memory is disabled, avoid requiring Milvus configuration.
    if not EPISODIC_MEMORY_ENABLE:
        dsn = get_postgres_dsn()
        if dsn:
            return PostgresConversationEpisodeStore(dsn=dsn)
        return InMemoryConversationEpisodeStore()

    if EPISODIC_VECTOR_BACKEND == "milvus":
        from infrastructure.persistence.milvus.conversation_episode_store import (
            MilvusConversationEpisodeStore,
        )

        dim = int(EPISODIC_MILVUS_EMBEDDING_DIM) or None
        return MilvusConversationEpisodeStore(
            host=str(EPISODIC_MILVUS_HOST),
            port=int(EPISODIC_MILVUS_PORT),
            collection=str(EPISODIC_MILVUS_COLLECTION),
            embedding_dim=dim,
        )

    dsn = get_postgres_dsn()
    if dsn:
        return PostgresConversationEpisodeStore(dsn=dsn)
    return InMemoryConversationEpisodeStore()


@lru_cache(maxsize=1)
def _build_episodic_task_manager():
    from infrastructure.chat_history import EpisodicTaskManager

    return EpisodicTaskManager()


@lru_cache(maxsize=1)
def _build_conversation_episodic_memory():
    if not EPISODIC_MEMORY_ENABLE:
        return None
    from infrastructure.chat_history import ConversationEpisodicMemory

    return ConversationEpisodicMemory(
        store=_build_conversation_episode_store(),
        task_manager=_build_episodic_task_manager(),
        conversation_store=_build_conversation_store(),
        top_k=int(EPISODIC_MEMORY_TOP_K),
        scan_limit=int(EPISODIC_MEMORY_SCAN_LIMIT),
        min_score=float(EPISODIC_MEMORY_MIN_SCORE),
        recall_mode=str(EPISODIC_MEMORY_RECALL_MODE),
        max_context_chars=int(EPISODIC_MEMORY_MAX_CONTEXT_CHARS),
    )


@lru_cache(maxsize=1)
def _build_summary_task_manager():
    from infrastructure.chat_history import SummaryTaskManager

    return SummaryTaskManager()


@lru_cache(maxsize=1)
def _build_conversation_summarizer():
    if not CHAT_SUMMARY_ENABLE:
        return None
    from infrastructure.chat_history import ConversationSummarizer

    return ConversationSummarizer(
        store=_build_conversation_summary_store(),
        task_manager=_build_summary_task_manager(),
        min_messages=int(CHAT_SUMMARY_MIN_MESSAGES),
        update_delta=int(CHAT_SUMMARY_UPDATE_DELTA),
        window_size=int(CHAT_SUMMARY_WINDOW_SIZE),
        max_summary_chars=int(CHAT_SUMMARY_MAX_CHARS),
    )


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
def _build_watchlist_store() -> WatchlistStorePort:
    from config.database import get_postgres_dsn
    from infrastructure.persistence.postgres.watchlist_store import (
        InMemoryWatchlistStore,
        PostgresWatchlistStore,
    )

    dsn = get_postgres_dsn()
    if dsn:
        return PostgresWatchlistStore(dsn=dsn)
    return InMemoryWatchlistStore()


def get_watchlist_store() -> WatchlistStorePort:
    return _build_watchlist_store()



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
    conversation_summarizer = _build_conversation_summarizer()
    episodic_memory = _build_conversation_episodic_memory()
    watchlist_capture = WatchlistCaptureService(
        store=_build_watchlist_store(),
        enabled=bool(WATCHLIST_AUTO_CAPTURE_ENABLE),
        max_items_per_turn=int(WATCHLIST_AUTO_CAPTURE_MAX_ITEMS),
    )
    return (
        ChatHandler(
            router=router,
            executor=executor,
            stream_executor=stream_executor,
            completion=completion,
            conversation_store=conversation_store,
            memory_service=memory_service,
            conversation_summarizer=conversation_summarizer,
            episodic_memory=episodic_memory,
            watchlist_capture=watchlist_capture,
            kb_handler_factory=kb_handler_factory,
            enable_kb_handlers=PHASE2_ENABLE_KB_HANDLERS,
        ),
        StreamHandler(
            router=router,
            executor=executor,
            stream_executor=stream_executor,
            completion=completion,
            conversation_store=conversation_store,
            memory_service=memory_service,
            conversation_summarizer=conversation_summarizer,
            episodic_memory=episodic_memory,
            watchlist_capture=watchlist_capture,
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


@lru_cache(maxsize=1)
def _build_memory_facade_service():
    from application.memory_center.memory_facade_service import MemoryFacadeService

    return MemoryFacadeService(
        summary_store=_build_conversation_summary_store(),
        memory_store=_build_memory_store(),
        watchlist_store=_build_watchlist_store(),
    )


def get_memory_facade_service():
    return _build_memory_facade_service()


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

    # Phase 1 summary resources.
    summary_store = _build_conversation_summary_store()
    close_sum = getattr(summary_store, "close", None)
    if callable(close_sum):
        await close_sum()

    watchlist_store = _build_watchlist_store()
    close_watch = getattr(watchlist_store, "close", None)
    if callable(close_watch):
        await close_watch()

    task_manager = _build_summary_task_manager()
    shutdown = getattr(task_manager, "shutdown", None)
    if callable(shutdown):
        await shutdown()

    # Phase 2 episodic memory resources.
    if EPISODIC_MEMORY_ENABLE:
        episode_store = _build_conversation_episode_store()
        close_ep = getattr(episode_store, "close", None)
        if callable(close_ep):
            await close_ep()

        epi_tasks = _build_episodic_task_manager()
        shutdown_epi = getattr(epi_tasks, "shutdown", None)
        if callable(shutdown_epi):
            await shutdown_epi()

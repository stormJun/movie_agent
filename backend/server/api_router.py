from __future__ import annotations

from fastapi import APIRouter

import server.api.rest.v1.chat as chat_v1
import server.api.rest.v1.chat_stream as chat_stream_v1
import server.api.rest.v1.clear as clear_v1
import server.api.rest.v1.conversations as conversations_v1
import server.api.rest.v1.debug as debug_v1
import server.api.rest.v1.examples as examples_v1
import server.api.rest.v1.feedback as feedback_v1
import server.api.rest.v1.knowledge_graph as knowledge_graph_v1
import server.api.rest.v1.memory as memory_v1
import server.api.rest.v1.messages as messages_v1
import server.api.rest.v1.source as source_v1

# Canonical API router aggregator (v1 only; legacy routers were removed).
api_router = APIRouter()
api_router.include_router(chat_v1.router)
api_router.include_router(chat_stream_v1.router)
api_router.include_router(clear_v1.router)
api_router.include_router(conversations_v1.router)
api_router.include_router(debug_v1.router)
api_router.include_router(feedback_v1.router)
api_router.include_router(knowledge_graph_v1.router)
api_router.include_router(memory_v1.router)
api_router.include_router(messages_v1.router)
api_router.include_router(source_v1.router)
api_router.include_router(examples_v1.router)

__all__ = ["api_router"]

from __future__ import annotations

from typing import Optional

from application.handlers.base import KnowledgeBaseHandler
from application.handlers.edu.handler import EduKnowledgeBaseHandler
from application.ports.rag_executor_port import RAGExecutorPort
from application.ports.rag_stream_executor_port import RAGStreamExecutorPort


class KnowledgeBaseHandlerFactory:
    def __init__(
        self,
        *,
        executor: RAGExecutorPort,
        stream_executor: RAGStreamExecutorPort,
    ) -> None:
        self._executor = executor
        self._stream_executor = stream_executor
        self._handlers: dict[str, KnowledgeBaseHandler] = {}

    def get(self, kb_prefix: str) -> Optional[KnowledgeBaseHandler]:
        key = kb_prefix or ""
        if key in self._handlers:
            return self._handlers[key]
        if key == "edu":
            handler = EduKnowledgeBaseHandler(
                executor=self._executor,
                stream_executor=self._stream_executor,
            )
        else:
            return None
        self._handlers[key] = handler
        return handler

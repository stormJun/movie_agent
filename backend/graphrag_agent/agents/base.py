from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

import time

from graphrag_agent.config.settings import AGENT_SETTINGS
from graphrag_agent.ports.models import get_embeddings_model


class BaseAgent(ABC):
    """Retrieve-only Agent base (v3 strict).

    Notes:
    - Legacy chat execution (ask/ask_stream + LangGraph checkpointer) is removed.
    """

    @staticmethod
    def _normalize_kb_prefix(kb_prefix: str) -> str:
        raw = (kb_prefix or "").strip()
        if raw.endswith(":"):
            raw = raw[:-1]
        return raw.strip()

    def __init__(
        self,
        kb_prefix: str | None = None,
        agent_mode: str = "retrieve_only",
        enable_embeddings: bool = True,
        **_: Any,
    ) -> None:
        self.kb_prefix = self._normalize_kb_prefix(kb_prefix or "")
        self.agent_mode = (agent_mode or "retrieve_only").strip() or "retrieve_only"
        if self.agent_mode != "retrieve_only":
            raise ValueError(f"legacy mode has been removed (agent_mode={self.agent_mode})")

        # Some v3 retrieval-only wrappers don't need embeddings; keep it optional
        # so core-only import checks and unit tests remain lightweight.
        self.embeddings = get_embeddings_model() if enable_embeddings else None

        self.default_recursion_limit = AGENT_SETTINGS["default_recursion_limit"]
        self.stream_flush_threshold = AGENT_SETTINGS["stream_flush_threshold"]
        self.deep_stream_flush_threshold = AGENT_SETTINGS["deep_stream_flush_threshold"]
        self.fusion_stream_flush_threshold = AGENT_SETTINGS["fusion_stream_flush_threshold"]
        self.chunk_size = AGENT_SETTINGS["chunk_size"]

        self.execution_log: list[dict[str, Any]] = []
        self.performance_metrics: dict[str, Any] = {}

    @abstractmethod
    def retrieve_with_trace(self, query: str, thread_id: str = "default") -> Dict[str, Any]:
        """v3: Agents are retrieval-only and must return structured evidence."""
        raise NotImplementedError

    def _log_execution(self, node_name: str, input_data: Any, output_data: Any) -> None:
        self.execution_log.append(
            {
                "node": node_name,
                "timestamp": time.time(),
                "input": input_data,
                "output": output_data,
            }
        )

    def _log_performance(self, operation: str, metrics: dict[str, Any]) -> None:
        self.performance_metrics[operation] = {"timestamp": time.time(), **metrics}

    def close(self) -> None:
        return None

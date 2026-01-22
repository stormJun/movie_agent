from __future__ import annotations

from typing import Any, Dict, Optional
import threading

from infrastructure.agents.rag_factory.factory import RAGAgentFactory


class RAGAgentManager:
    """RAG Agent 管理器：负责实例缓存与会话隔离。"""

    def __init__(self, *, factory: Optional[RAGAgentFactory] = None) -> None:
        self._factory = factory or RAGAgentFactory()
        self._agent_instances: Dict[str, Any] = {}
        self._agent_lock = threading.RLock()

    @staticmethod
    def _normalize_kb_prefix(kb_prefix: str) -> str:
        raw = (kb_prefix or "").strip()
        if raw.endswith(":"):
            raw = raw[:-1]
        return raw.strip()

    def get_agent(
        self,
        agent_type: str,
        session_id: str = "default",
        kb_prefix: str | None = None,
        agent_mode: str | None = None,
    ) -> Any:
        kb_slug = self._normalize_kb_prefix(kb_prefix or "")
        # v3: legacy mode is removed; default to retrieve_only.
        mode_slug = (agent_mode or "retrieve_only").strip() or "retrieve_only"
        if mode_slug != "retrieve_only":
            raise ValueError(f"unsupported agent_mode: {mode_slug}")

        # v3: resident instances keyed by (agent_type, kb_prefix, mode); session
        # only affects thread_id (passed into retrieve calls), not pool size.
        instance_key = f"{kb_slug}:{agent_type}:{mode_slug}"

        with self._agent_lock:
            if instance_key not in self._agent_instances:
                self._agent_instances[instance_key] = self._factory.create_agent(
                    agent_type,
                    kb_prefix=kb_slug,
                    agent_mode=mode_slug,
                )
            return self._agent_instances[instance_key]

    def clear_history(self, session_id: str, kb_prefix: str | None = None) -> Dict[str, str]:
        # Legacy compatibility: in v3, conversation history is persisted via the
        # service-side ConversationStore (Postgres). Retrieval workers are
        # stateless; there is no LangGraph checkpointer state to clear here.
        #
        # Keep a stable return shape for callers.
        _ = session_id, kb_prefix
        return {"status": "success", "remaining_messages": "ok"}

    def close_all(self) -> None:
        with self._agent_lock:
            for instance_key, agent in self._agent_instances.items():
                try:
                    agent.close()
                    print(f"已关闭 {instance_key} 资源")
                except Exception as e:  # noqa: BLE001
                    print(f"关闭 {instance_key} 资源时出错: {e}")
            self._agent_instances.clear()

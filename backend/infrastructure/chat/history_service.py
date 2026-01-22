from __future__ import annotations

from typing import Dict, Optional

from application.ports.chat_history_port import ChatHistoryPort
from application.ports.conversation_store_port import ConversationStorePort
from infrastructure.agents.rag_factory import rag_agent_manager as agent_manager


class AgentHistoryService(ChatHistoryPort):
    def __init__(self, *, conversation_store: ConversationStorePort) -> None:
        self._conversation_store = conversation_store

    async def clear_history(
        self, *, user_id: str, session_id: str, kb_prefix: Optional[str] = None
    ) -> Dict[str, str]:
        # 1) Clear persisted chat messages for this (user_id, session_id) mapping.
        conversation_id = await self._conversation_store.get_or_create_conversation_id(
            user_id=user_id,
            session_id=session_id,
        )
        cleared = await self._conversation_store.clear_messages(conversation_id=conversation_id)

        # 2) Keep legacy in-memory/cache cleanup for now (helps avoid context leakage
        # from legacy agent_manager implementations during the migration).
        agent_manager.clear_history(session_id=session_id, kb_prefix=kb_prefix)

        return {"status": "ok", "remaining_messages": str(cleared)}

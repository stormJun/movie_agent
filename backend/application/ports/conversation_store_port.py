from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID


class ConversationStorePort(Protocol):
    """会话记录存储 Port（接口）。

    约定：
    - (user_id, session_id) 由前端传入；后端映射到 conversation_id（UUID）。
    - messages 以 conversation_id 为主键关联，便于分页/清理。
    """

    async def get_or_create_conversation_id(self, *, user_id: str, session_id: str) -> UUID:
        ...

    async def append_message(
        self,
        *,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: Optional[Dict[str, Any]] = None,
        debug: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        ...

    async def list_messages(
        self,
        *,
        conversation_id: UUID,
        limit: Optional[int] = None,
        before: Optional[datetime] = None,
        desc: bool = False,
    ) -> List[Dict[str, Any]]:
        ...

    async def clear_messages(self, *, conversation_id: UUID) -> int:
        ...

    async def list_conversations(
        self, *, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列出用户的历史会话列表，按更新时间倒序。"""
        ...


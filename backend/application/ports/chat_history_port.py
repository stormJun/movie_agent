from __future__ import annotations

from typing import Dict, Optional, Protocol


class ChatHistoryPort(Protocol):
    async def clear_history(
        self,
        *,
        user_id: str,
        session_id: str,
        kb_prefix: Optional[str] = None,
    ) -> Dict[str, str]:
        ...

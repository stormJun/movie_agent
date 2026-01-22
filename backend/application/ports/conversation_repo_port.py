from __future__ import annotations

from typing import Any, Optional, Protocol


class ConversationRepositoryPort(Protocol):
    def get(self, *, session_id: str) -> Optional[dict[str, Any]]:
        ...

    def save(self, *, session_id: str, conversation: dict[str, Any]) -> None:
        ...

    def clear(self, *, session_id: str) -> None:
        ...

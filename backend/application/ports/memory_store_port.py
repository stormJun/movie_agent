from __future__ import annotations

from typing import Any, Protocol, Optional

from domain.memory import MemoryItem


class MemoryStorePort(Protocol):
    async def search(
        self,
        *,
        user_id: str,
        query: str,
        top_k: int,
    ) -> list[MemoryItem]:
        ...

    async def add(
        self,
        *,
        user_id: str,
        text: str,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        ...

    async def close(self) -> None:
        ...


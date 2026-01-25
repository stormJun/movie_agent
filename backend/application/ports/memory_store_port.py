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

    async def get_all(
        self,
        *,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryItem]:
        """List user's memory items (for Memory Center dashboard/admin UIs)."""
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

    async def delete(self, *, user_id: str, memory_id: str) -> bool:
        """Delete a memory item (best-effort).

        Some providers may ignore user_id and delete by memory_id only.
        """
        ...

    async def close(self) -> None:
        ...

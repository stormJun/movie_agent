from __future__ import annotations

from typing import Any, Optional

from application.ports.memory_store_port import MemoryStorePort
from domain.memory import MemoryItem


class NullMemoryStore(MemoryStorePort):
    async def search(self, *, user_id: str, query: str, top_k: int) -> list[MemoryItem]:
        return []

    async def add(
        self,
        *,
        user_id: str,
        text: str,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        return None

    async def close(self) -> None:
        return None


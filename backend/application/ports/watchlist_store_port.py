from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from domain.memory import WatchlistItem


class WatchlistStorePort(Protocol):
    async def list_items(
        self,
        *,
        user_id: str,
        status: Optional[str] = None,
        query: Optional[str] = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WatchlistItem]:
        ...

    async def count_items(
        self,
        *,
        user_id: str,
        status: Optional[str] = None,
        query: Optional[str] = None,
        include_deleted: bool = False,
    ) -> int:
        ...

    async def add_item(
        self,
        *,
        user_id: str,
        title: str,
        year: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WatchlistItem:
        ...

    async def update_item(
        self,
        *,
        user_id: str,
        item_id: UUID,
        title: Optional[str] = None,
        year: Optional[int] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[WatchlistItem]:
        ...

    async def delete_item(self, *, user_id: str, item_id: UUID) -> bool:
        ...

    async def restore_item(self, *, user_id: str, item_id: UUID) -> Optional[WatchlistItem]:
        ...

    async def dedup_merge(self, *, user_id: str) -> Dict[str, int]:
        """Merge duplicates for a user (best-effort maintenance endpoint)."""
        ...

    async def close(self) -> None:
        ...

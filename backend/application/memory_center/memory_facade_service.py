from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from application.ports.conversation_summary_store_port import ConversationSummaryStorePort
from application.ports.memory_store_port import MemoryStorePort
from application.ports.watchlist_store_port import WatchlistStorePort


class MemoryFacadeService:
    """MVP facade for the Memory Center dashboard.

    Tech doc target:
    - Aggregate conversation summary (Phase 1) + user long-term memory (mem0).
    - Keep the API response lightweight and UI-friendly.
    """

    def __init__(
        self,
        *,
        summary_store: ConversationSummaryStorePort,
        memory_store: MemoryStorePort,
        watchlist_store: WatchlistStorePort,
    ) -> None:
        self._summary_store = summary_store
        self._memory_store = memory_store
        self._watchlist_store = watchlist_store

    @staticmethod
    def _format_taste_profile(memories: list[Any] | None) -> list[dict[str, Any]]:
        taste_profile: list[dict[str, Any]] = []
        for m in memories or []:
            # Keep the payload stable and small for UI use.
            tag = (m.tags[0] if getattr(m, "tags", ()) else "") or (m.text or "")
            tag = str(tag).strip()
            if len(tag) > 80:
                tag = tag[:77].rstrip() + "..."
            taste_profile.append(
                {
                    "id": str(m.id),
                    "tag": tag,
                    "text": str(getattr(m, "text", "") or ""),
                    "tags": list(getattr(m, "tags", ()) or ()),
                    "category": (m.metadata or {}).get("category") if isinstance(m.metadata, dict) else None,
                    "confidence": float(getattr(m, "score", 0.0) or 0.0),
                    "created_at": getattr(m, "created_at", None),
                    "metadata": dict(m.metadata or {}) if isinstance(getattr(m, "metadata", None), dict) else {},
                }
            )
        return taste_profile

    async def get_dashboard(self, *, conversation_id: UUID, user_id: str) -> dict[str, Any]:
        summary_task = self._summary_store.get_summary(conversation_id=conversation_id)
        memories_task = self._memory_store.get_all(user_id=str(user_id), limit=100, offset=0)
        watchlist_task = self._watchlist_store.list_items(user_id=str(user_id), limit=50, offset=0)
        watchlist_count_task = self._watchlist_store.count_items(user_id=str(user_id))

        summary_row, memories, watchlist_items, watchlist_count = await asyncio.gather(
            summary_task,
            memories_task,
            watchlist_task,
            watchlist_count_task,
        )

        summary_text = ""
        summary_updated_at = None
        if isinstance(summary_row, dict):
            summary_text = str(summary_row.get("summary") or "")
            summary_updated_at = summary_row.get("updated_at")

        taste_profile = self._format_taste_profile(memories)

        watchlist = []
        for it in watchlist_items or []:
            source = None
            if isinstance(it.metadata, dict):
                source = it.metadata.get("source")
            watchlist.append(
                {
                    "id": str(it.id),
                    "title": it.title,
                    "year": it.year,
                    "status": getattr(it, "status", "to_watch"),
                    "created_at": it.created_at,
                    "updated_at": getattr(it, "updated_at", None),
                    "deleted_at": getattr(it, "deleted_at", None),
                    "source": source,
                    "metadata": it.metadata or {},
                }
            )

        return {
            "summary": {"content": summary_text, "updated_at": summary_updated_at},
            "taste_profile": taste_profile,
            "watchlist": watchlist,
            "stats": {
                "total_memories": len(taste_profile),
                "watchlist_count": int(watchlist_count or 0),
            },
        }

    async def list_taste_profile(self, *, user_id: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        memories = await self._memory_store.get_all(user_id=str(user_id), limit=int(limit), offset=int(offset))
        return self._format_taste_profile(memories)

    async def delete_memory_item(self, *, user_id: str, memory_id: str) -> bool:
        return await self._memory_store.delete(user_id=str(user_id), memory_id=str(memory_id))

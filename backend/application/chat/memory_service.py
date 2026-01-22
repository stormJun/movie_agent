from __future__ import annotations

from typing import Any, Optional

from application.ports.memory_store_port import MemoryStorePort
from domain.memory.policy import MemoryPolicy, build_memory_context, extract_memory_candidates


class MemoryService:
    """Application-layer memory orchestration (when to recall/write)."""

    def __init__(
        self,
        *,
        store: MemoryStorePort,
        policy: MemoryPolicy,
        write_enabled: bool,
        write_mode: str = "rules",
    ) -> None:
        self._store = store
        self._policy = policy
        self._write_enabled = bool(write_enabled)
        self._write_mode = (write_mode or "rules").strip() or "rules"

    async def recall_context(self, *, user_id: str, query: str) -> Optional[str]:
        try:
            memories = await self._store.search(
                user_id=user_id,
                query=query,
                top_k=int(self._policy.top_k),
            )
        except Exception:
            # Best-effort degradation: memory recall must never break chat.
            return None
        return build_memory_context(memories=memories, policy=self._policy)

    async def maybe_write(
        self,
        *,
        user_id: str,
        user_message: str,
        assistant_message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if not self._write_enabled:
            return
        if self._write_mode != "rules":
            # v3 minimal: only rule-based write is supported for now.
            return

        candidates = extract_memory_candidates(user_message=user_message)
        if not candidates:
            return

        text, tags = candidates[0]
        try:
            await self._store.add(
                user_id=user_id,
                text=text,
                tags=list(tags),
                metadata=metadata,
            )
        except Exception:
            # Best-effort degradation: memory write must never break chat.
            return


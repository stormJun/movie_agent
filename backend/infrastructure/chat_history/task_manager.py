from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class SummaryTaskManager:
    """Best-effort in-process background task manager (single-flight per conversation).

    This avoids relying on request-scoped BackgroundTasks (which is brittle for
    StreamingResponse generators). For production durability, prefer a DB job
    table + worker, but this is a good minimal baseline.
    """

    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def schedule(self, *, conversation_id: UUID, coro_factory: Callable[[], Awaitable[Any]]) -> bool:
        """Schedule a background task for a conversation if none is running.

        Returns True if scheduled, False if skipped (already running).
        """
        async with self._lock:
            existing = self._tasks.get(conversation_id)
            if existing is not None and not existing.done():
                return False

            task = asyncio.create_task(self._run(conversation_id=conversation_id, coro_factory=coro_factory))
            self._tasks[conversation_id] = task
            return True

    async def _run(self, *, conversation_id: UUID, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        try:
            await coro_factory()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("summary task failed (conversation_id=%s)", conversation_id)
        finally:
            async with self._lock:
                task = self._tasks.get(conversation_id)
                if task is not None and task.done():
                    self._tasks.pop(conversation_id, None)

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


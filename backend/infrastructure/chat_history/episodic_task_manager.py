from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class EpisodicTaskManager:
    """Best-effort background task manager for episodic indexing (idempotent by key).

    - We key tasks by assistant_message_id to avoid duplicate indexing when retries happen.
    - Tasks are in-process (not durable). For production, use a DB job table + worker.
    """

    def __init__(self, *, max_concurrent: int = 4) -> None:
        self._max_concurrent = int(max_concurrent)
        self._sem = asyncio.Semaphore(self._max_concurrent)
        self._tasks: dict[UUID, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def schedule(self, *, key: UUID, coro_factory: Callable[[], Awaitable[Any]]) -> bool:
        async with self._lock:
            existing = self._tasks.get(key)
            if existing is not None and not existing.done():
                return False
            task = asyncio.create_task(self._run(key=key, coro_factory=coro_factory))
            self._tasks[key] = task
            return True

    async def _run(self, *, key: UUID, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        try:
            async with self._sem:
                await coro_factory()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("episodic task failed (key=%s)", key)
        finally:
            async with self._lock:
                task = self._tasks.get(key)
                if task is not None and task.done():
                    self._tasks.pop(key, None)

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


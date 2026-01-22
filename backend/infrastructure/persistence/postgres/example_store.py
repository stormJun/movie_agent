from __future__ import annotations

import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)


class PostgresExampleStore:
    """PostgreSQL example questions store (asyncpg).

    Tables:
      - example_questions(id uuid pk, content text, is_active boolean, created_at)
    """

    def __init__(
        self,
        *,
        dsn: str,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool = None
        self._pool_lock = asyncio.Lock()

    async def _get_pool(self):
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is not None:
                return self._pool
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
            )
            logger.info("PostgreSQL example store pool initialized")
            return self._pool

    async def list_examples(self) -> List[str]:
        """Fetch active example questions."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Fallback for dev/test if table doesn't exist? 
            # Ideally we fail or return empty. But let's assume table exists per plan.
            try:
                rows = await conn.fetch(
                    """
                    SELECT content FROM example_questions
                    WHERE is_active = TRUE
                    ORDER BY created_at ASC
                    LIMIT 20
                    """
                )
                return [row["content"] for row in rows]
            except Exception as e:
                logger.warning(f"Failed to fetch example questions (table missing?): {e}")
                return []

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL example store pool closed")

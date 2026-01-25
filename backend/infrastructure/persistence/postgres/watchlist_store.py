from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from application.ports.watchlist_store_port import WatchlistStorePort
from domain.memory import WatchlistItem

logger = logging.getLogger(__name__)

_YEAR_RE = re.compile(r"[\(（]\s*(\d{4})\s*[\)）]")


def _normalize_title(title: str) -> str:
    """Normalize title for dedupe/version-merge.

    MVP goal: dedupe superficial variants (case/punctuation/spacing).
    We intentionally do NOT try to map zh<->en aliases without an external movie DB.
    """
    t = (title or "").strip().lower()
    # Remove surrounding quotes/brackets.
    t = t.strip("'\"“”‘’")
    # Collapse separators/spaces.
    t = re.sub(r"[\s\-_:/\\|]+", " ", t).strip()
    # Remove most punctuation but keep CJK/latin/digits/spaces.
    t = re.sub(r"[^0-9a-z\u4e00-\u9fff ]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _canonicalize_title_and_year(title: str, year: Optional[int]) -> tuple[str, Optional[int], Optional[str]]:
    """Return (canonical_title, merged_year, raw_title_for_metadata)."""
    raw = (title or "").strip()
    if not raw:
        return "", year, None

    parsed_year = None
    m = _YEAR_RE.search(raw)
    if m:
        try:
            parsed_year = int(m.group(1))
        except Exception:
            parsed_year = None
    # Prefer explicit year param, else parse from title text.
    merged_year = int(year) if year is not None else parsed_year

    # Strip "(2014)" suffix and other trailing brackets.
    canonical = _YEAR_RE.sub("", raw).strip()
    canonical = re.sub(r"\s+", " ", canonical).strip()
    # Remove common leading list markers (defense in depth).
    canonical = re.sub(r"^\s*(?:[-*•]\s+|\d+\.\s+)", "", canonical).strip()

    return canonical, merged_year, raw if raw != canonical else None


class InMemoryWatchlistStore(WatchlistStorePort):
    def __init__(self) -> None:
        self._items: list[WatchlistItem] = []

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
        items = [i for i in self._items if i.user_id == user_id]
        if not include_deleted:
            items = [i for i in items if i.deleted_at is None]
        if status:
            items = [i for i in items if (i.status or "to_watch") == status]
        if query:
            q = (query or "").strip().lower()
            if q:
                items = [i for i in items if q in (i.title or "").lower()]

        items.sort(
            key=lambda x: (x.updated_at or x.created_at or datetime.min.replace(tzinfo=timezone.utc), x.id),
            reverse=True,
        )
        return items[int(offset) : int(offset) + int(limit)]

    async def count_items(
        self,
        *,
        user_id: str,
        status: Optional[str] = None,
        query: Optional[str] = None,
        include_deleted: bool = False,
    ) -> int:
        items = await self.list_items(
            user_id=user_id,
            status=status,
            query=query,
            include_deleted=include_deleted,
            limit=10_000,
            offset=0,
        )
        return len(items)

    async def add_item(
        self,
        *,
        user_id: str,
        title: str,
        year: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WatchlistItem:
        from uuid import uuid4

        canonical, merged_year, raw_title = _canonicalize_title_and_year(title, year)
        if not canonical:
            raise ValueError("title is required")
        norm = _normalize_title(canonical)
        if not norm:
            raise ValueError("title is invalid")

        # Dedupe/version-merge: if same normalized title exists, return it and
        # best-effort enrich year/metadata.
        for idx, it in enumerate(list(self._items)):
            if it.user_id != str(user_id):
                continue
            if _normalize_title(it.title) != norm:
                continue
            if it.deleted_at is not None:
                # Restore.
                now = datetime.now(timezone.utc)
                self._items[idx] = WatchlistItem(
                    id=it.id,
                    user_id=it.user_id,
                    title=it.title,
                    year=it.year if it.year is not None else merged_year,
                    status="to_watch",
                    metadata={**dict(it.metadata or {}), **dict(metadata or {})},
                    created_at=it.created_at,
                    updated_at=now,
                    deleted_at=None,
                )
                return self._items[idx]
            merged_meta = dict(it.metadata or {})
            if raw_title:
                merged_meta.setdefault("raw_titles", [])
                if isinstance(merged_meta.get("raw_titles"), list) and raw_title not in merged_meta["raw_titles"]:
                    merged_meta["raw_titles"].append(raw_title)
            if metadata:
                merged_meta.update(dict(metadata))
            next_year = it.year if it.year is not None else merged_year
            if next_year != it.year or merged_meta != it.metadata:
                now = datetime.now(timezone.utc)
                self._items[idx] = WatchlistItem(
                    id=it.id,
                    user_id=it.user_id,
                    title=it.title,
                    year=next_year,
                    status=it.status,
                    metadata=merged_meta,
                    created_at=it.created_at,
                    updated_at=now,
                    deleted_at=it.deleted_at,
                )
                return self._items[idx]
            return it

        now = datetime.now(timezone.utc)
        item = WatchlistItem(
            id=uuid4(),
            user_id=str(user_id),
            title=canonical,
            year=merged_year,
            status="to_watch",
            metadata={**({"raw_title": raw_title} if raw_title else {}), **dict(metadata or {})},
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self._items.append(item)
        return item

    async def delete_item(self, *, user_id: str, item_id: UUID) -> bool:
        for idx, it in enumerate(list(self._items)):
            if it.user_id == user_id and it.id == item_id and it.deleted_at is None:
                now = datetime.now(timezone.utc)
                self._items[idx] = WatchlistItem(
                    id=it.id,
                    user_id=it.user_id,
                    title=it.title,
                    year=it.year,
                    status=it.status,
                    metadata=dict(it.metadata or {}),
                    created_at=it.created_at,
                    updated_at=now,
                    deleted_at=now,
                )
                return True
        return False

    async def restore_item(self, *, user_id: str, item_id: UUID) -> Optional[WatchlistItem]:
        for idx, it in enumerate(list(self._items)):
            if it.user_id == user_id and it.id == item_id and it.deleted_at is not None:
                now = datetime.now(timezone.utc)
                self._items[idx] = WatchlistItem(
                    id=it.id,
                    user_id=it.user_id,
                    title=it.title,
                    year=it.year,
                    status="to_watch",
                    metadata=dict(it.metadata or {}),
                    created_at=it.created_at,
                    updated_at=now,
                    deleted_at=None,
                )
                return self._items[idx]
        return None

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
        for idx, it in enumerate(list(self._items)):
            if it.user_id != user_id or it.id != item_id or it.deleted_at is not None:
                continue
            next_title = it.title
            next_year = it.year
            if title is not None:
                canonical, merged_year, raw_title = _canonicalize_title_and_year(title, year)
                if not canonical:
                    raise ValueError("title is required")
                next_title = canonical
                next_year = merged_year
                # keep raw title in metadata if it changed
                if raw_title:
                    meta = dict(it.metadata or {})
                    meta.setdefault("raw_title", raw_title)
                    it = WatchlistItem(
                        id=it.id,
                        user_id=it.user_id,
                        title=it.title,
                        year=it.year,
                        status=it.status,
                        metadata=meta,
                        created_at=it.created_at,
                        updated_at=it.updated_at,
                        deleted_at=it.deleted_at,
                    )
            elif year is not None:
                next_year = int(year)

            next_status = it.status
            if status is not None:
                next_status = str(status)
            next_meta = dict(it.metadata or {})
            if metadata:
                next_meta.update(dict(metadata))

            now = datetime.now(timezone.utc)
            self._items[idx] = WatchlistItem(
                id=it.id,
                user_id=it.user_id,
                title=next_title,
                year=next_year,
                status=next_status,
                metadata=next_meta,
                created_at=it.created_at,
                updated_at=now,
                deleted_at=None,
            )
            return self._items[idx]
        return None

    async def dedup_merge(self, *, user_id: str) -> Dict[str, int]:
        # In-memory store already dedupes on add; keep a minimal no-op.
        _ = user_id
        return {"kept": 0, "deleted": 0, "merged": 0}

    async def close(self) -> None:
        return None


class PostgresWatchlistStore(WatchlistStorePort):
    """Postgres-backed watchlist storage (asyncpg)."""

    def __init__(
        self,
        *,
        dsn: str,
        min_size: int = 1,
        max_size: int = 5,
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
            import asyncpg  # type: ignore

            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                ssl=False,
            )
            await self._ensure_schema()
            logger.info("PostgreSQL watchlist store pool initialized")
            return self._pool

    async def _ensure_schema(self) -> None:
        pool = self._pool
        if pool is None:
            return
        async with pool.acquire() as conn:
            try:
                await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
            except Exception as e:
                logger.warning("Failed to ensure pgcrypto extension: %s", e)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlist_items (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id text NOT NULL,
                    title text NOT NULL,
                    year int,
                    status text NOT NULL DEFAULT 'to_watch',
                    normalized_title text,
                    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT NOW(),
                    updated_at timestamptz NOT NULL DEFAULT NOW(),
                    deleted_at timestamptz
                );
                """
            )
            # Best-effort schema evolution.
            await conn.execute("ALTER TABLE watchlist_items ADD COLUMN IF NOT EXISTS normalized_title text;")
            await conn.execute("ALTER TABLE watchlist_items ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'to_watch';")
            await conn.execute("UPDATE watchlist_items SET normalized_title = lower(title) WHERE normalized_title IS NULL;")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS watchlist_items_user_id_idx ON watchlist_items(user_id);"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS watchlist_items_user_norm_idx ON watchlist_items(user_id, normalized_title);"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS watchlist_items_user_status_idx ON watchlist_items(user_id, status);"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS watchlist_items_deleted_at_idx ON watchlist_items(deleted_at);"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS watchlist_items_created_at_idx ON watchlist_items(created_at);"
            )

    @staticmethod
    def _row_to_item(row: dict) -> WatchlistItem:
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        if not isinstance(meta, dict):
            meta = {}
        return WatchlistItem(
            id=row["id"],
            user_id=str(row.get("user_id") or ""),
            title=str(row.get("title") or ""),
            year=row.get("year"),
            status=str(row.get("status") or "to_watch"),
            metadata=dict(meta),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            deleted_at=row.get("deleted_at"),
        )

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
        pool = await self._get_pool()
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        async with pool.acquire() as conn:
            params: list[Any] = [str(user_id)]
            sql = "SELECT id, user_id, title, year, status, normalized_title, metadata, created_at, updated_at, deleted_at FROM watchlist_items WHERE user_id = $1"
            if not include_deleted:
                sql += " AND deleted_at IS NULL"
            if status:
                params.append(str(status))
                sql += f" AND status = ${len(params)}"
            if query:
                q = (query or "").strip()
                if q:
                    params.append(f"%{q}%")
                    sql += f" AND title ILIKE ${len(params)}"
            sql += " ORDER BY updated_at DESC, id DESC"
            params.append(limit)
            sql += f" LIMIT ${len(params)}"
            params.append(offset)
            sql += f" OFFSET ${len(params)}"
            rows = await conn.fetch(sql, *params)
        return [self._row_to_item(dict(r)) for r in rows]

    async def count_items(
        self,
        *,
        user_id: str,
        status: Optional[str] = None,
        query: Optional[str] = None,
        include_deleted: bool = False,
    ) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            params: list[Any] = [str(user_id)]
            sql = "SELECT COUNT(1) AS n FROM watchlist_items WHERE user_id = $1"
            if not include_deleted:
                sql += " AND deleted_at IS NULL"
            if status:
                params.append(str(status))
                sql += f" AND status = ${len(params)}"
            if query:
                q = (query or "").strip()
                if q:
                    params.append(f"%{q}%")
                    sql += f" AND title ILIKE ${len(params)}"
            row = await conn.fetchrow(sql, *params)
        return int(row["n"] if row and "n" in row else 0)

    async def add_item(
        self,
        *,
        user_id: str,
        title: str,
        year: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WatchlistItem:
        pool = await self._get_pool()
        canonical, merged_year, raw_title = _canonicalize_title_and_year(title, year)
        if not canonical:
            raise ValueError("title is required")
        norm = _normalize_title(canonical)
        if not norm:
            raise ValueError("title is invalid")

        # Dedupe/version-merge: try by normalized_title first.
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT id, user_id, title, year, status, metadata, created_at, updated_at, deleted_at
                FROM watchlist_items
                WHERE user_id = $1
                  AND normalized_title = $2
                ORDER BY deleted_at NULLS FIRST, created_at DESC
                LIMIT 1;
                """,
                str(user_id),
                norm,
            )

            merged_meta = dict(metadata or {})
            if raw_title:
                merged_meta.setdefault("raw_title", raw_title)

            if existing is not None:
                ex = dict(existing)
                if ex.get("deleted_at") is None:
                    # Best-effort enrichment: fill missing year / update metadata.
                    next_year = ex.get("year") if ex.get("year") is not None else merged_year
                    if next_year != ex.get("year") or merged_meta:
                        row = await conn.fetchrow(
                            """
                            UPDATE watchlist_items
                            SET year = COALESCE(year, $3),
                                metadata = (metadata || $4::jsonb),
                                updated_at = NOW()
                            WHERE id = $1
                              AND user_id = $2
                            RETURNING id, user_id, title, year, status, metadata, created_at, updated_at, deleted_at;
                            """,
                            ex["id"],
                            str(user_id),
                            next_year,
                            json.dumps(merged_meta),
                        )
                        assert row is not None
                        return self._row_to_item(dict(row))
                    return self._row_to_item(ex)

                # If previously deleted, restore it.
                row = await conn.fetchrow(
                    """
                    UPDATE watchlist_items
                    SET deleted_at = NULL,
                        title = $3,
                        year = COALESCE(year, $4),
                        status = 'to_watch',
                        metadata = (metadata || $5::jsonb),
                        normalized_title = $6,
                        updated_at = NOW()
                    WHERE id = $1
                      AND user_id = $2
                    RETURNING id, user_id, title, year, status, metadata, created_at, updated_at, deleted_at;
                    """,
                    ex["id"],
                    str(user_id),
                    canonical,
                    merged_year,
                    json.dumps(merged_meta),
                    norm,
                )
                assert row is not None
                return self._row_to_item(dict(row))

            # Insert new.
            meta_out = dict(metadata or {})
            if raw_title:
                meta_out.setdefault("raw_title", raw_title)
            row = await conn.fetchrow(
                """
                INSERT INTO watchlist_items (user_id, title, year, status, normalized_title, metadata)
                VALUES ($1, $2, $3, 'to_watch', $4, $5::jsonb)
                RETURNING id, user_id, title, year, status, metadata, created_at, updated_at, deleted_at;
                """,
                str(user_id),
                canonical,
                merged_year,
                norm,
                json.dumps(meta_out),
            )
        assert row is not None
        return self._row_to_item(dict(row))

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
        pool = await self._get_pool()
        next_title = None
        next_year = None
        next_norm = None

        if title is not None:
            canonical, merged_year, raw_title = _canonicalize_title_and_year(title, year)
            if not canonical:
                raise ValueError("title is required")
            next_title = canonical
            next_year = merged_year
            next_norm = _normalize_title(canonical)
            if not next_norm:
                raise ValueError("title is invalid")
            meta = dict(metadata or {})
            if raw_title:
                meta.setdefault("raw_title", raw_title)
            metadata = meta
        elif year is not None:
            next_year = int(year)

        next_status = None
        if status is not None:
            next_status = str(status)
            if next_status not in {"to_watch", "watched", "dismissed"}:
                raise ValueError("invalid status")

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if next_norm is not None:
                conflict = await conn.fetchrow(
                    """
                    SELECT id
                    FROM watchlist_items
                    WHERE user_id = $1
                      AND normalized_title = $2
                      AND deleted_at IS NULL
                      AND id <> $3
                    LIMIT 1;
                    """,
                    str(user_id),
                    next_norm,
                    item_id,
                )
                if conflict is not None:
                    raise ValueError("conflict: another item already has this title")

            meta_json = json.dumps(metadata) if metadata else None
            row = await conn.fetchrow(
                """
                UPDATE watchlist_items
                SET title = COALESCE($4, title),
                    year = COALESCE($5, year),
                    status = COALESCE($6, status),
                    normalized_title = COALESCE($7, normalized_title),
                    metadata = CASE
                        WHEN $8::jsonb IS NULL THEN metadata
                        ELSE (metadata || $8::jsonb)
                    END,
                    updated_at = NOW()
                WHERE user_id = $1
                  AND id = $2
                  AND deleted_at IS NULL
                RETURNING id, user_id, title, year, status, metadata, created_at, updated_at, deleted_at;
                """,
                str(user_id),
                item_id,
                str(user_id),  # keep param count stable; unused but preserves old style
                next_title,
                next_year,
                next_status,
                next_norm,
                meta_json,
            )
        return self._row_to_item(dict(row)) if row else None

    async def delete_item(self, *, user_id: str, item_id: UUID) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE watchlist_items
                SET deleted_at = NOW(),
                    updated_at = NOW()
                WHERE user_id = $1
                  AND id = $2
                  AND deleted_at IS NULL
                RETURNING id;
                """,
                str(user_id),
                item_id,
            )
        return bool(row)

    async def restore_item(self, *, user_id: str, item_id: UUID) -> Optional[WatchlistItem]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE watchlist_items
                SET deleted_at = NULL,
                    status = 'to_watch',
                    updated_at = NOW()
                WHERE user_id = $1
                  AND id = $2
                  AND deleted_at IS NOT NULL
                RETURNING id, user_id, title, year, status, metadata, created_at, updated_at, deleted_at;
                """,
                str(user_id),
                item_id,
            )
        return self._row_to_item(dict(row)) if row else None

    async def dedup_merge(self, *, user_id: str) -> Dict[str, int]:
        """Best-effort dedupe existing rows created before normalized_title existed."""
        pool = await self._get_pool()
        kept = deleted = merged = 0
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, year, status, normalized_title, metadata, created_at, updated_at, deleted_at
                FROM watchlist_items
                WHERE user_id = $1
                ORDER BY updated_at DESC, id DESC;
                """,
                str(user_id),
            )
            by_norm: dict[str, list[dict[str, Any]]] = {}
            for r in rows:
                d = dict(r)
                norm = d.get("normalized_title") or _normalize_title(str(d.get("title") or ""))
                if not norm:
                    continue
                by_norm.setdefault(str(norm), []).append(d)

            for norm, items in by_norm.items():
                # Keep newest non-deleted if possible; else keep newest.
                items.sort(
                    key=lambda x: (x.get("deleted_at") is None, x.get("updated_at") or x.get("created_at"), x.get("id")),
                    reverse=True,
                )
                winner = items[0]
                kept += 1
                if len(items) == 1:
                    continue

                # Merge year if missing.
                winner_year = winner.get("year")
                if winner_year is None:
                    for it in items[1:]:
                        if it.get("year") is not None:
                            winner_year = it.get("year")
                            break

                # Merge metadata (best-effort).
                meta = winner.get("metadata") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                if not isinstance(meta, dict):
                    meta = {}

                raw_titles: list[str] = []
                for it in items[1:]:
                    t = str(it.get("title") or "").strip()
                    if t:
                        raw_titles.append(t)
                if raw_titles:
                    meta.setdefault("raw_titles", [])
                    if isinstance(meta.get("raw_titles"), list):
                        for t in raw_titles:
                            if t not in meta["raw_titles"]:
                                meta["raw_titles"].append(t)

                # Update winner if needed.
                if winner_year != winner.get("year") or norm != winner.get("normalized_title") or raw_titles:
                    await conn.execute(
                        """
                        UPDATE watchlist_items
                        SET year = COALESCE(year, $3),
                            normalized_title = $4,
                            metadata = (metadata || $5::jsonb),
                            updated_at = NOW()
                        WHERE user_id = $1 AND id = $2;
                        """,
                        str(user_id),
                        winner["id"],
                        winner_year,
                        norm,
                        json.dumps(meta),
                    )
                    merged += 1

                # Soft delete the rest.
                for it in items[1:]:
                    if it.get("deleted_at") is None:
                        await conn.execute(
                            """
                            UPDATE watchlist_items
                            SET deleted_at = NOW(),
                                updated_at = NOW()
                            WHERE user_id = $1 AND id = $2 AND deleted_at IS NULL;
                            """,
                            str(user_id),
                            it["id"],
                        )
                        deleted += 1

        return {"kept": kept, "deleted": deleted, "merged": merged}

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
        self._pool = None

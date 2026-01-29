from __future__ import annotations

import argparse
import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Any, Iterable

from infrastructure.config.database import get_postgres_dsn
from infrastructure.config.settings import TMDB_API_KEY, TMDB_API_TOKEN
from infrastructure.enrichment.tmdb_client import TMDBClient
from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedListSpec:
    list_type: str  # popular/top_rated/now_playing/upcoming
    per_list: int


class _RateLimiter:
    """A tiny async rate limiter to keep TMDB calls polite.

    This is a global limiter (shared by list-page + details calls) so we don't
    accidentally exceed rate limits with high concurrency.
    """

    def __init__(self, *, min_interval_s: float) -> None:
        self._min_interval_s = max(0.0, float(min_interval_s))
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def wait(self) -> None:
        if self._min_interval_s <= 0:
            return
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            if now < self._next_allowed:
                await asyncio.sleep(self._next_allowed - now)
            self._next_allowed = loop.time() + self._min_interval_s


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Seed tmdb.movies from TMDB list endpoints (popular/top_rated/now_playing/upcoming). "
            "Optionally clears tmdb schema tables first."
        )
    )
    p.add_argument(
        "--clear",
        action="store_true",
        help="Clear tmdb schema tables (TRUNCATE ... CASCADE) before seeding (default off).",
    )
    p.add_argument(
        "--per-list",
        type=int,
        default=1000,
        help="Target number of movies to ingest per list endpoint (default 1000).",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip /movie/{id} fetch if tmdb.movies already has the row (default on).",
    )
    g.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Do not skip existing rows; always refetch /movie/{id}.",
    )
    p.add_argument(
        "--lists",
        default="popular,top_rated,now_playing,upcoming",
        help="Comma separated list types (default popular,top_rated,now_playing,upcoming).",
    )
    p.add_argument("--language", default="zh-CN", help="TMDB language for list pages (default zh-CN).")
    p.add_argument(
        "--details-language",
        default="zh-CN",
        help="TMDB language for details snapshots (default zh-CN).",
    )
    p.add_argument(
        "--details-concurrency",
        type=int,
        default=6,
        help="Concurrent TMDB /movie/{id} detail fetches (default 6).",
    )
    p.add_argument(
        "--min-interval-ms",
        type=int,
        default=120,
        help="Global minimum interval between TMDB HTTP requests in milliseconds (default 120ms).",
    )
    p.add_argument(
        "--fill-overview-en",
        action="store_true",
        help="If overview is empty in details-language, fallback to en-US overview (default off).",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=500,
        help="Safety cap for page iteration per list (TMDB enforces max=500; default 500).",
    )
    return p


def _parse_lists(arg: str, per_list: int) -> list[SeedListSpec]:
    raw = [s.strip() for s in (arg or "").split(",") if s.strip()]
    allowed = {"popular", "top_rated", "now_playing", "upcoming"}
    out: list[SeedListSpec] = []
    for lt in raw:
        if lt not in allowed:
            raise ValueError(f"unsupported list type: {lt!r} (allowed: {sorted(allowed)})")
        out.append(SeedListSpec(list_type=lt, per_list=int(per_list)))
    if not out:
        raise ValueError("no list types specified")
    return out


async def _clear_tmdb_schema(*, store: PostgresTmdbStore) -> None:
    pool = await store._get_pool()  # internal OK for integration scripts
    async with pool.acquire() as conn:
        # CASCADE to satisfy foreign keys (translations, request entities, outbox, ...).
        await conn.execute("TRUNCATE tmdb.enrichment_request_entities CASCADE;")
        await conn.execute("TRUNCATE tmdb.enrichment_requests CASCADE;")
        await conn.execute("TRUNCATE tmdb.movie_translations CASCADE;")
        await conn.execute("TRUNCATE tmdb.person_translations CASCADE;")
        await conn.execute("TRUNCATE tmdb.tv_translations CASCADE;")
        await conn.execute("TRUNCATE tmdb.neo4j_etl_outbox CASCADE;")
        await conn.execute("TRUNCATE tmdb.movies CASCADE;")
        await conn.execute("TRUNCATE tmdb.people CASCADE;")
        await conn.execute("TRUNCATE tmdb.tv_shows CASCADE;")


def _iter_chunks(items: Iterable[int], chunk_size: int) -> Iterable[list[int]]:
    buf: list[int] = []
    for x in items:
        buf.append(int(x))
        if len(buf) >= chunk_size:
            yield buf
            buf = []
    if buf:
        yield buf


async def _fetch_list_ids(
    *,
    client: TMDBClient,
    limiter: _RateLimiter,
    list_type: str,
    per_list: int,
    language: str,
    max_pages: int,
) -> list[int]:
    # TMDB list endpoints return 20 per page.
    need_pages = int(math.ceil(max(1, int(per_list)) / 20.0))
    need_pages = min(need_pages, int(max_pages))

    ids: list[int] = []
    for page in range(1, need_pages + 1):
        await limiter.wait()
        raw = await client.movie_list_raw(list_type=list_type, language=language, page=page)
        if not isinstance(raw, dict):
            continue
        results = raw.get("results", []) or []
        if not isinstance(results, list):
            continue
        for r in results:
            if not isinstance(r, dict):
                continue
            mid = r.get("id")
            if mid is None:
                continue
            try:
                ids.append(int(mid))
            except Exception:
                continue
        if len(ids) >= per_list:
            break

    # Keep order; trim to target.
    return ids[: int(per_list)]


async def _persist_full_movie(
    *,
    store: PostgresTmdbStore,
    client: TMDBClient,
    limiter: _RateLimiter,
    tmdb_id: int,
    details_language: str,
    fill_overview_en: bool,
) -> bool:
    await limiter.wait()
    details = await client.get_movie_details(int(tmdb_id), language=details_language)
    if not isinstance(details, dict) or not details:
        return False

    if fill_overview_en:
        overview = str(details.get("overview") or "").strip()
        if not overview:
            await limiter.wait()
            details_en = await client.get_movie_details(int(tmdb_id), language="en-US")
            if isinstance(details_en, dict) and str(details_en.get("overview") or "").strip():
                details["overview"] = str(details_en.get("overview") or "")

    # Persist as a "full" snapshot via the same pipeline used by online enrichment.
    await store.persist_enrichment(
        user_id="seed",
        session_id="seed",
        query_text=f"seed_movie_list:{tmdb_id}",
        tmdb_endpoint=f"/movie/{tmdb_id}",
        extracted_entities=None,
        disambiguation=[{"type": "movie", "selected": {"id": int(tmdb_id), "score": 999.0}}],
        payloads=[{"type": "movie", "data": details}],
    )
    return True


async def _run(
    *,
    clear: bool,
    specs: list[SeedListSpec],
    skip_existing: bool,
    language: str,
    details_language: str,
    details_concurrency: int,
    min_interval_ms: int,
    fill_overview_en: bool,
    max_pages: int,
) -> int:
    if not (TMDB_API_TOKEN or TMDB_API_KEY):
        logger.error("TMDB auth not configured: set TMDB_API_TOKEN or TMDB_API_KEY")
        return 2

    dsn = get_postgres_dsn()
    if not dsn:
        logger.error("Postgres not configured: set POSTGRES_DSN or POSTGRES_HOST/PORT/USER/PASSWORD/DB")
        return 2

    store = PostgresTmdbStore(dsn=dsn)
    client = TMDBClient()
    limiter = _RateLimiter(min_interval_s=float(min_interval_ms) / 1000.0)
    sem = asyncio.Semaphore(max(1, int(details_concurrency)))

    try:
        if clear:
            logger.info("clearing tmdb schema tables...")
            await _clear_tmdb_schema(store=store)
            logger.info("clearing tmdb schema tables done")

        all_ids: list[tuple[str, int]] = []
        for spec in specs:
            logger.info("fetching ids from /movie/%s target=%s ...", spec.list_type, spec.per_list)
            ids = await _fetch_list_ids(
                client=client,
                limiter=limiter,
                list_type=spec.list_type,
                per_list=spec.per_list,
                language=language,
                max_pages=max_pages,
            )
            logger.info("list /movie/%s got ids=%s", spec.list_type, len(ids))
            all_ids.extend((spec.list_type, mid) for mid in ids)

        # Dedup to avoid extra /movie/{id} calls across lists.
        ordered_unique: list[int] = []
        seen: set[int] = set()
        for _, mid in all_ids:
            if mid in seen:
                continue
            seen.add(mid)
            ordered_unique.append(mid)

        if skip_existing and not clear:
            pool = await store._get_pool()  # internal OK for integration scripts
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT tmdb_id FROM tmdb.movies")
            existing = {int(r["tmdb_id"]) for r in rows if r and r.get("tmdb_id") is not None}
            before = len(ordered_unique)
            ordered_unique = [mid for mid in ordered_unique if mid not in existing]
            logger.info("skip-existing enabled: %s -> %s ids to fetch", before, len(ordered_unique))

        logger.info(
            "seeding details snapshots: unique_ids=%s (from %s lists)",
            len(ordered_unique),
            len(specs),
        )

        ok = 0
        failed = 0

        async def fetch_one(mid: int) -> None:
            nonlocal ok, failed
            async with sem:
                try:
                    if await _persist_full_movie(
                        store=store,
                        client=client,
                        limiter=limiter,
                        tmdb_id=mid,
                        details_language=details_language,
                        fill_overview_en=fill_overview_en,
                    ):
                        ok += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    logger.info("seed failed tmdb_id=%s err=%s", mid, e)

        # Chunk gather to keep memory + concurrency stable.
        for chunk in _iter_chunks(ordered_unique, 200):
            await asyncio.gather(*(fetch_one(mid) for mid in chunk), return_exceptions=True)
            logger.info("progress ok=%s failed=%s / %s", ok, failed, len(ordered_unique))

        logger.info("done ok=%s failed=%s", ok, failed)
        return 0
    finally:
        await client.close()
        await store.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _build_parser().parse_args()
    specs = _parse_lists(str(args.lists), int(args.per_list))
    skip_existing = True
    if bool(args.no_skip_existing):
        skip_existing = False
    if bool(args.skip_existing):
        skip_existing = True
    raise SystemExit(
        asyncio.run(
            _run(
                clear=bool(args.clear),
                specs=specs,
                skip_existing=skip_existing,
                language=str(args.language),
                details_language=str(args.details_language),
                details_concurrency=int(args.details_concurrency),
                min_interval_ms=int(args.min_interval_ms),
                fill_overview_en=bool(args.fill_overview_en),
                max_pages=int(args.max_pages),
            )
        )
    )


if __name__ == "__main__":
    main()

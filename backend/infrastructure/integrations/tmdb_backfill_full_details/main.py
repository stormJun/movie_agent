from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from infrastructure.config.database import get_postgres_dsn
from infrastructure.config.settings import TMDB_API_KEY, TMDB_API_TOKEN
from infrastructure.enrichment.tmdb_client import TMDBClient
from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Backfill incomplete tmdb.movies rows by fetching full "
            "/movie/{id}?append_to_response=credits snapshots and persisting them."
        )
    )
    p.add_argument("--limit", type=int, default=500, help="Max ids to backfill in this run.")
    p.add_argument("--concurrency", type=int, default=5, help="Concurrent TMDB detail fetches.")
    p.add_argument("--language", default="zh-CN", help="Primary TMDB language (default zh-CN).")
    p.add_argument(
        "--fill-overview-en",
        action="store_true",
        help="If overview is empty in primary language, fallback to en-US overview (default off).",
    )
    return p


async def _fetch_incomplete_movie_ids(*, store: PostgresTmdbStore, limit: int) -> list[int]:
    # NOTE: We treat missing/empty credits+genres as incomplete snapshots.
    sql = """
    SELECT tmdb_id
    FROM tmdb.movies
    WHERE raw IS NULL
       OR jsonb_typeof(raw->'credits') <> 'object'
       OR jsonb_typeof(raw->'credits'->'crew') <> 'array'
       OR jsonb_array_length(COALESCE(raw->'credits'->'crew','[]'::jsonb)) = 0
       OR jsonb_typeof(raw->'credits'->'cast') <> 'array'
       OR jsonb_array_length(COALESCE(raw->'credits'->'cast','[]'::jsonb)) = 0
       OR jsonb_typeof(raw->'genres') <> 'array'
       OR jsonb_array_length(COALESCE(raw->'genres','[]'::jsonb)) = 0
    ORDER BY fetched_at ASC NULLS FIRST, tmdb_id ASC
    LIMIT $1
    """
    pool = await store._get_pool()  # internal, but OK for an integration script
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, int(limit))
        return [int(r["tmdb_id"]) for r in rows if r and r.get("tmdb_id") is not None]


async def _run(*, limit: int, concurrency: int, language: str, fill_overview_en: bool) -> int:
    if not (TMDB_API_TOKEN or TMDB_API_KEY):
        logger.error("TMDB auth not configured: set TMDB_API_TOKEN or TMDB_API_KEY")
        return 2

    dsn = get_postgres_dsn()
    if not dsn:
        logger.error("Postgres not configured: set POSTGRES_DSN or POSTGRES_HOST/PORT/USER/PASSWORD/DB")
        return 2

    store = PostgresTmdbStore(dsn=dsn)
    client = TMDBClient()
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    fetched = 0
    updated = 0
    failed = 0

    try:
        ids = await _fetch_incomplete_movie_ids(store=store, limit=limit)
        if not ids:
            logger.info("no incomplete movies found")
            return 0
        logger.info("found %s incomplete tmdb.movies rows (limit=%s)", len(ids), limit)

        async def fetch_one(tmdb_id: int) -> None:
            nonlocal fetched, updated, failed
            async with sem:
                try:
                    details = await client.get_movie_details(int(tmdb_id), language=language)
                    fetched += 1
                    if not isinstance(details, dict) or not details:
                        failed += 1
                        return
                    if fill_overview_en:
                        overview = str(details.get("overview") or "").strip()
                        if not overview:
                            details_en = await client.get_movie_details(int(tmdb_id), language="en-US")
                            if isinstance(details_en, dict) and str(details_en.get("overview") or "").strip():
                                details["overview"] = str(details_en.get("overview") or "")

                    # Persist full snapshot (raw includes credits via append_to_response=credits).
                    await store.persist_enrichment(
                        user_id="seed",
                        session_id="seed",
                        query_text=f"backfill_full_details:{tmdb_id}",
                        tmdb_endpoint=f"/movie/{tmdb_id}",
                        extracted_entities=None,
                        disambiguation=[
                            {"type": "movie", "selected": {"id": int(tmdb_id), "score": 999.0}}
                        ],
                        payloads=[{"type": "movie", "data": details}],
                    )
                    updated += 1
                except Exception as e:
                    failed += 1
                    logger.info("backfill failed tmdb_id=%s err=%s", tmdb_id, e)

        await asyncio.gather(*(fetch_one(mid) for mid in ids), return_exceptions=True)
    finally:
        await client.close()
        await store.close()

    logger.info("done fetched=%s updated=%s failed=%s", fetched, updated, failed)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _build_parser().parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                limit=int(args.limit),
                concurrency=int(args.concurrency),
                language=str(args.language),
                fill_overview_en=bool(args.fill_overview_en),
            )
        )
    )


if __name__ == "__main__":
    main()


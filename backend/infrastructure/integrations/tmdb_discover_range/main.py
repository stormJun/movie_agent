from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime
from typing import Any

from infrastructure.config.database import get_postgres_dsn
from infrastructure.enrichment.tmdb_client import TMDBClient
from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Seed TMDB movies into Postgres using /discover/movie for a date range.")
    p.add_argument("--start-date", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--end-date", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--pages", type=int, default=10, help="Discover pages to fetch (20 items/page).")
    p.add_argument("--sort-by", default="popularity.desc", help="TMDB discover sort_by (default popularity.desc).")
    p.add_argument("--language", default="zh-CN", help="TMDB language for details (default zh-CN).")
    p.add_argument("--concurrency", type=int, default=5, help="Concurrent detail fetches.")
    p.add_argument("--max-imported", type=int, default=500, help="Stop after importing N movies.")
    p.add_argument("--skip-existing", action="store_true", help="Skip tmdb_id that already exists in Postgres.")
    return p


async def _run(
    *,
    start_date: str,
    end_date: str,
    pages: int,
    sort_by: str,
    language: str,
    concurrency: int,
    max_imported: int,
    skip_existing: bool,
) -> int:
    dsn = get_postgres_dsn()
    if not dsn:
        logger.error("Postgres not configured: set POSTGRES_DSN or POSTGRES_HOST/PORT/USER/PASSWORD/DB")
        return 2

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start > end:
        logger.error("invalid date range: start_date=%s end_date=%s", start, end)
        return 2

    client = TMDBClient()
    store = PostgresTmdbStore(dsn=dsn)
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    imported = 0
    fetched = 0
    discovered = 0

    async def fetch_and_persist(mid: int) -> None:
        nonlocal imported, fetched
        async with sem:
            if skip_existing and await store.has_movie(tmdb_id=mid):
                return
            details = await client.get_movie_details(int(mid), language=language)
            fetched += 1
            if not isinstance(details, dict) or not details:
                return
            # Persist the full snapshot (raw includes credits).
            await store.persist_enrichment(
                user_id="seed",
                session_id="seed",
                query_text=f"discover_range:{start_date}:{end_date}:{mid}",
                tmdb_endpoint="/discover/movie",
                extracted_entities=None,
                disambiguation=[{"type": "movie", "selected": {"id": int(mid), "score": 999.0}}],
                payloads=[{"type": "movie", "data": details}],
            )
            imported += 1

    try:
        for page in range(1, max(1, int(pages)) + 1):
            if imported >= max_imported:
                break

            raw = await client.discover_movie_raw(
                language=language,
                page=page,
                sort_by=sort_by,
                filters={"date_range": {"gte": start.isoformat(), "lte": end.isoformat()}},
            )
            results = raw.get("results") if isinstance(raw, dict) else None
            if not isinstance(results, list) or not results:
                logger.info("no results page=%s", page)
                break

            ids: list[int] = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                mid = r.get("id")
                try:
                    ids.append(int(mid))
                except Exception:
                    continue
            discovered += len(ids)

            await asyncio.gather(*(fetch_and_persist(mid) for mid in ids), return_exceptions=True)
            logger.info(
                "progress page=%s discovered=%s fetched=%s imported=%s",
                page,
                discovered,
                fetched,
                imported,
            )
    finally:
        await client.close()
        await store.close()

    logger.info("done discovered=%s fetched=%s imported=%s", discovered, fetched, imported)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _build_parser().parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                start_date=args.start_date,
                end_date=args.end_date,
                pages=int(args.pages),
                sort_by=str(args.sort_by),
                language=str(args.language),
                concurrency=int(args.concurrency),
                max_imported=int(args.max_imported),
                skip_existing=bool(args.skip_existing),
            )
        )
    )


if __name__ == "__main__":
    main()


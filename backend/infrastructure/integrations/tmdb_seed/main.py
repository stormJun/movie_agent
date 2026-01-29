from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from infrastructure.config.database import get_postgres_dsn
from infrastructure.config.settings import TMDB_API_KEY, TMDB_API_TOKEN
from infrastructure.enrichment.tmdb_client import TMDBClient
from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Seed TMDB snapshots into Postgres (MVP browse feeds).")
    p.add_argument(
        "--feed",
        default="popular",
        choices=["popular", "now_playing", "upcoming"],
        help="Which feed heuristic to seed via TMDB discover API.",
    )
    p.add_argument("--pages", type=int, default=2, help="How many discover pages to fetch.")
    p.add_argument("--language", default="zh-CN", help="TMDB language (e.g. zh-CN, en-US).")
    p.add_argument("--concurrency", type=int, default=5, help="Concurrent detail fetches.")
    return p


def _discover_filters(feed: str) -> dict[str, Any]:
    today = date.today()
    if feed == "upcoming":
        return {
            "date_range": {
                "gte": today.isoformat(),
                "lte": (today + timedelta(days=180)).isoformat(),
            }
        }
    if feed == "now_playing":
        return {
            "date_range": {
                "gte": (today - timedelta(days=90)).isoformat(),
                "lte": today.isoformat(),
            }
        }
    return {}


async def _run(feed: str, pages: int, language: str, concurrency: int) -> int:
    if not (TMDB_API_TOKEN or TMDB_API_KEY):
        logger.error("TMDB auth not configured: set TMDB_API_TOKEN or TMDB_API_KEY")
        return 2

    dsn = get_postgres_dsn()
    if not dsn:
        logger.error("Postgres not configured: set POSTGRES_DSN or POSTGRES_HOST/PORT/USER/PASSWORD/DB")
        return 2

    client = TMDBClient(api_token=TMDB_API_TOKEN or None, api_key=TMDB_API_KEY or None)
    store = PostgresTmdbStore(dsn=dsn)

    filters = _discover_filters(feed)
    total_persisted = 0

    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def fetch_and_persist(movie_id: int) -> None:
        nonlocal total_persisted
        async with sem:
            details = await client.get_movie_details(movie_id, language=language)
            if not isinstance(details, dict) or not details:
                return
            await store.persist_enrichment(
                user_id="seed",
                session_id="seed",
                query_text=f"seed:{feed}:{movie_id}",
                tmdb_endpoint="/discover/movie",
                extracted_entities=None,
                disambiguation=[{"type": "movie", "selected": {"id": int(movie_id), "score": 999.0}}],
                payloads=[{"type": "movie", "data": details}],
            )
            total_persisted += 1

    try:
        for page in range(1, max(1, int(pages)) + 1):
            raw = await client.discover_movie_raw(
                language=language,
                page=page,
                sort_by="popularity.desc",
                filters=filters,
            )
            results = raw.get("results") if isinstance(raw, dict) else None
            if not isinstance(results, list) or not results:
                logger.info("No results for page=%s feed=%s", page, feed)
                continue

            ids: list[int] = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                mid = r.get("id")
                try:
                    ids.append(int(mid))
                except Exception:
                    continue

            await asyncio.gather(*(fetch_and_persist(mid) for mid in ids))
            logger.info("seed progress: feed=%s page=%s persisted=%s", feed, page, total_persisted)
    finally:
        await client.close()
        await store.close()

    logger.info("seed done: feed=%s persisted=%s", feed, total_persisted)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _build_parser().parse_args()
    raise SystemExit(asyncio.run(_run(args.feed, args.pages, args.language, args.concurrency)))


if __name__ == "__main__":
    main()

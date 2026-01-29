from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from infrastructure.config.database import get_postgres_dsn
from infrastructure.enrichment.tmdb_client import TMDBClient
from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdRow:
    tmdb_id: int
    original_title: str
    popularity: float
    adult: bool


def _iter_ndjson_ids(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            mid = obj.get("id")
            if mid is None:
                continue
            try:
                tmdb_id = int(mid)
            except Exception:
                continue
            original_title = str(obj.get("original_title") or "").strip()
            try:
                popularity = float(obj.get("popularity") or 0.0)
            except Exception:
                popularity = 0.0
            adult = bool(obj.get("adult") or False)
            yield IdRow(
                tmdb_id=tmdb_id,
                original_title=original_title,
                popularity=popularity,
                adult=adult,
            )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Import TMDB movie ids (NDJSON) into Postgres by fetching /movie/{id}.")
    p.add_argument("--ids-file", required=True, help="Path to NDJSON file (one JSON object per line).")
    p.add_argument("--language", default="zh-CN", help="TMDB language for details (default zh-CN).")
    p.add_argument("--concurrency", type=int, default=5, help="Concurrent detail fetches.")
    p.add_argument("--max-imported", type=int, default=2000, help="Stop after importing N movies.")
    p.add_argument("--skip-existing", action="store_true", help="Skip tmdb_id that already exists in Postgres.")
    p.add_argument("--include-adult", action="store_true", help="Include adult movies (default: false).")
    return p


async def _run(
    *,
    ids_file: str,
    language: str,
    concurrency: int,
    max_imported: int,
    skip_existing: bool,
    include_adult: bool,
) -> int:
    if not os.path.exists(ids_file):
        logger.error("ids_file not found: %s", ids_file)
        return 2

    dsn = get_postgres_dsn()
    if not dsn:
        logger.error("Postgres not configured: set POSTGRES_DSN or POSTGRES_HOST/PORT/USER/PASSWORD/DB")
        return 2

    store = PostgresTmdbStore(dsn=dsn)
    client = TMDBClient()
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    scanned = 0
    imported = 0
    skipped_existing_n = 0
    skipped_adult_n = 0
    fetched_n = 0

    async def fetch_one(row: IdRow) -> None:
        nonlocal imported, skipped_existing_n, fetched_n
        async with sem:
            if skip_existing and await store.has_movie(tmdb_id=row.tmdb_id):
                skipped_existing_n += 1
                return
            details = await client.get_movie_details(int(row.tmdb_id), language=language)
            fetched_n += 1
            if not isinstance(details, dict) or not details:
                return
            await store.persist_enrichment(
                user_id="seed",
                session_id="seed",
                query_text=f"id_list:{os.path.basename(ids_file)}:{row.tmdb_id}",
                tmdb_endpoint=f"/movie/{row.tmdb_id}",
                extracted_entities=[row.original_title] if row.original_title else None,
                disambiguation=[{"type": "movie", "selected": {"id": int(row.tmdb_id), "score": 999.0}}],
                payloads=[{"type": "movie", "data": details}],
            )
            imported += 1

    try:
        tasks: set[asyncio.Task[None]] = set()
        for row in _iter_ndjson_ids(ids_file):
            scanned += 1
            if row.adult and not include_adult:
                skipped_adult_n += 1
                continue
            if imported >= max_imported:
                break

            t = asyncio.create_task(fetch_one(row))
            tasks.add(t)
            # Limit outstanding tasks to avoid memory spikes.
            if len(tasks) >= max(20, concurrency * 10):
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = set(pending)

            if scanned % 200 == 0:
                logger.info(
                    "progress scanned=%s fetched=%s imported=%s (skip_existing=%s, skip_adult=%s)",
                    scanned,
                    fetched_n,
                    imported,
                    skipped_existing_n,
                    skipped_adult_n,
                )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await client.close()
        await store.close()

    logger.info(
        "done scanned=%s fetched=%s imported=%s (skip_existing=%s, skip_adult=%s)",
        scanned,
        fetched_n,
        imported,
        skipped_existing_n,
        skipped_adult_n,
    )
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _build_parser().parse_args()
    raise SystemExit(
        asyncio.run(
            _run(
                ids_file=args.ids_file,
                language=str(args.language),
                concurrency=int(args.concurrency),
                max_imported=int(args.max_imported),
                skip_existing=bool(args.skip_existing),
                include_adult=bool(args.include_adult),
            )
        )
    )


if __name__ == "__main__":
    main()


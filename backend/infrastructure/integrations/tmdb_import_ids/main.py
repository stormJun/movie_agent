from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

from infrastructure.config.database import get_postgres_dsn
from infrastructure.enrichment.tmdb_client import TMDBClient
from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _today_utc() -> date:
    return datetime.utcnow().date()


@dataclass(frozen=True)
class IdRow:
    tmdb_id: int
    popularity: float
    original_title: str
    adult: bool


def _iter_ndjson_ids(path: str) -> Any:
    """Yield IdRow from TMDB daily id exports (NDJSON)."""
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
            popularity = 0.0
            try:
                popularity = float(obj.get("popularity") or 0.0)
            except Exception:
                popularity = 0.0
            original_title = str(obj.get("original_title") or "").strip()
            adult = bool(obj.get("adult") or False)
            yield IdRow(tmdb_id=tmdb_id, popularity=popularity, original_title=original_title, adult=adult)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Import TMDB daily movie id export into Postgres by fetching details and filtering by release_date."
    )
    p.add_argument("--ids-file", required=True, help="Path to TMDB daily export NDJSON file (movie ids).")
    p.add_argument(
        "--start-date",
        default=None,
        help="Inclusive start date (YYYY-MM-DD). Default: end_date - 365 days.",
    )
    p.add_argument(
        "--end-date",
        default=None,
        help="Inclusive end date (YYYY-MM-DD). Default: today (UTC).",
    )
    p.add_argument("--max-scanned", type=int, default=200000, help="Max NDJSON rows to scan.")
    p.add_argument("--max-imported", type=int, default=500, help="Stop after importing N movies.")
    p.add_argument("--min-popularity", type=float, default=5.0, help="Skip ids with popularity below this.")
    p.add_argument("--concurrency", type=int, default=5, help="Concurrent TMDB detail fetches.")
    p.add_argument("--language", default="zh-CN", help="TMDB language for details (default zh-CN).")
    p.add_argument(
        "--include-adult",
        action="store_true",
        help="Include adult movies (default: false).",
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip tmdb_id that already exists in Postgres (default: false).",
    )
    return p


def _release_date_in_range(release_date: Optional[str], start: date, end: date) -> bool:
    if not release_date:
        return False
    try:
        d = _parse_date(release_date)
    except Exception:
        return False
    return start <= d <= end


async def _run(
    *,
    ids_file: str,
    start_date: Optional[str],
    end_date: Optional[str],
    max_scanned: int,
    max_imported: int,
    min_popularity: float,
    concurrency: int,
    language: str,
    include_adult: bool,
    skip_existing: bool,
) -> int:
    if not os.path.exists(ids_file):
        logger.error("ids_file not found: %s", ids_file)
        return 2

    dsn = get_postgres_dsn()
    if not dsn:
        logger.error("Postgres not configured: set POSTGRES_DSN or POSTGRES_HOST/PORT/USER/PASSWORD/DB")
        return 2

    end = _parse_date(end_date) if end_date else _today_utc()
    start = _parse_date(start_date) if start_date else (end - timedelta(days=365))
    if start > end:
        logger.error("invalid date range: start_date=%s end_date=%s", start, end)
        return 2

    store = PostgresTmdbStore(dsn=dsn)
    client = TMDBClient()

    scanned = 0
    enqueued = 0
    imported = 0
    matched = 0
    skipped_existing_n = 0
    skipped_popularity_n = 0
    skipped_adult_n = 0
    fetched_n = 0

    q: asyncio.Queue[IdRow | None] = asyncio.Queue(maxsize=max(10, concurrency * 10))
    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def worker() -> None:
        nonlocal imported, matched, fetched_n, skipped_existing_n
        while True:
            item = await q.get()
            if item is None:
                q.task_done()
                return

            async with sem:
                try:
                    if skip_existing and await store.has_movie(tmdb_id=item.tmdb_id):
                        skipped_existing_n += 1
                        q.task_done()
                        continue

                    details = await client.get_movie_details(item.tmdb_id, language=language)
                    fetched_n += 1
                    if not isinstance(details, dict) or not details:
                        q.task_done()
                        continue

                    if _release_date_in_range(str(details.get("release_date") or ""), start, end):
                        matched += 1
                        await store.persist_enrichment(
                            user_id="seed",
                            session_id="seed",
                            query_text=f"ids_file:{os.path.basename(ids_file)}:{item.tmdb_id}",
                            tmdb_endpoint=f"/movie/{item.tmdb_id}",
                            extracted_entities=[item.original_title] if item.original_title else None,
                            disambiguation=[
                                {
                                    "type": "movie",
                                    "selected": {
                                        "id": int(item.tmdb_id),
                                        "score": 999.0,
                                    },
                                }
                            ],
                            payloads=[{"type": "movie", "data": details}],
                        )
                        imported += 1
                except Exception as e:
                    logger.debug("worker failed tmdb_id=%s err=%s", item.tmdb_id, e)
                finally:
                    q.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(max(1, concurrency))]

    try:
        for row in _iter_ndjson_ids(ids_file):
            scanned += 1
            if scanned > max_scanned:
                break

            if row.adult and not include_adult:
                skipped_adult_n += 1
                continue

            if row.popularity < float(min_popularity):
                skipped_popularity_n += 1
                continue

            if imported >= max_imported:
                break

            await q.put(row)
            enqueued += 1

            if scanned % 5000 == 0:
                logger.info(
                    "progress scanned=%s enqueued=%s fetched=%s matched=%s imported=%s (skip_existing=%s, skip_popularity=%s, skip_adult=%s)",
                    scanned,
                    enqueued,
                    fetched_n,
                    matched,
                    imported,
                    skipped_existing_n,
                    skipped_popularity_n,
                    skipped_adult_n,
                )

        # Drain queue
        await q.join()
    finally:
        for _ in workers:
            await q.put(None)
        await asyncio.gather(*workers, return_exceptions=True)
        await client.close()
        await store.close()

    logger.info(
        "done scanned=%s enqueued=%s fetched=%s matched=%s imported=%s (skip_existing=%s, skip_popularity=%s, skip_adult=%s)",
        scanned,
        enqueued,
        fetched_n,
        matched,
        imported,
        skipped_existing_n,
        skipped_popularity_n,
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
                start_date=args.start_date,
                end_date=args.end_date,
                max_scanned=int(args.max_scanned),
                max_imported=int(args.max_imported),
                min_popularity=float(args.min_popularity),
                concurrency=int(args.concurrency),
                language=str(args.language),
                include_adult=bool(args.include_adult),
                skip_existing=bool(args.skip_existing),
            )
        )
    )


if __name__ == "__main__":
    main()


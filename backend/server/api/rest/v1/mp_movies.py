from __future__ import annotations

import logging
import json
import time
import asyncio
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from pydantic import ConfigDict

from config.database import get_postgres_dsn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mp", tags=["mp-v1"])

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"

_AUTO_SEED_LAST_ATTEMPT: dict[str, float] = {}


def _img(path: Any, *, size: str) -> Optional[str]:
    p = str(path or "").strip()
    if not p:
        return None
    if not p.startswith("/"):
        p = "/" + p
    return f"{TMDB_IMAGE_BASE}/{size}{p}"


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_json_dict(value: Any) -> dict[str, Any] | None:
    """asyncpg may return jsonb as str unless a codec is registered."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def _extract_directors(raw: dict[str, Any] | None) -> list[str]:
    if not isinstance(raw, dict):
        return []
    credits = raw.get("credits")
    if not isinstance(credits, dict):
        return []
    crew = _as_list(credits.get("crew"))
    names: list[str] = []
    seen = set()
    for c in crew:
        if not isinstance(c, dict):
            continue
        if str(c.get("job") or "").strip().lower() != "director":
            continue
        name = str(c.get("name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _extract_top_cast(raw: dict[str, Any] | None, *, limit: int = 8) -> list[str]:
    if not isinstance(raw, dict):
        return []
    credits = raw.get("credits")
    if not isinstance(credits, dict):
        return []
    cast = _as_list(credits.get("cast"))
    out: list[str] = []
    for c in cast:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "").strip()
        if name:
            out.append(name)
        if limit and len(out) >= limit:
            break
    return out


def _extract_genres(raw: dict[str, Any] | None) -> list[str]:
    if not isinstance(raw, dict):
        return []
    genres = _as_list(raw.get("genres"))
    out: list[str] = []
    for g in genres:
        if not isinstance(g, dict):
            continue
        name = str(g.get("name") or "").strip()
        if name:
            out.append(name)
    return out


def _raw_needs_details(raw: dict[str, Any] | None) -> bool:
    """Best-effort heuristic: treat rows without credits/genres as incomplete snapshots."""
    if not isinstance(raw, dict) or not raw:
        return True
    credits = raw.get("credits")
    if not isinstance(credits, dict):
        return True
    crew = credits.get("crew")
    cast = credits.get("cast")
    genres = raw.get("genres")
    if not isinstance(crew, list) or len(crew) == 0:
        return True
    if not isinstance(cast, list) or len(cast) == 0:
        return True
    if not isinstance(genres, list) or len(genres) == 0:
        return True
    # Some incomplete snapshots include credits but miss the Director row.
    if not _extract_directors(raw):
        return True
    return False


def _year_from_release_date(release_date: Any) -> Optional[int]:
    if release_date is None:
        return None
    # asyncpg returns datetime.date for date columns.
    s = str(release_date)
    if len(s) >= 4 and s[:4].isdigit():
        y = int(s[:4])
        if 1800 <= y <= 2500:
            return y
    return None


class MovieCard(BaseModel):
    tmdb_id: int
    title: str = ""
    release_date: Optional[str] = None
    year: Optional[int] = None
    poster_url: Optional[str] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
    directors: list[str] = Field(default_factory=list)
    top_cast: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)


class MovieDetail(BaseModel):
    tmdb_id: int
    title: str = ""
    original_title: Optional[str] = None
    overview: Optional[str] = None
    release_date: Optional[str] = None
    year: Optional[int] = None
    runtime: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
    directors: list[str] = Field(default_factory=list)
    top_cast: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    cast: list[dict[str, Any]] = Field(default_factory=list)
    crew: list[dict[str, Any]] = Field(default_factory=list)


class MoviesBulkRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # MVP contract uses `ids`; keep `tmdb_ids` as internal name for clarity.
    tmdb_ids: list[int] = Field(default_factory=list, alias="ids")


class MoviesBulkResponse(BaseModel):
    items: list[MovieCard] = Field(default_factory=list)
    missing_ids: list[int] = Field(default_factory=list)


class MovieDetailResponse(BaseModel):
    movie: MovieDetail


class MoviesFeedResponse(BaseModel):
    items: list[MovieCard] = Field(default_factory=list)
    next_offset: int = 0


@lru_cache(maxsize=1)
def _get_tmdb_store():
    dsn = get_postgres_dsn()
    if not dsn:
        return None
    from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

    return PostgresTmdbStore(dsn=dsn)


def _row_to_card(row: dict[str, Any]) -> MovieCard:
    raw = _as_json_dict(row.get("raw"))
    return MovieCard(
        tmdb_id=int(row.get("tmdb_id")),
        title=str(row.get("title") or ""),
        release_date=str(row.get("release_date") or "") or None,
        year=_year_from_release_date(row.get("release_date")),
        poster_url=_img((raw or {}).get("poster_path"), size="w500"),
        vote_average=row.get("vote_average"),
        vote_count=row.get("vote_count"),
        popularity=row.get("popularity"),
        directors=_extract_directors(raw),
        top_cast=_extract_top_cast(raw, limit=5),
        genres=_extract_genres(raw),
    )


def _row_to_detail(row: dict[str, Any]) -> MovieDetail:
    raw = _as_json_dict(row.get("raw"))
    credits = (raw or {}).get("credits") if isinstance((raw or {}).get("credits"), dict) else {}
    cast_raw = credits.get("cast") if isinstance(credits, dict) else None
    crew_raw = credits.get("crew") if isinstance(credits, dict) else None
    cast_items = []
    for c in _as_list(cast_raw)[:20]:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        cast_items.append({"name": name, "character": str(c.get("character") or "").strip() or None})
    crew_items = []
    for c in _as_list(crew_raw)[:30]:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "").strip()
        job = str(c.get("job") or "").strip()
        if not name or not job:
            continue
        if job.lower() in {"director", "writer", "screenplay", "producer"}:
            crew_items.append({"name": name, "job": job})

    return MovieDetail(
        tmdb_id=int(row.get("tmdb_id")),
        title=str(row.get("title") or ""),
        original_title=row.get("original_title"),
        overview=str((raw or {}).get("overview") or "") or None,
        release_date=str(row.get("release_date") or "") or None,
        year=_year_from_release_date(row.get("release_date")),
        runtime=(raw or {}).get("runtime") if isinstance((raw or {}).get("runtime"), int) else None,
        poster_url=_img((raw or {}).get("poster_path"), size="w500"),
        backdrop_url=_img((raw or {}).get("backdrop_path"), size="w780"),
        vote_average=row.get("vote_average"),
        vote_count=row.get("vote_count"),
        popularity=row.get("popularity"),
        directors=_extract_directors(raw),
        top_cast=_extract_top_cast(raw, limit=8),
        genres=_extract_genres(raw),
        cast=cast_items,
        crew=crew_items,
    )


@router.post("/movies/bulk", response_model=MoviesBulkResponse)
async def mp_movies_bulk(request: MoviesBulkRequest) -> MoviesBulkResponse:
    store = _get_tmdb_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Postgres not configured")

    # Preserve input order and avoid duplicates.
    ordered: list[int] = []
    seen = set()
    for mid in request.tmdb_ids:
        try:
            v = int(mid)
        except Exception:
            continue
        if v not in seen:
            seen.add(v)
            ordered.append(v)

    rows = await store.get_movies(tmdb_ids=ordered)
    by_id: dict[int, dict[str, Any]] = {
        int(r.get("tmdb_id")): r
        for r in rows
        if isinstance(r, dict) and r.get("tmdb_id") is not None
    }

    # Fetch-through on miss: streaming chat returns TMDB ids first, and persistence may be
    # async; ensure MiniProgram can still render cards by backfilling from TMDB.
    missing_now = [mid for mid in ordered if mid not in by_id]
    incomplete_now: list[int] = []
    for mid, row in by_id.items():
        raw = _as_json_dict(row.get("raw"))
        if _raw_needs_details(raw):
            incomplete_now.append(int(mid))

    fetch_through_ids = []
    for mid in ordered:
        if mid in missing_now or mid in incomplete_now:
            fetch_through_ids.append(mid)

    if fetch_through_ids:
        try:
            from infrastructure.enrichment.tmdb_client import TMDBClient

            client = TMDBClient()

            async def _fetch(mid: int) -> dict[str, Any] | None:
                details = await client.get_movie_details(int(mid), language="zh-CN")
                return details if isinstance(details, dict) and details else None

            fetched = await asyncio.gather(*[_fetch(mid) for mid in fetch_through_ids[:20]], return_exceptions=True)
            payloads: list[dict[str, Any]] = []
            for r in fetched:
                if isinstance(r, dict) and r:
                    payloads.append({"type": "movie", "data": r})

            if payloads:
                await store.persist_enrichment(
                    user_id="mp",
                    session_id="mp",
                    query_text="mp_movies_bulk_fetch_through",
                    tmdb_endpoint="/movies/bulk",
                    extracted_entities=None,
                    disambiguation=[],
                    payloads=payloads,
                )
                rows2 = await store.get_movies(tmdb_ids=fetch_through_ids)
                for r in rows2:
                    if isinstance(r, dict) and r.get("tmdb_id") is not None:
                        by_id[int(r["tmdb_id"])] = r
            await client.close()
        except Exception as e:
            logger.warning(
                "mp movies bulk fetch-through failed ids=%s err=%s", len(fetch_through_ids), e
            )

    items: list[MovieCard] = []
    missing: list[int] = []
    for mid in ordered:
        row = by_id.get(mid)
        if row is None:
            missing.append(mid)
            continue
        items.append(_row_to_card(row))

    return MoviesBulkResponse(items=items, missing_ids=missing)


@router.get("/movies/feed", response_model=MoviesFeedResponse)
async def mp_movies_feed(
    type: str = Query("popular", pattern="^(popular|now_playing|upcoming)$"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> MoviesFeedResponse:
    store = _get_tmdb_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Postgres not configured")

    rows = await store.list_movies_feed(feed_type=type, limit=limit, offset=offset)
    # upcoming/now_playing may be empty if local snapshots are stale (e.g. DB has 2024/2025 data
    # but current_date is 2026). Best-effort auto seed the browse list once in a while.
    if not rows and offset == 0 and type in {"upcoming", "now_playing"}:
        last = _AUTO_SEED_LAST_ATTEMPT.get(type, 0.0)
        now = time.time()
        if now - last > 300:  # 5 minutes
            _AUTO_SEED_LAST_ATTEMPT[type] = now
            try:
                from infrastructure.enrichment.tmdb_client import TMDBClient

                client = TMDBClient()
                today = date.today()
                if type == "upcoming":
                    filters = {
                        "date_range": {
                            "gte": today.isoformat(),
                            "lte": (today + timedelta(days=180)).isoformat(),
                        }
                    }
                else:
                    filters = {
                        "date_range": {
                            "gte": (today - timedelta(days=90)).isoformat(),
                            "lte": today.isoformat(),
                        }
                    }

                raw = await client.discover_movie_raw(
                    language="zh-CN",
                    page=1,
                    sort_by="popularity.desc",
                    filters=filters,
                )
                results = raw.get("results") if isinstance(raw, dict) else None
                ids: list[int] = []
                if isinstance(results, list):
                    for r in results[:40]:
                        if not isinstance(r, dict):
                            continue
                        mid = r.get("id")
                        try:
                            ids.append(int(mid))
                        except Exception:
                            continue

                for mid in ids[:20]:
                    details = await client.get_movie_details(int(mid), language="zh-CN")
                    if isinstance(details, dict) and details:
                        await store.persist_enrichment(
                            user_id="mp",
                            session_id="mp",
                            query_text=f"mp_seed:{type}:{mid}",
                            tmdb_endpoint="/discover/movie",
                            extracted_entities=None,
                            disambiguation=[
                                {"type": "movie", "selected": {"id": int(mid), "score": 999.0}}
                            ],
                            payloads=[{"type": "movie", "data": details}],
                        )
                await client.close()
            except Exception as e:
                logger.warning("mp feed auto-seed failed feed=%s err=%s", type, e)
            rows = await store.list_movies_feed(feed_type=type, limit=limit, offset=offset)
    items = [_row_to_card(r) for r in rows if isinstance(r, dict)]
    return MoviesFeedResponse(items=items, next_offset=offset + len(items))


@router.get("/movies/{tmdb_id}", response_model=MovieDetailResponse)
async def mp_movie_detail(tmdb_id: int) -> MovieDetailResponse:
    store = _get_tmdb_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Postgres not configured")

    row = await store.get_movie(tmdb_id=tmdb_id)
    needs_fetch = False
    if row is None:
        needs_fetch = True
    else:
        raw = _as_json_dict(row.get("raw"))
        if _raw_needs_details(raw):
            needs_fetch = True

    if needs_fetch:
        # Best-effort fetch-through on miss or incomplete snapshot, if TMDB is configured.
        try:
            from infrastructure.enrichment.tmdb_client import TMDBClient

            client = TMDBClient()
            details = await client.get_movie_details(int(tmdb_id), language="zh-CN")
            await client.close()
            if isinstance(details, dict) and details:
                await store.persist_enrichment(
                    user_id="mp",
                    session_id="mp",
                    query_text=f"movie_id:{tmdb_id}",
                    tmdb_endpoint=f"/movie/{tmdb_id}",
                    extracted_entities=None,
                    disambiguation=[{"type": "movie", "selected": {"id": int(tmdb_id), "score": 999.0}}],
                    payloads=[{"type": "movie", "data": details}],
                )
                row = await store.get_movie(tmdb_id=tmdb_id)
        except Exception as e:
            logger.warning("mp movie detail fetch-through failed tmdb_id=%s err=%s", tmdb_id, e)

    if row is None:
        raise HTTPException(status_code=404, detail="movie not found")

    return MovieDetailResponse(movie=_row_to_detail(row))


__all__ = [
    "router",
    "MovieCard",
    "MovieDetail",
]

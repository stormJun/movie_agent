"""
TMDB API HTTP client for fetching movie data.

This module provides an async HTTP client for interacting with The Movie Database (TMDB) API,
following the same patterns as Mem0HttpMemoryStore for consistency.
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import re
from typing import Any

import aiohttp

from infrastructure.config.settings import (
    TMDB_API_KEY,
    TMDB_API_TOKEN,
    TMDB_BASE_URL,
    TMDB_TIMEOUT_S,
)

logger = logging.getLogger(__name__)


def _extract_year(text: str) -> int | None:
    """Extract a plausible release year from user text."""
    if not text:
        return None
    m = re.search(r"(19\\d{2}|20\\d{2})", text)
    if not m:
        return None
    try:
        year = int(m.group(1))
    except Exception:
        return None
    if 1880 <= year <= 2100:
        return year
    return None


def _normalize_title(s: str) -> str:
    s = (s or "").strip().lower()
    # Remove common punctuation/whitespace to make fuzzy matching less brittle.
    s = re.sub(r"[\\s\\-_:：·'\"“”‘’《》()（）\\[\\]{}.,!?，。！？;；/\\\\]+", "", s)
    return s


def _extract_person_role_hint(text: str) -> str | None:
    """Best-effort role hint from a query for person disambiguation."""
    q = (text or "").lower()
    if not q:
        return None
    # Chinese + English keywords.
    if ("导演" in q) or ("director" in q):
        return "Directing"
    if ("演员" in q) or ("主演" in q) or ("actor" in q) or ("actress" in q) or ("cast" in q):
        return "Acting"
    if ("编剧" in q) or ("writer" in q) or ("screenplay" in q):
        return "Writing"
    return None


def _score_movie_candidate(*, query_title: str, candidate: dict[str, Any], target_year: int | None) -> float:
    """Score a TMDB search result to pick the best match for a title."""
    qt_raw = (query_title or "").strip()
    qt = _normalize_title(qt_raw)
    title = str(candidate.get("title") or "").strip()
    original_title = str(candidate.get("original_title") or "").strip()
    ct = _normalize_title(title)
    cot = _normalize_title(original_title)

    score = 0.0

    # Strong signals: exact match.
    if qt and (qt == ct):
        score += 5.0
    elif qt and (qt == cot):
        score += 4.0

    # Medium signals: substring containment.
    if qt and ct and (qt in ct or ct in qt):
        score += 2.0
    if qt and cot and (qt in cot or cot in qt):
        score += 2.0

    # Fuzzy similarity.
    if qt and (ct or cot):
        best = max(
            difflib.SequenceMatcher(a=qt, b=ct).ratio() if ct else 0.0,
            difflib.SequenceMatcher(a=qt, b=cot).ratio() if cot else 0.0,
        )
        if best >= 0.85:
            score += 2.0
        elif best >= 0.75:
            score += 1.0

    # Year alignment (when available).
    if target_year is not None:
        release_date = str(candidate.get("release_date") or "").strip()
        try:
            release_year = int(release_date[:4]) if len(release_date) >= 4 else None
        except Exception:
            release_year = None
        if release_year is not None:
            if release_year == target_year:
                score += 3.0
            elif abs(release_year - target_year) <= 1:
                score += 1.0
            elif abs(release_year - target_year) >= 5:
                score -= 3.0

    # Weak signals: usable description and a bit of popularity to break ties.
    overview = str(candidate.get("overview") or "").strip()
    if len(overview) >= 30:
        score += 0.5
    try:
        vote_count = float(candidate.get("vote_count") or 0.0)
        popularity = float(candidate.get("popularity") or 0.0)
        score += min(vote_count / 10000.0, 0.5)
        score += min(popularity / 1000.0, 0.5)
    except Exception:
        pass

    return score


def _score_tv_candidate(*, query_title: str, candidate: dict[str, Any], target_year: int | None) -> float:
    """Score a TMDB TV search result to pick the best match for a title."""
    qt_raw = (query_title or "").strip()
    qt = _normalize_title(qt_raw)
    name = str(candidate.get("name") or "").strip()
    original_name = str(candidate.get("original_name") or "").strip()
    cn = _normalize_title(name)
    con = _normalize_title(original_name)

    score = 0.0

    if qt and (qt == cn):
        score += 5.0
    elif qt and (qt == con):
        score += 4.0

    if qt and cn and (qt in cn or cn in qt):
        score += 2.0
    if qt and con and (qt in con or con in qt):
        score += 2.0

    if qt and (cn or con):
        best = max(
            difflib.SequenceMatcher(a=qt, b=cn).ratio() if cn else 0.0,
            difflib.SequenceMatcher(a=qt, b=con).ratio() if con else 0.0,
        )
        if best >= 0.85:
            score += 2.0
        elif best >= 0.75:
            score += 1.0

    if target_year is not None:
        first_air_date = str(candidate.get("first_air_date") or "").strip()
        try:
            air_year = int(first_air_date[:4]) if len(first_air_date) >= 4 else None
        except Exception:
            air_year = None
        if air_year is not None:
            if air_year == target_year:
                score += 3.0
            elif abs(air_year - target_year) <= 1:
                score += 1.0
            elif abs(air_year - target_year) >= 5:
                score -= 3.0

    overview = str(candidate.get("overview") or "").strip()
    if len(overview) >= 30:
        score += 0.5
    try:
        vote_count = float(candidate.get("vote_count") or 0.0)
        popularity = float(candidate.get("popularity") or 0.0)
        score += min(vote_count / 10000.0, 0.5)
        score += min(popularity / 1000.0, 0.5)
    except Exception:
        pass

    return score


def _score_person_candidate(
    *,
    query_name: str,
    candidate: dict[str, Any],
    role_hint: str | None,
) -> float:
    """Score a TMDB person search result to pick the best match for a name."""
    qn_raw = (query_name or "").strip()
    qn = _normalize_title(qn_raw)
    name = str(candidate.get("name") or "").strip()
    original_name = str(candidate.get("original_name") or "").strip()
    cn = _normalize_title(name)
    con = _normalize_title(original_name)

    score = 0.0

    # Strong: exact match.
    if qn and (qn == cn):
        score += 5.0
    elif qn and (qn == con):
        score += 4.0

    # Medium: containment.
    if qn and cn and (qn in cn or cn in qn):
        score += 2.0
    if qn and con and (qn in con or con in qn):
        score += 2.0

    # Fuzzy similarity.
    if qn and (cn or con):
        best = max(
            difflib.SequenceMatcher(a=qn, b=cn).ratio() if cn else 0.0,
            difflib.SequenceMatcher(a=qn, b=con).ratio() if con else 0.0,
        )
        if best >= 0.85:
            score += 2.0
        elif best >= 0.75:
            score += 1.0

    # Department hint (director/actor/etc.).
    dept = str(candidate.get("known_for_department") or "").strip()
    if role_hint and dept:
        if dept.lower() == role_hint.lower():
            score += 1.5
        else:
            score -= 0.5

    # Popularity as tie-breaker.
    try:
        popularity = float(candidate.get("popularity") or 0.0)
        score += min(popularity / 100.0, 1.0)
    except Exception:
        pass

    return score


def _pick_best_candidate(
    *,
    query_title: str,
    candidates: list[dict[str, Any]],
    target_year: int | None,
    top_k: int = 3,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for c in candidates or []:
        scored.append((_score_movie_candidate(query_title=query_title, candidate=c, target_year=target_year), c))
    scored.sort(key=lambda x: x[0], reverse=True)

    top: list[dict[str, Any]] = []
    for s, c in scored[: int(top_k)]:
        top.append(
            {
                "id": c.get("id"),
                "title": c.get("title"),
                "original_title": c.get("original_title"),
                "release_date": c.get("release_date"),
                "score": float(s),
            }
        )

    return (scored[0][1] if scored else None), top


def _pick_best_person_candidate(
    *,
    query_name: str,
    candidates: list[dict[str, Any]],
    role_hint: str | None,
    top_k: int = 3,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for c in candidates or []:
        scored.append(
            (
                _score_person_candidate(query_name=query_name, candidate=c, role_hint=role_hint),
                c,
            )
        )
    scored.sort(key=lambda x: x[0], reverse=True)

    top: list[dict[str, Any]] = []
    for s, c in scored[: int(top_k)]:
        top.append(
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "original_name": c.get("original_name"),
                "known_for_department": c.get("known_for_department"),
                "score": float(s),
            }
        )

    return (scored[0][1] if scored else None), top


class TMDBClient:
    """Async HTTP client for TMDB API.

    This client manages HTTP connections to TMDB API with proper session handling,
    timeout configuration, and error handling.

    Attributes:
        _base_url: TMDB API base URL
        _api_token: TMDB API bearer token (JWT)
        _timeout_s: Request timeout in seconds
        _session: aiohttp ClientSession (lazily initialized)
        _lock: Async lock for thread-safe session creation
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_token: str | None = None,
        api_key: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        """Initialize the TMDB client.

        Args:
            base_url: TMDB API base URL (default: from settings)
            api_token: TMDB API bearer token (default: from settings)
            timeout_s: Request timeout in seconds (default: from settings)
        """
        self._base_url = (base_url or TMDB_BASE_URL or "").rstrip("/")
        self._api_token = (api_token or TMDB_API_TOKEN or "").strip()
        self._api_key = (api_key or TMDB_API_KEY or "").strip()
        self._timeout_s = float(timeout_s or TMDB_TIMEOUT_S or 10.0)
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    def _headers(self) -> dict[str, str]:
        """Build HTTP headers for TMDB API requests.

        Returns:
            Dictionary of HTTP headers including Authorization bearer token.
        """
        headers = {"accept": "application/json"}
        # Prefer v4 bearer token auth when available.
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        return headers

    def _auth_params(self) -> dict[str, str]:
        """v3 auth via api_key query param (used when bearer token is absent)."""
        if self._api_token:
            return {}
        if self._api_key:
            return {"api_key": self._api_key}
        return {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session in a thread-safe manner.

        This implements double-checked locking pattern for lazy session initialization.

        Returns:
            An active aiohttp ClientSession.
        """
        if self._session is not None and not self._session.closed:
            return self._session

        async with self._lock:
            # Double-check after acquiring lock
            if self._session is not None and not self._session.closed:
                return self._session

            timeout = aiohttp.ClientTimeout(total=self._timeout_s)
            self._session = aiohttp.ClientSession(timeout=timeout)
            return self._session

    async def search_movie(self, title: str) -> dict[str, Any] | None:
        """Resolve a movie title into a detailed movie payload.

        Args:
            title: Movie title to search for

        Returns:
            Movie details dictionary including credits, or None when not found.
        """
        details, _ = await self.resolve_movie(title=title, query=title)
        return details

    async def search_movies(
        self, *, title: str, language: str, primary_release_year: int | None = None
    ) -> list[dict[str, Any]]:
        """Search for movies by title (returns the raw search results list)."""
        if not self._base_url or not (self._api_token or self._api_key):
            logger.warning("TMDB client not configured (missing base_url or auth)")
            return []

        try:
            session = await self._get_session()
            # Use direct concatenation to avoid urljoin eating the /3 path
            url = f"{self._base_url}/search/movie"
            params = {
                "query": title,
                "language": language,
                "page": 1,
                "include_adult": "false",
            }
            if primary_release_year is not None:
                # TMDB supports this filter; it helps disambiguate common titles.
                params["primary_release_year"] = int(primary_release_year)
            params.update(self._auth_params())

            logger.debug("TMDB search url=%s params=%s", url, params)

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB search failed ({resp.status}): {error_text[:200]}")
                    return []

                data = await resp.json(content_type=None)

            results = data.get("results", []) or []
            if not isinstance(results, list):
                return []
            return [r for r in results if isinstance(r, dict)]

        except asyncio.TimeoutError:
            logger.error(f"TMDB search timeout after {self._timeout_s}s for '{title}'")
            return []
        except Exception as e:
            logger.exception(f"TMDB search failed for '{title}': {e}")
            return []

    async def resolve_movie(self, *, title: str, query: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Search and disambiguate a movie by title, then fetch full details.

        Returns:
            (details, meta) where meta includes selection diagnostics.
        """
        meta: dict[str, Any] = {"type": "movie", "query_title": title}
        if not self._base_url or not (self._api_token or self._api_key):
            meta["error"] = "tmdb_not_configured"
            return None, meta

        target_year = _extract_year(query)
        meta["target_year"] = target_year

        # Try Chinese first, then English as a fallback.
        for lang in ("zh-CN", "en-US"):
            candidates = await self.search_movies(
                title=title, language=lang, primary_release_year=target_year
            )
            if not candidates:
                continue

            best, top = _pick_best_candidate(query_title=title, candidates=candidates[:10], target_year=target_year)
            meta["language"] = lang
            meta["candidates_top3"] = top

            if not best or not best.get("id"):
                continue

            best_score = float(top[0]["score"]) if top else 0.0
            meta["selected"] = {
                "id": best.get("id"),
                "title": best.get("title"),
                "original_title": best.get("original_title"),
                "release_date": best.get("release_date"),
                "score": best_score,
            }

            # Require a minimal confidence to avoid injecting wrong facts.
            if best_score < 4.0:
                meta["rejected"] = "low_score"
                return None, meta

            details_zh = await self.get_movie_details(int(best["id"]), language="zh-CN")
            if details_zh is None:
                meta["error"] = "details_fetch_failed"
                return None, meta

            # If zh overview is missing, pull English overview as fallback.
            overview = str(details_zh.get("overview") or "").strip()
            if not overview:
                details_en = await self.get_movie_details(int(best["id"]), language="en-US")
                if details_en and str(details_en.get("overview") or "").strip():
                    details_zh["overview"] = str(details_en.get("overview") or "")
                    meta["overview_fallback_language"] = "en-US"

            return details_zh, meta

        meta["rejected"] = "no_candidates"
        return None, meta

    async def search_people(self, *, name: str, language: str) -> list[dict[str, Any]]:
        """Search for people by name (returns the raw search results list)."""
        if not self._base_url or not (self._api_token or self._api_key):
            logger.warning("TMDB client not configured (missing base_url or auth)")
            return []

        try:
            session = await self._get_session()
            url = f"{self._base_url}/search/person"
            params = {
                "query": name,
                "language": language,
                "page": 1,
                "include_adult": "false",
            }
            params.update(self._auth_params())

            logger.debug("TMDB person search url=%s params=%s", url, params)

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB person search failed ({resp.status}): {error_text[:200]}")
                    return []

                data = await resp.json(content_type=None)

            results = data.get("results", []) or []
            if not isinstance(results, list):
                return []
            return [r for r in results if isinstance(r, dict)]
        except asyncio.TimeoutError:
            logger.error(f"TMDB person search timeout after {self._timeout_s}s for '{name}'")
            return []
        except Exception as e:
            logger.exception(f"TMDB person search failed for '{name}': {e}")
            return []

    async def search_multi(self, *, query: str, language: str) -> list[dict[str, Any]]:
        """Search across media types (movie/tv/person) using TMDB's multi search."""
        raw = await self.search_multi_raw(query=query, language=language)
        if not isinstance(raw, dict):
            return []
        results = raw.get("results", []) or []
        if not isinstance(results, list):
            return []
        return [r for r in results if isinstance(r, dict)]

    async def search_multi_raw(self, *, query: str, language: str) -> dict[str, Any] | None:
        """Search across media types (movie/tv/person) using TMDB's multi search (raw payload)."""
        if not self._base_url or not (self._api_token or self._api_key):
            logger.warning("TMDB client not configured (missing base_url or auth)")
            return None

        try:
            session = await self._get_session()
            url = f"{self._base_url}/search/multi"
            params = {
                "query": query,
                "language": language,
                "page": 1,
                "include_adult": "false",
            }
            params.update(self._auth_params())

            logger.debug("TMDB multi search url=%s params=%s", url, params)

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB multi search failed ({resp.status}): {error_text[:200]}")
                    return None

                data = await resp.json(content_type=None)
            return data if isinstance(data, dict) else None
        except asyncio.TimeoutError:
            logger.error(f"TMDB multi search timeout after {self._timeout_s}s for '{query}'")
            return None
        except Exception as e:
            logger.exception(f"TMDB multi search failed for '{query}': {e}")
            return None

    async def get_person_details(
        self, person_id: int, *, language: str = "zh-CN"
    ) -> dict[str, Any] | None:
        """Fetch detailed person information including combined credits."""
        if not self._base_url or not (self._api_token or self._api_key):
            return None

        try:
            session = await self._get_session()
            url = f"{self._base_url}/person/{person_id}"
            params = {"language": language, "append_to_response": "combined_credits"}
            params.update(self._auth_params())

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB person details failed ({resp.status}): {error_text[:200]}")
                    return None
                return await resp.json(content_type=None)
        except Exception as e:
            logger.exception(f"TMDB get_person_details failed for id={person_id}: {e}")
            return None

    async def get_tv_details(self, tv_id: int, *, language: str = "zh-CN") -> dict[str, Any] | None:
        """Fetch detailed TV information including credits."""
        if not self._base_url or not (self._api_token or self._api_key):
            return None

        try:
            session = await self._get_session()
            url = f"{self._base_url}/tv/{tv_id}"
            params = {"language": language, "append_to_response": "credits"}
            params.update(self._auth_params())

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB tv details failed ({resp.status}): {error_text[:200]}")
                    return None
                return await resp.json(content_type=None)
        except Exception as e:
            logger.exception(f"TMDB get_tv_details failed for id={tv_id}: {e}")
            return None

    async def discover_chinese_tv(
        self,
        *,
        language: str = "zh-CN",
        page: int = 1,
        sort_by: str = "popularity.desc",
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Discover Chinese TV series (best-effort, for recommendation-style queries)."""
        raw = await self.discover_tv_raw(
            language=language,
            page=page,
            sort_by=sort_by,
            filters={"origin_country": "CN", "original_language": "zh"},
        )
        if not isinstance(raw, dict):
            return []
        results = raw.get("results", []) or []
        if not isinstance(results, list):
            return []
        out = [r for r in results if isinstance(r, dict)]
        return out[: max_results if max_results and max_results > 0 else len(out)]

    async def discover_tv_raw(
        self,
        *,
        language: str = "zh-CN",
        page: int = 1,
        sort_by: str = "popularity.desc",
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Discover TV series (raw payload)."""
        if not self._base_url or not (self._api_token or self._api_key):
            logger.warning("TMDB client not configured (missing base_url or auth)")
            return None

        try:
            session = await self._get_session()
            url = f"{self._base_url}/discover/tv"
            params: dict[str, Any] = {
                "language": language,
                "page": page,
                "sort_by": sort_by,
                "include_adult": "false",
            }
            f = filters if isinstance(filters, dict) else {}
            origin_country = f.get("origin_country")
            if isinstance(origin_country, str) and origin_country.strip():
                params["with_origin_country"] = origin_country.strip()
            original_language = f.get("original_language")
            if isinstance(original_language, str) and original_language.strip():
                params["with_original_language"] = original_language.strip()
            year = f.get("year")
            if isinstance(year, int) and 1900 <= year <= 2100:
                params["first_air_date_year"] = year
            dr = f.get("date_range")
            if isinstance(dr, dict):
                gte = dr.get("gte")
                lte = dr.get("lte")
                if isinstance(gte, str) and gte.strip():
                    params["first_air_date.gte"] = gte.strip()
                if isinstance(lte, str) and lte.strip():
                    params["first_air_date.lte"] = lte.strip()
            params.update(self._auth_params())

            logger.debug("TMDB discover tv url=%s params=%s", url, params)

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB discover tv failed ({resp.status}): {error_text[:200]}")
                    return None
                data = await resp.json(content_type=None)
            return data if isinstance(data, dict) else None
        except asyncio.TimeoutError:
            logger.error(f"TMDB discover tv timeout after {self._timeout_s}s")
            return None
        except Exception as e:
            logger.exception(f"TMDB discover tv failed: {e}")
            return None

    async def discover_movie_raw(
        self,
        *,
        language: str = "zh-CN",
        page: int = 1,
        sort_by: str = "popularity.desc",
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Discover movies (raw payload)."""
        if not self._base_url or not (self._api_token or self._api_key):
            logger.warning("TMDB client not configured (missing base_url or auth)")
            return None

        try:
            session = await self._get_session()
            url = f"{self._base_url}/discover/movie"
            params: dict[str, Any] = {
                "language": language,
                "page": page,
                "sort_by": sort_by,
                "include_adult": "false",
            }
            f = filters if isinstance(filters, dict) else {}
            region = f.get("region")
            if isinstance(region, str) and region.strip():
                params["region"] = region.strip()
            origin_country = f.get("origin_country")
            if isinstance(origin_country, str) and origin_country.strip():
                # Best-effort: TMDB supports with_origin_country for discover.
                params["with_origin_country"] = origin_country.strip()
            original_language = f.get("original_language")
            if isinstance(original_language, str) and original_language.strip():
                params["with_original_language"] = original_language.strip()
            year = f.get("year")
            if isinstance(year, int) and 1900 <= year <= 2100:
                params["primary_release_year"] = year
            dr = f.get("date_range")
            if isinstance(dr, dict):
                gte = dr.get("gte")
                lte = dr.get("lte")
                if isinstance(gte, str) and gte.strip():
                    params["primary_release_date.gte"] = gte.strip()
                if isinstance(lte, str) and lte.strip():
                    params["primary_release_date.lte"] = lte.strip()
            params.update(self._auth_params())

            logger.debug("TMDB discover movie url=%s params=%s", url, params)

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB discover movie failed ({resp.status}): {error_text[:200]}")
                    return None
                data = await resp.json(content_type=None)
            return data if isinstance(data, dict) else None
        except asyncio.TimeoutError:
            logger.error(f"TMDB discover movie timeout after {self._timeout_s}s")
            return None
        except Exception as e:
            logger.exception(f"TMDB discover movie failed: {e}")
            return None

    async def movie_list_raw(
        self,
        *,
        list_type: str,
        language: str = "zh-CN",
        page: int = 1,
        region: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a movie list page.

        TMDB movie lists:
        - /movie/popular
        - /movie/top_rated
        - /movie/now_playing
        - /movie/upcoming

        Notes:
        - TMDB enforces max page=500 for list endpoints.
        - Some list endpoints accept a `region` hint; we pass it when provided.
        """
        if not self._base_url or not (self._api_token or self._api_key):
            logger.warning("TMDB client not configured (missing base_url or auth)")
            return None

        lt = (list_type or "").strip().lower()
        if lt not in {"popular", "top_rated", "now_playing", "upcoming"}:
            raise ValueError(f"unsupported list_type={list_type!r}")

        try:
            session = await self._get_session()
            url = f"{self._base_url}/movie/{lt}"
            params: dict[str, Any] = {"language": language, "page": int(page)}
            if isinstance(region, str) and region.strip():
                params["region"] = region.strip()
            params.update(self._auth_params())

            logger.debug("TMDB movie list url=%s params=%s", url, params)

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB movie list failed ({resp.status}): {error_text[:200]}")
                    return None
                data = await resp.json(content_type=None)
            return data if isinstance(data, dict) else None
        except asyncio.TimeoutError:
            logger.error(f"TMDB movie list timeout after {self._timeout_s}s list={lt} page={page}")
            return None
        except Exception as e:
            logger.exception(f"TMDB movie list failed list={lt} page={page}: {e}")
            return None

    async def movie_recommendations_raw(
        self,
        *,
        movie_id: int,
        language: str = "zh-CN",
        page: int = 1,
    ) -> dict[str, Any] | None:
        """Fetch TMDB /movie/{movie_id}/recommendations (raw payload)."""
        if not self._base_url or not (self._api_token or self._api_key):
            logger.warning("TMDB client not configured (missing base_url or auth)")
            return None
        try:
            session = await self._get_session()
            url = f"{self._base_url}/movie/{int(movie_id)}/recommendations"
            params: dict[str, Any] = {"language": language, "page": page}
            params.update(self._auth_params())
            logger.debug("TMDB movie recommendations url=%s params=%s", url, params)
            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB movie recommendations failed ({resp.status}): {error_text[:200]}")
                    return None
                data = await resp.json(content_type=None)
            return data if isinstance(data, dict) else None
        except asyncio.TimeoutError:
            logger.error(f"TMDB movie recommendations timeout after {self._timeout_s}s")
            return None
        except Exception as e:
            logger.exception(f"TMDB movie recommendations failed for id={movie_id}: {e}")
            return None

    async def resolve_entity_via_multi(
        self, *, text: str, query: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Resolve an entity as either a movie, tv, or person using /search/multi.

        This reduces wasted requests compared to "try movie then person".
        Returns:
            (payload, meta) where payload is {"type": "movie|tv|person", "data": {...}}.
        """
        meta: dict[str, Any] = {"query_text": text, "entity": text}
        if not self._base_url or not (self._api_token or self._api_key):
            meta["error"] = "tmdb_not_configured"
            return None, meta

        target_year = _extract_year(query)
        role_hint = _extract_person_role_hint(query)
        meta["target_year"] = target_year
        meta["role_hint"] = role_hint

        def _score_multi_candidate(candidate: dict[str, Any]) -> float:
            media_type = str(candidate.get("media_type") or "").strip().lower()
            if media_type == "movie":
                return _score_movie_candidate(
                    query_title=text, candidate=candidate, target_year=target_year
                )
            if media_type == "tv":
                return _score_tv_candidate(
                    query_title=text, candidate=candidate, target_year=target_year
                )
            if media_type == "person":
                return _score_person_candidate(
                    query_name=text, candidate=candidate, role_hint=role_hint
                )
            return -999.0

        def _candidate_view(candidate: dict[str, Any], score: float) -> dict[str, Any]:
            media_type = str(candidate.get("media_type") or "").strip().lower()
            view: dict[str, Any] = {"media_type": media_type, "id": candidate.get("id"), "score": float(score)}
            if media_type == "movie":
                view.update(
                    {
                        "title": candidate.get("title"),
                        "original_title": candidate.get("original_title"),
                        "release_date": candidate.get("release_date"),
                    }
                )
            elif media_type == "tv":
                view.update(
                    {
                        "name": candidate.get("name"),
                        "original_name": candidate.get("original_name"),
                        "first_air_date": candidate.get("first_air_date"),
                    }
                )
            elif media_type == "person":
                view.update(
                    {
                        "name": candidate.get("name"),
                        "original_name": candidate.get("original_name"),
                        "known_for_department": candidate.get("known_for_department"),
                    }
                )
            return view

        # Try Chinese first, then English as a fallback.
        for lang in ("zh-CN", "en-US"):
            raw = await self.search_multi_raw(query=text, language=lang)
            results = []
            if isinstance(raw, dict):
                results = raw.get("results", []) or []
                if not isinstance(results, list):
                    results = []

            candidates = [
                r
                for r in (results or [])
                if isinstance(r, dict)
                and str(r.get("media_type") or "").strip().lower() in {"movie", "tv", "person"}
            ]
            if not candidates:
                continue

            scored: list[tuple[float, dict[str, Any]]] = []
            for c in candidates[:12]:
                scored.append((_score_multi_candidate(c), c))
            scored.sort(key=lambda x: x[0], reverse=True)

            meta["language"] = lang
            meta["tmdb_endpoint"] = "/search/multi"
            if isinstance(raw, dict):
                meta["multi_results_raw"] = raw
            meta["candidates_top3"] = [_candidate_view(c, s) for s, c in scored[:3]]

            best_score, best = scored[0]
            media_type = str(best.get("media_type") or "").strip().lower()
            meta["type"] = media_type
            meta["selected"] = _candidate_view(best, best_score)

            # Keep the same conservative confidence threshold as the dedicated resolvers.
            if float(best_score) < 4.0:
                meta["rejected"] = "low_score"
                return None, meta

            if media_type == "movie" and best.get("id"):
                details_zh = await self.get_movie_details(int(best["id"]), language="zh-CN")
                if details_zh is None:
                    meta["error"] = "details_fetch_failed"
                    return None, meta
                overview = str(details_zh.get("overview") or "").strip()
                if not overview:
                    details_en = await self.get_movie_details(int(best["id"]), language="en-US")
                    if details_en and str(details_en.get("overview") or "").strip():
                        details_zh["overview"] = str(details_en.get("overview") or "")
                        meta["overview_fallback_language"] = "en-US"
                return {"type": "movie", "data": details_zh}, meta

            if media_type == "tv" and best.get("id"):
                details_zh = await self.get_tv_details(int(best["id"]), language="zh-CN")
                if details_zh is None:
                    meta["error"] = "details_fetch_failed"
                    return None, meta

                overview = str(details_zh.get("overview") or "").strip()
                if not overview:
                    details_en = await self.get_tv_details(int(best["id"]), language="en-US")
                    if details_en and str(details_en.get("overview") or "").strip():
                        details_zh["overview"] = str(details_en.get("overview") or "")
                        meta["overview_fallback_language"] = "en-US"
                return {"type": "tv", "data": details_zh}, meta

            if media_type == "person" and best.get("id"):
                details_zh = await self.get_person_details(int(best["id"]), language="zh-CN")
                if details_zh is None:
                    meta["error"] = "details_fetch_failed"
                    return None, meta
                bio = str(details_zh.get("biography") or "").strip()
                if not bio:
                    details_en = await self.get_person_details(int(best["id"]), language="en-US")
                    if details_en and str(details_en.get("biography") or "").strip():
                        details_zh["biography"] = str(details_en.get("biography") or "")
                        meta["biography_fallback_language"] = "en-US"
                return {"type": "person", "data": details_zh}, meta

        meta["rejected"] = "no_candidates"
        return None, meta

    async def resolve_person(self, *, name: str, query: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Search and disambiguate a person by name, then fetch full details."""
        meta: dict[str, Any] = {"type": "person", "query_name": name}
        if not self._base_url or not (self._api_token or self._api_key):
            meta["error"] = "tmdb_not_configured"
            return None, meta

        role_hint = _extract_person_role_hint(query)
        meta["role_hint"] = role_hint

        for lang in ("zh-CN", "en-US"):
            candidates = await self.search_people(name=name, language=lang)
            if not candidates:
                continue

            best, top = _pick_best_person_candidate(
                query_name=name, candidates=candidates[:10], role_hint=role_hint
            )
            meta["language"] = lang
            meta["candidates_top3"] = top

            if not best or not best.get("id"):
                continue

            best_score = float(top[0]["score"]) if top else 0.0
            meta["selected"] = {
                "id": best.get("id"),
                "name": best.get("name"),
                "original_name": best.get("original_name"),
                "known_for_department": best.get("known_for_department"),
                "score": best_score,
            }

            # Require a minimal confidence to avoid injecting wrong facts.
            if best_score < 4.0:
                meta["rejected"] = "low_score"
                return None, meta

            details_zh = await self.get_person_details(int(best["id"]), language="zh-CN")
            if details_zh is None:
                meta["error"] = "details_fetch_failed"
                return None, meta

            bio = str(details_zh.get("biography") or "").strip()
            if not bio:
                details_en = await self.get_person_details(int(best["id"]), language="en-US")
                if details_en and str(details_en.get("biography") or "").strip():
                    details_zh["biography"] = str(details_en.get("biography") or "")
                    meta["biography_fallback_language"] = "en-US"

            return details_zh, meta

        meta["rejected"] = "no_candidates"
        return None, meta

    async def get_movie_details(self, movie_id: int, *, language: str = "zh-CN") -> dict[str, Any] | None:
        """Fetch detailed movie information including credits.

        This uses the append_to_response feature to fetch movie details and credits
        in a single API call for efficiency.

        Args:
            movie_id: TMDB movie ID

        Returns:
            Movie details dictionary with the following structure:
            {
                "id": int,
                "title": str,
                "overview": str,
                "release_date": str,
                "vote_average": float,
                "genres": [...],
                "credits": {
                    "cast": [...],
                    "crew": [...]
                }
            }
            Or None if an error occurs.
        """
        if not self._base_url or not (self._api_token or self._api_key):
            return None

        try:
            session = await self._get_session()
            url = f"{self._base_url}/movie/{movie_id}"
            params = {
                "language": language,
                "append_to_response": "credits",  # Fetch credits in same call
            }
            params.update(self._auth_params())

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB details failed ({resp.status}): {error_text[:200]}")
                    return None

                return await resp.json(content_type=None)

        except Exception as e:
            logger.exception(f"TMDB get_movie_details failed for id={movie_id}: {e}")
            return None

    async def close(self) -> None:
        """Close the HTTP session and release resources.

        This should be called when the client is no longer needed.
        """
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

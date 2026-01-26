"""
TMDB API HTTP client for fetching movie data.

This module provides an async HTTP client for interacting with The Movie Database (TMDB) API,
following the same patterns as Mem0HttpMemoryStore for consistency.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from infrastructure.config.settings import (
    TMDB_API_KEY,
    TMDB_API_TOKEN,
    TMDB_BASE_URL,
    TMDB_TIMEOUT_S,
)

logger = logging.getLogger(__name__)


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
        """Search for a movie by title and fetch its full details.

        This method performs two steps:
        1. Search for the movie by title
        2. Fetch detailed information including credits using append_to_response

        Args:
            title: Movie title to search for

        Returns:
            Movie details dictionary including credits, or None if:
            - Client is not configured (missing base_url or api_key)
            - Movie not found
            - API error occurs
        """
        if not self._base_url or not (self._api_token or self._api_key):
            logger.warning("TMDB client not configured (missing base_url or auth)")
            return None

        try:
            session = await self._get_session()
            # Use direct concatenation to avoid urljoin eating the /3 path
            url = f"{self._base_url}/search/movie"
            params = {
                "query": title,
                "language": "zh-CN",  # Prefer Chinese results
                "page": 1,
            }
            params.update(self._auth_params())

            logger.debug(f"TMDB request URL: {url}")
            logger.debug(f"TMDB params: {params}")

            async with session.get(url, params=params, headers=self._headers()) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"TMDB search failed ({resp.status}): {error_text[:200]}")
                    return None

                data = await resp.json(content_type=None)

            # Extract first result
            results = data.get("results", [])
            if not results:
                logger.info(f"TMDB: No results found for '{title}'")
                return None

            first_result = results[0]
            movie_id = first_result.get("id")

            if not movie_id:
                logger.warning(f"TMDB: Result missing 'id' for '{title}'")
                return first_result

            # Fetch full details with credits
            return await self.get_movie_details(movie_id)

        except asyncio.TimeoutError:
            logger.error(f"TMDB search timeout after {self._timeout_s}s for '{title}'")
            return None
        except Exception as e:
            logger.exception(f"TMDB search failed for '{title}': {e}")
            return None

    async def get_movie_details(self, movie_id: int) -> dict[str, Any] | None:
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
                "language": "zh-CN",
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

"""
TMDB Enrichment service for orchestrating real-time knowledge enrichment.

This service coordinates the enrichment pipeline:
1. Extract movie entities from user query
2. Call TMDB API to fetch movie data
3. Build TransientGraph from the data
4. Return enriched context for fusion with GraphRAG results
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from infrastructure.config.settings import (
    ENRICHMENT_ENABLE,
    ENRICHMENT_ASYNC_WRITE_ENABLE,
    ENRICHMENT_MAX_RETRIES,
    ENRICHMENT_WRITE_QUEUE_SIZE,
)
from infrastructure.enrichment.entity_extractor import EntityExtractor
from infrastructure.enrichment.graph_builder import TransientGraphBuilder
from infrastructure.enrichment.models import EnrichmentResult, TransientGraph
from infrastructure.enrichment.tmdb_client import TMDBClient

logger = logging.getLogger(__name__)


class TMDBEnrichmentService:
    """Core service for TMDB-based query enrichment.

    This service orchestrates the enrichment flow, including entity extraction,
    TMDB API calls, graph building, and error handling.

    Attributes:
        _tmdb_client: HTTP client for TMDB API
        _graph_builder: Builder for converting TMDB data to TransientGraph
        _enable_cache: Whether to use caching (not implemented in Phase 1)
    """

    def __init__(
        self,
        *,
        tmdb_client: TMDBClient | None = None,
        graph_builder: TransientGraphBuilder | None = None,
        store: Any | None = None,
        enable_cache: bool = False,  # Cache will be implemented in Phase 2
    ) -> None:
        """Initialize the enrichment service.

        Args:
            tmdb_client: TMDB API client (default: create new instance)
            graph_builder: Graph builder (default: create new instance)
            enable_cache: Whether to enable caching (default: False)
        """
        self._tmdb_client = tmdb_client or TMDBClient()
        self._graph_builder = graph_builder or TransientGraphBuilder()
        self._store = store
        self._enable_cache = enable_cache
        self._write_queue: asyncio.Queue[dict[str, Any] | None] | None = None
        self._writer_task: asyncio.Task[None] | None = None
        self._writer_lock = asyncio.Lock()

    async def enrich_query(
        self,
        *,
        message: str,
        kb_prefix: str,
        extracted_entities: dict[str, Any] | None = None,
        query_intent: str | None = None,
        media_type_hint: str | None = None,
        filters: dict[str, Any] | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        request_id: str | None = None,
        conversation_id: Any | None = None,
        user_message_id: Any | None = None,
        incognito: bool = False,
    ) -> EnrichmentResult:
        """Enrich a query with TMDB data.

        This method:
        1. Checks if enrichment is enabled and applicable
        2. Extracts movie entities from the query
        3. Fetches movie data from TMDB API
        4. Builds a TransientGraph from the data
        5. Returns the enrichment result

        Args:
            message: User's query text
            kb_prefix: Knowledge base prefix (should be "movie" to trigger enrichment)
            extracted_entities: Optional router-extracted entities

        Returns:
            EnrichmentResult containing the TransientGraph and metadata.
        """
        start_time = time.monotonic()
        incognito = bool(incognito)

        # 1. Check if enrichment is enabled
        if not ENRICHMENT_ENABLE:
            logger.debug("enrichment disabled: ENRICHMENT_ENABLE=%s", ENRICHMENT_ENABLE)
            return EnrichmentResult(
                success=False,
                transient_graph=TransientGraph(),
                extracted_entities=[],
            )

        # 2. Only trigger for movie knowledge base
        if kb_prefix != "movie":
            logger.debug("enrichment skipped: kb_prefix=%s", kb_prefix)
            return EnrichmentResult(
                success=False,
                transient_graph=TransientGraph(),
                extracted_entities=[],
            )

        # Recommendation flows are router-directed (query_intent/media_type_hint),
        # so we avoid local keyword heuristics here.
        router_intent = (query_intent or "").strip().lower()
        router_media = (media_type_hint or "").strip().lower()

        router_low_level: list[str] = []
        if isinstance(extracted_entities, dict):
            low = extracted_entities.get("low_level")
            if isinstance(low, list):
                router_low_level = [str(x).strip() for x in low if str(x).strip()]

        if router_intent == "recommend" and router_media == "tv" and not router_low_level:
            payloads = await self._fetch_tv_recommendations_with_retry(query_text=message, filters=filters)
            if payloads:
                transient_graph = self._graph_builder.build_from_tmdb_payloads(payloads)
                transient_graph.metadata["context_hint"] = (
                    "NOTE: The user is asking for TV series recommendations. "
                    "The following TV items are candidates returned by TMDB /discover/tv "
                    "(using router-provided filters when present)."
                )
                disamb = getattr(self, "_last_disambiguation", None)
                if isinstance(disamb, list) and disamb:
                    transient_graph.metadata["tmdb_disambiguation"] = disamb
                duration_ms = (time.monotonic() - start_time) * 1000
                await self._maybe_persist(
                    user_id=user_id,
                    session_id=session_id,
                    request_id=request_id,
                    conversation_id=conversation_id,
                    user_message_id=user_message_id,
                    incognito=incognito,
                    query_text=message,
                    tmdb_endpoint="/discover/tv",
                    extracted_entities=["__discover_tv__"],
                    payloads=payloads,
                    duration_ms=duration_ms,
                )
                return EnrichmentResult(
                    success=True,
                    transient_graph=transient_graph,
                    extracted_entities=["__discover_tv__"],
                    cached=False,
                    duration_ms=duration_ms,
                )

        # Movie recommendations with explicit filters should use /discover/movie.
        if router_intent == "recommend" and router_media == "movie" and not router_low_level and isinstance(filters, dict) and filters:
            payloads = await self._fetch_movie_recommendations_with_retry(query_text=message, filters=filters)
            if payloads:
                transient_graph = self._graph_builder.build_from_tmdb_payloads(payloads)
                transient_graph.metadata["context_hint"] = (
                    "NOTE: The user is asking for movie recommendations with explicit filters "
                    "(e.g., year/region/language). The following movie items are candidates returned "
                    "by TMDB /discover/movie."
                )
                disamb = getattr(self, "_last_disambiguation", None)
                if isinstance(disamb, list) and disamb:
                    transient_graph.metadata["tmdb_disambiguation"] = disamb
                duration_ms = (time.monotonic() - start_time) * 1000
                await self._maybe_persist(
                    user_id=user_id,
                    session_id=session_id,
                    request_id=request_id,
                    conversation_id=conversation_id,
                    user_message_id=user_message_id,
                    incognito=incognito,
                    query_text=message,
                    tmdb_endpoint="/discover/movie",
                    extracted_entities=["__discover_movie__"],
                    payloads=payloads,
                    duration_ms=duration_ms,
                )
                return EnrichmentResult(
                    success=True,
                    transient_graph=transient_graph,
                    extracted_entities=["__discover_movie__"],
                    cached=False,
                    duration_ms=duration_ms,
                )

        # 3. Extract movie entities (prefer router output when available)
        entities: list[str] = []
        if isinstance(extracted_entities, dict):
            low = extracted_entities.get("low_level")
            if isinstance(low, list):
                entities = [str(x).strip() for x in low if str(x).strip()]
        if not entities:
            entities = EntityExtractor.extract_movie_entities(message)
        if not entities:
            entities = EntityExtractor.extract_person_entities(message)
        logger.debug("enrichment extracted entities=%s", entities)
        if not entities:
            return EnrichmentResult(
                success=False,
                transient_graph=TransientGraph(),
                extracted_entities=[],
            )

        # 4. Fetch TMDB payloads (movies and/or people) with retry logic
        payloads = await self._fetch_payloads_with_retry(entities, query_text=message)

        if not payloads:
            return EnrichmentResult(
                success=False,
                transient_graph=TransientGraph(),
                extracted_entities=entities,
                api_errors=["All TMDB API calls failed"],
            )

        # 5. Build TransientGraph
        transient_graph = self._graph_builder.build_from_tmdb_payloads(payloads)
        # Attach disambiguation diagnostics for debugging / UI visualization.
        disamb = getattr(self, "_last_disambiguation", None)
        if isinstance(disamb, list) and disamb:
            transient_graph.metadata["tmdb_disambiguation"] = disamb

        duration_ms = (time.monotonic() - start_time) * 1000
        await self._maybe_persist(
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            incognito=incognito,
            query_text=message,
            tmdb_endpoint="/search/multi",
            extracted_entities=entities,
            payloads=payloads,
            duration_ms=duration_ms,
        )
        logger.info(
            f"Enrichment completed: {len(entities)} entities, "
            f"{len(transient_graph.nodes)} nodes, {duration_ms:.0f}ms"
        )

        return EnrichmentResult(
            success=True,
            transient_graph=transient_graph,
            extracted_entities=entities,
            cached=False,
            duration_ms=duration_ms,
        )

    async def close(self) -> None:
        """Clean up resources.

        This should be called when the service is no longer needed to properly
        close the HTTP client session.
        """
        # Best-effort: stop persistence worker before closing underlying resources.
        try:
            await self._stop_writer()
        except Exception:
            pass
        await self._tmdb_client.close()
        store = self._store
        close = getattr(store, "close", None)
        if callable(close):
            try:
                await close()
            except Exception:
                pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup."""
        await self.close()

    async def _fetch_payloads_with_retry(
        self, entities: list[str], *, query_text: str
    ) -> list[dict[str, Any]]:
        """Fetch TMDB payloads (movies and/or people) with retry logic.

        Args:
            entities: List of entity strings (movie titles and/or people names)

        Returns:
            List of payload dicts with shape: {"type": "movie|person", "data": {...}}.
        """
        max_retries = ENRICHMENT_MAX_RETRIES or 2

        # Collect disambiguation metadata for debugging/observability.
        self._last_disambiguation: list[dict[str, Any]] = []
        self._last_discover_raw: dict[str, Any] | None = None

        async def _resolve_entity(entity: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
            payload, meta = await self._tmdb_client.resolve_entity_via_multi(text=entity, query=query_text)
            if isinstance(meta, dict):
                meta.setdefault("entity", entity)
            return payload, (meta or {"type": "unresolved", "entity": entity})

        for attempt in range(max_retries):
            if attempt > 0:
                logger.warning(f"Retrying TMDB fetch (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(1.0 * attempt)  # Exponential backoff

            # Parallel requests for all entities
            tasks = [_resolve_entity(entity) for entity in entities]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter successful results
            success_results: list[dict[str, Any]] = []
            disamb: list[dict[str, Any]] = []
            for r in results:
                if isinstance(r, Exception):
                    continue
                if not isinstance(r, tuple) or len(r) != 2:
                    continue
                payload, meta = r
                if isinstance(meta, dict):
                    disamb.append(meta)
                if isinstance(payload, dict) and payload:
                    success_results.append(payload)

            self._last_disambiguation = disamb

            if success_results:
                return success_results

        logger.error(f"TMDB fetch failed after {max_retries} retries")
        return []

    async def _fetch_tv_recommendations_with_retry(
        self,
        *,
        query_text: str,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Fetch a small list of Chinese TV recommendations from TMDB (best-effort)."""
        max_retries = ENRICHMENT_MAX_RETRIES or 2

        self._last_disambiguation = []
        self._last_discover_raw = None

        for attempt in range(max_retries):
            if attempt > 0:
                logger.warning(f"Retrying TMDB discover tv (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(1.0 * attempt)

            raw = await self._tmdb_client.discover_tv_raw(
                language="zh-CN",
                page=1,
                sort_by=str((filters or {}).get("sort_by") or "popularity.desc"),
                filters=filters,
            )
            self._last_discover_raw = raw if isinstance(raw, dict) else None
            results = []
            if isinstance(raw, dict):
                res = raw.get("results") or []
                if isinstance(res, list):
                    results = [r for r in res if isinstance(r, dict)]
            if not results:
                continue

            top = results[:5]
            self._last_disambiguation = [
                {
                    "type": "tv_recommendations",
                    "query_text": query_text,
                    "top10": [
                        {
                            "id": it.get("id"),
                            "name": it.get("name"),
                            "original_name": it.get("original_name"),
                            "first_air_date": it.get("first_air_date"),
                            "vote_average": it.get("vote_average"),
                        }
                        for it in (results[:10] if isinstance(results, list) else [])
                        if isinstance(it, dict)
                    ],
                }
            ]

            async def _fetch(it: dict[str, Any]) -> dict[str, Any] | None:
                tv_id = it.get("id")
                if not tv_id:
                    return None
                details = await self._tmdb_client.get_tv_details(int(tv_id), language="zh-CN")
                if not isinstance(details, dict) or not details:
                    return None
                overview = str(details.get("overview") or "").strip()
                if not overview:
                    details_en = await self._tmdb_client.get_tv_details(int(tv_id), language="en-US")
                    if details_en and str(details_en.get("overview") or "").strip():
                        details["overview"] = str(details_en.get("overview") or "")
                return {"type": "tv", "data": details}

            payloads: list[dict[str, Any]] = []
            fetched = await asyncio.gather(*[_fetch(it) for it in top], return_exceptions=True)
            for r in fetched:
                if isinstance(r, dict) and r:
                    payloads.append(r)
            if payloads:
                return payloads

        return []

    async def _fetch_movie_recommendations_with_retry(
        self,
        *,
        query_text: str,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Fetch a small list of movie recommendations from TMDB /discover/movie (best-effort)."""
        max_retries = ENRICHMENT_MAX_RETRIES or 2

        self._last_disambiguation = []
        self._last_discover_raw = None

        for attempt in range(max_retries):
            if attempt > 0:
                logger.warning(f"Retrying TMDB discover movie (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(1.0 * attempt)

            raw = await self._tmdb_client.discover_movie_raw(
                language="zh-CN",
                page=1,
                sort_by=str((filters or {}).get("sort_by") or "popularity.desc"),
                filters=filters,
            )
            self._last_discover_raw = raw if isinstance(raw, dict) else None
            results = []
            if isinstance(raw, dict):
                res = raw.get("results") or []
                if isinstance(res, list):
                    results = [r for r in res if isinstance(r, dict)]
            if not results:
                continue

            top = results[:5]
            self._last_disambiguation = [
                {
                    "type": "movie_recommendations",
                    "query_text": query_text,
                    "filters": filters or {},
                    "top10": [
                        {
                            "id": it.get("id"),
                            "title": it.get("title"),
                            "original_title": it.get("original_title"),
                            "release_date": it.get("release_date"),
                            "vote_average": it.get("vote_average"),
                        }
                        for it in (results[:10] if isinstance(results, list) else [])
                        if isinstance(it, dict)
                    ],
                }
            ]

            async def _fetch(it: dict[str, Any]) -> dict[str, Any] | None:
                movie_id = it.get("id")
                if not movie_id:
                    return None
                details = await self._tmdb_client.get_movie_details(int(movie_id), language="zh-CN")
                if not isinstance(details, dict) or not details:
                    return None
                overview = str(details.get("overview") or "").strip()
                if not overview:
                    details_en = await self._tmdb_client.get_movie_details(int(movie_id), language="en-US")
                    if details_en and str(details_en.get("overview") or "").strip():
                        details["overview"] = str(details_en.get("overview") or "")
                return {"type": "movie", "data": details}

            payloads: list[dict[str, Any]] = []
            fetched = await asyncio.gather(*[_fetch(it) for it in top], return_exceptions=True)
            for r in fetched:
                if isinstance(r, dict) and r:
                    payloads.append(r)
            if payloads:
                return payloads

        return []

    async def _ensure_writer(self) -> None:
        if self._store is None:
            return
        if not ENRICHMENT_ASYNC_WRITE_ENABLE:
            return
        if self._writer_task is not None and self._write_queue is not None:
            return
        async with self._writer_lock:
            if self._writer_task is not None and self._write_queue is not None:
                return
            self._write_queue = asyncio.Queue(maxsize=int(ENRICHMENT_WRITE_QUEUE_SIZE or 100))
            self._writer_task = asyncio.create_task(self._writer_loop())

    async def _stop_writer(self) -> None:
        q = self._write_queue
        t = self._writer_task
        if q is None or t is None:
            return
        try:
            q.put_nowait(None)
        except Exception:
            pass
        try:
            await asyncio.wait_for(t, timeout=2.0)
        except Exception:
            t.cancel()

        self._write_queue = None
        self._writer_task = None

    async def _writer_loop(self) -> None:
        q = self._write_queue
        if q is None:
            return
        while True:
            job = await q.get()
            try:
                if job is None:
                    return
                store = self._store
                if store is None:
                    continue
                persist = getattr(store, "persist_enrichment", None)
                if callable(persist):
                    await persist(**job)
            except Exception as e:
                logger.debug("tmdb persistence job failed: %s", e, exc_info=True)
            finally:
                q.task_done()

    async def _maybe_persist(
        self,
        *,
        user_id: str | None,
        session_id: str | None,
        request_id: str | None,
        conversation_id: Any | None,
        user_message_id: Any | None,
        incognito: bool,
        query_text: str,
        tmdb_endpoint: str,
        extracted_entities: list[str],
        payloads: list[dict[str, Any]],
        duration_ms: float,
    ) -> None:
        """Best-effort persistence for TMDB enrichment (does not affect user response)."""
        if incognito:
            return
        store = self._store
        if store is None:
            return
        if not user_id or not session_id:
            return

        disamb = getattr(self, "_last_disambiguation", None)
        discover_raw = getattr(self, "_last_discover_raw", None)

        role_hint = None
        tmdb_language = None
        candidates_top3: list[dict[str, Any]] = []
        multi_results_raw: dict[str, Any] | None = None

        if isinstance(disamb, list):
            for m in disamb:
                if not isinstance(m, dict):
                    continue
                if role_hint is None and m.get("role_hint"):
                    role_hint = str(m.get("role_hint"))
                if tmdb_language is None and m.get("language"):
                    tmdb_language = str(m.get("language"))
                entity = m.get("entity")
                top3 = m.get("candidates_top3")
                if top3 is not None:
                    candidates_top3.append({"entity": entity, "candidates_top3": top3})

            # Aggregate raw multi responses per entity when available.
            raw_by_entity: list[dict[str, Any]] = []
            for m in disamb:
                if not isinstance(m, dict):
                    continue
                raw = m.get("multi_results_raw")
                if raw is None:
                    continue
                raw_by_entity.append(
                    {
                        "entity": m.get("entity"),
                        "language": m.get("language"),
                        "response": raw,
                    }
                )
            if raw_by_entity:
                multi_results_raw = {"results_by_entity": raw_by_entity}

        job: dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "query_text": query_text,
            "tmdb_endpoint": tmdb_endpoint,
            "extracted_entities": extracted_entities,
            "disambiguation": disamb if isinstance(disamb, list) else [],
            "payloads": payloads,
            "request_id": request_id,
            "conversation_id": conversation_id,
            "user_message_id": user_message_id,
            "candidates_top3": candidates_top3 or None,
            "multi_results_raw": multi_results_raw,
            "discover_results_raw": discover_raw if (tmdb_endpoint or "").startswith("/discover/") else None,
            "role_hint": role_hint,
            "tmdb_language": tmdb_language,
            "duration_ms": float(duration_ms),
        }

        if ENRICHMENT_ASYNC_WRITE_ENABLE:
            await self._ensure_writer()
            q = self._write_queue
            if q is None:
                return
            try:
                q.put_nowait(job)
            except asyncio.QueueFull:
                logger.debug("tmdb persistence queue full; dropping job")
            return

        persist = getattr(store, "persist_enrichment", None)
        if callable(persist):
            try:
                await persist(**job)
            except Exception as e:
                logger.debug("tmdb persistence failed: %s", e, exc_info=True)

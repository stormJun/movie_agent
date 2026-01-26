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
    ENRICHMENT_MAX_RETRIES,
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
        self._enable_cache = enable_cache

    async def enrich_query(
        self,
        *,
        message: str,
        kb_prefix: str,
        extracted_entities: dict[str, Any] | None = None,
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

        # 3. Extract movie entities (prefer router output when available)
        entities: list[str] = []
        if isinstance(extracted_entities, dict):
            low = extracted_entities.get("low_level")
            if isinstance(low, list):
                entities = [str(x).strip() for x in low if str(x).strip()]
        if not entities:
            entities = EntityExtractor.extract_movie_entities(message)
        logger.debug("enrichment extracted entities=%s", entities)
        if not entities:
            return EnrichmentResult(
                success=False,
                transient_graph=TransientGraph(),
                extracted_entities=[],
            )

        # 4. Fetch movies with retry logic
        movie_data_list = await self._fetch_movies_with_retry(entities)

        if not movie_data_list:
            return EnrichmentResult(
                success=False,
                transient_graph=TransientGraph(),
                extracted_entities=entities,
                api_errors=["All TMDB API calls failed"],
            )

        # 5. Build TransientGraph
        transient_graph = self._graph_builder.build_from_tmdb_data(movie_data_list)

        duration_ms = (time.monotonic() - start_time) * 1000
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
        await self._tmdb_client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup."""
        await self.close()

    async def _fetch_movies_with_retry(self, entities: list[str]) -> list[dict[str, Any]]:
        """Fetch movie data from TMDB with retry logic.

        Args:
            entities: List of movie titles to fetch

        Returns:
            List of movie detail dictionaries from TMDB API.
        """
        max_retries = ENRICHMENT_MAX_RETRIES or 2

        for attempt in range(max_retries):
            if attempt > 0:
                logger.warning(f"Retrying TMDB fetch (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(1.0 * attempt)  # Exponential backoff

            # Parallel requests for all movies
            tasks = [self._tmdb_client.search_movie(entity) for entity in entities]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter successful results
            success_results = [r for r in results if isinstance(r, dict) and r is not None]

            if success_results:
                return success_results

        logger.error(f"TMDB fetch failed after {max_retries} retries")
        return []

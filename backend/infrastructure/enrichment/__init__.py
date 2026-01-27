"""
Query-Time Enrichment Module

This module provides real-time knowledge enrichment from external APIs (e.g., TMDB)
to enhance GraphRAG retrieval results when the knowledge base is missing entities.
"""

from infrastructure.enrichment.models import (
    EnrichmentResult,
    TransientEdge,
    TransientGraph,
    TransientNode,
)

_tmdb_service = None


def get_tmdb_enrichment_service():
    """Lazy singleton builder for TMDB enrichment.

    Returns None when enrichment is disabled or TMDB auth is not configured.
    """
    global _tmdb_service
    if _tmdb_service is not None:
        return _tmdb_service

    from infrastructure.config.settings import ENRICHMENT_ENABLE, TMDB_API_KEY, TMDB_API_TOKEN

    if not ENRICHMENT_ENABLE:
        return None

    # Prefer v4 bearer token, but allow v3 API key for local dev.
    if not (TMDB_API_TOKEN or TMDB_API_KEY):
        return None

    from infrastructure.enrichment.tmdb_client import TMDBClient
    from infrastructure.enrichment.tmdb_enrichment_service import TMDBEnrichmentService

    store = None
    try:
        from infrastructure.config.database import get_postgres_dsn

        dsn = get_postgres_dsn()
        if dsn:
            from infrastructure.persistence.postgres.tmdb_store import PostgresTmdbStore

            store = PostgresTmdbStore(dsn=dsn)
    except Exception:
        store = None

    _tmdb_service = TMDBEnrichmentService(
        tmdb_client=TMDBClient(api_token=TMDB_API_TOKEN or None, api_key=TMDB_API_KEY or None),
        store=store,
    )
    return _tmdb_service

__all__ = [
    "TransientNode",
    "TransientEdge",
    "TransientGraph",
    "EnrichmentResult",
    "get_tmdb_enrichment_service",
]

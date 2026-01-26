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

__all__ = [
    "TransientNode",
    "TransientEdge",
    "TransientGraph",
    "EnrichmentResult",
]

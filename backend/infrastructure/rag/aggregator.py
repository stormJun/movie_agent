from __future__ import annotations

from typing import Optional

from domain.chat.services.rag_aggregator import aggregate_run_results as _aggregate
from infrastructure.config.settings import (
    RAG_SYNTHESIZE_EVIDENCE_STRATEGY,
    RAG_SYNTHESIZE_MAX_CHARS,
    RAG_SYNTHESIZE_MAX_EVIDENCE,
)
from infrastructure.rag.specs import RagRunResult


def aggregate_run_results(
    *,
    results: list[RagRunResult],
    preferred_agent_order: Optional[list[str]] = None,
) -> RagRunResult:
    return _aggregate(
        results=results,
        preferred_agent_order=preferred_agent_order,
        result_cls=RagRunResult,
        synthesize_max_chars=RAG_SYNTHESIZE_MAX_CHARS,
        synthesize_max_evidence=RAG_SYNTHESIZE_MAX_EVIDENCE,
        synthesize_evidence_strategy=RAG_SYNTHESIZE_EVIDENCE_STRATEGY,
    )

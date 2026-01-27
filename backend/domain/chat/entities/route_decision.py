from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, TypedDict


KBPrefix = Literal["movie", "edu", "general"]
QueryIntent = Literal["qa", "recommend", "list", "compare", "unknown"]
MediaTypeHint = Literal["movie", "tv", "person", "mixed", "unknown"]


@dataclass(frozen=True)
class RouteDecision:
    requested_kb_prefix: str
    routed_kb_prefix: str
    kb_prefix: str
    confidence: float
    method: str
    reason: str
    worker_name: str
    # Router-level hints for downstream enrichment/UX.
    query_intent: QueryIntent = "unknown"
    media_type_hint: MediaTypeHint = "unknown"
    # Optional structured filters for recommendation-style queries.
    filters: Optional[dict[str, Any]] = None
    # Optional entity extraction from the router LLM (e.g. {"low_level": [...], "high_level": [...]}).
    extracted_entities: Optional[dict[str, Any]] = None
    # NEW: LLM-recommended agent_type (for reference/logging)
    recommended_agent_type: Optional[str] = None
    # NEW: Final resolved agent_type (used for retrieval, may differ from recommended due to planner override)
    resolved_agent_type: Optional[str] = None


class ChatRouteState(TypedDict, total=False):
    message: str
    session_id: str
    agent_type: str
    requested_kb_prefix: str
    routed_kb_prefix: Optional[str]
    kb_prefix: Optional[str]
    confidence: float
    method: str
    reason: str
    worker_name: str
    query_intent: QueryIntent
    media_type_hint: MediaTypeHint
    filters: Optional[dict[str, Any]]
    extracted_entities: Optional[dict[str, Any]]
    # NEW: LLM-recommended agent_type (has priority over agent_type)
    resolved_agent_type: Optional[str]

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, TypedDict


KBPrefix = Literal["movie", "edu", "general"]


@dataclass(frozen=True)
class RouteDecision:
    requested_kb_prefix: str
    routed_kb_prefix: str
    kb_prefix: str
    confidence: float
    method: str
    reason: str
    worker_name: str
    # Optional entity extraction from the router LLM (e.g. {"low_level": [...], "high_level": [...]}).
    extracted_entities: Optional[dict[str, Any]] = None


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
    extracted_entities: Optional[dict[str, Any]]

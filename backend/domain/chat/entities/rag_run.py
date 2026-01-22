from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class RagRunSpec:
    agent_type: str
    timeout_s: float = 30.0
    worker_name: Optional[str] = None


@dataclass(frozen=True)
class RagRunResult:
    agent_type: str
    answer: str
    context: Optional[str] = None
    reference: Optional[dict[str, Any]] = None
    retrieval_results: Optional[list[dict[str, Any]]] = None
    execution_log: Optional[list[dict[str, Any]]] = None
    error: Optional[str] = None

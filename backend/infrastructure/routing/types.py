from dataclasses import dataclass
from typing import Literal

KBPrefix = Literal["movie", "edu", "general"]


@dataclass(frozen=True)
class KBRoutingResult:
    kb_prefix: KBPrefix
    confidence: float
    method: Literal["heuristic", "llm", "fallback"]
    reason: str = ""

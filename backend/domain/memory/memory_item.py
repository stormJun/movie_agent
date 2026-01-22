from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class MemoryItem:
    """Long-term memory recall item (provider-agnostic)."""

    id: str
    text: str
    score: float = 0.0
    created_at: Optional[datetime] = None
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

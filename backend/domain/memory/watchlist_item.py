from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


@dataclass(frozen=True)
class WatchlistItem:
    """A user-scoped watchlist entry (movie to watch later)."""

    id: UUID
    user_id: str
    title: str
    year: Optional[int] = None
    # to_watch | watched | dismissed
    status: str = "to_watch"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

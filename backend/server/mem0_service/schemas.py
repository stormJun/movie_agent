from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class MemoryAddRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class MemoryAddResponse(BaseModel):
    id: str


class MemorySearchRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    limit: int = 5


class MemoryOut(BaseModel):
    id: str
    text: str
    score: float = 0.0
    tags: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class MemorySearchResponse(BaseModel):
    memories: list[MemoryOut] = Field(default_factory=list)


class MemoryListResponse(BaseModel):
    memories: list[MemoryOut] = Field(default_factory=list)
    total: int = 0


class MemoryUpdateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class ForgetRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = 50
    require_confirmation: bool = True
    confirm: bool = False

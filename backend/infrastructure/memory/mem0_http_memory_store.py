from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin

import aiohttp

from application.ports.memory_store_port import MemoryStorePort
from domain.memory import MemoryItem
from infrastructure.config.settings import (
    MEM0_ADD_PATH,
    MEM0_API_KEY,
    MEM0_BASE_URL,
    MEM0_SEARCH_PATH,
    MEM0_TIMEOUT_S,
)

logger = logging.getLogger(__name__)


def _join(base: str, path: str) -> str:
    base = (base or "").rstrip("/") + "/"
    path = (path or "").lstrip("/")
    return urljoin(base, path)


class Mem0HttpMemoryStore(MemoryStorePort):
    """mem0 HTTP client (best-effort; schema tolerant).

    This client intentionally accepts multiple response shapes so it can work
    against different mem0 deployments (open-source/self-hosted/SaaS).
    """

    def __init__(
        self,
        *,
        base_url: str = MEM0_BASE_URL,
        api_key: str = MEM0_API_KEY,
        timeout_s: float = MEM0_TIMEOUT_S,
        search_path: str = MEM0_SEARCH_PATH,
        add_path: str = MEM0_ADD_PATH,
    ) -> None:
        self._base_url = (base_url or "").strip()
        self._api_key = (api_key or "").strip()
        self._timeout_s = float(timeout_s or 10.0)
        self._search_url = _join(self._base_url, search_path)
        self._add_url = _join(self._base_url, add_path)
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()  # Protect session creation from concurrent access

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        # Fast path: return existing session if available
        if self._session is not None and not self._session.closed:
            return self._session

        # Slow path: acquire lock and create session (double-check pattern)
        async with self._lock:
            # Another coroutine may have created the session while we waited
            if self._session is not None and not self._session.closed:
                return self._session

            timeout = aiohttp.ClientTimeout(total=self._timeout_s)
            self._session = aiohttp.ClientSession(timeout=timeout)
            return self._session

    @staticmethod
    def _parse_items(payload: Any) -> list[MemoryItem]:
        # Accept common shapes:
        # - {"memories": [...]} / {"data": [...]} / {"results": [...]}
        # - [...]
        if isinstance(payload, dict):
            for key in ("memories", "data", "results", "items"):
                if key in payload and isinstance(payload[key], list):
                    payload = payload[key]
                    break

        items: list[MemoryItem] = []
        if not isinstance(payload, list):
            return items

        for raw in payload:
            if not isinstance(raw, dict):
                continue
            mid = str(raw.get("id") or raw.get("memory_id") or raw.get("_id") or "")
            text = str(raw.get("text") or raw.get("content") or raw.get("memory") or "")
            score = float(raw.get("score") or raw.get("similarity") or 0.0)
            tags_raw = raw.get("tags") or raw.get("tag") or []
            tags: tuple[str, ...] = ()
            if isinstance(tags_raw, list):
                tags = tuple(str(t) for t in tags_raw if t)
            elif isinstance(tags_raw, str) and tags_raw:
                tags = (tags_raw,)

            created_at = None
            ts = raw.get("created_at") or raw.get("createdAt") or raw.get("timestamp")
            if isinstance(ts, str) and ts:
                try:
                    created_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    created_at = None

            # Extract metadata if present
            metadata = raw.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}

            if not mid and not text:
                continue
            items.append(
                MemoryItem(
                    id=mid or text[:16],
                    text=text,
                    score=score,
                    created_at=created_at,
                    tags=tags,
                    metadata=metadata,
                )
            )
        return items

    async def search(self, *, user_id: str, query: str, top_k: int) -> list[MemoryItem]:
        if not self._base_url:
            return []
        session = await self._get_session()
        payload = {"user_id": str(user_id), "query": str(query), "limit": int(top_k)}
        async with session.post(self._search_url, json=payload, headers=self._headers()) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(f"mem0 search failed ({resp.status}): {text[:200]}")
            data = await resp.json(content_type=None)
        return self._parse_items(data)

    async def add(
        self,
        *,
        user_id: str,
        text: str,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self._base_url:
            return None
        session = await self._get_session()
        payload: dict[str, Any] = {"user_id": str(user_id), "text": str(text)}
        if tags:
            payload["tags"] = list(tags)
        if metadata:
            payload["metadata"] = dict(metadata)
        async with session.post(self._add_url, json=payload, headers=self._headers()) as resp:
            if resp.status >= 400:
                text_resp = await resp.text()
                raise RuntimeError(f"mem0 add failed ({resp.status}): {text_resp[:200]}")
            data = await resp.json(content_type=None)
        if isinstance(data, dict):
            mid = data.get("id") or data.get("memory_id") or data.get("data", {}).get("id")
            if mid:
                return str(mid)
        return None

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None


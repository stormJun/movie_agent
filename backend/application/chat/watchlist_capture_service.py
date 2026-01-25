from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from application.ports.watchlist_store_port import WatchlistStorePort
from domain.memory import WatchlistItem


_CJK_TITLE_RE = re.compile(r"《([^》]{1,60})》")
_YEAR_RE = re.compile(r"[\(（]\s*(\d{4})\s*[\)）]")


def _normalize_title(title: str) -> str:
    t = (title or "").strip().lower()
    # Remove common separators/spaces.
    t = re.sub(r"[\s\-_:/\\|]+", " ", t).strip()
    return t


def _extract_titles_from_text(text: str) -> list[tuple[str, Optional[int]]]:
    """Heuristic title extractor for movie-ish text.

    MVP-friendly:
    - Prefer 《...》 as a strong signal for movie titles in Chinese text.
    - Also scan list-like lines and attempt to parse "Title (2014)".
    """
    text = text or ""
    out: list[tuple[str, Optional[int]]] = []

    for m in _CJK_TITLE_RE.finditer(text):
        title = (m.group(1) or "").strip()
        if not title:
            continue
        # Try to infer "(2014)" immediately following the closing bracket.
        year = None
        suffix = text[m.end() : m.end() + 12]
        ym = _YEAR_RE.search(suffix)
        if ym:
            try:
                year = int(ym.group(1))
            except Exception:
                year = None
        out.append((title, year))

    # Scan list-like lines only (avoid parsing normal paragraphs).
    for raw_line in text.splitlines():
        raw = raw_line.strip()
        if not raw:
            continue
        if raw.startswith("#"):
            # Markdown headings are never titles.
            continue

        is_list_item = bool(re.match(r"^\s*(?:[-*•]\s+|\d+\.\s+)", raw_line))
        if not is_list_item:
            continue

        line = re.sub(r"^\s*(?:[-*•]\s+|\d+\.\s+)", "", raw_line).strip()
        if not line:
            continue

        # If the line still contains 《...》, it's already covered above.
        if "《" in line and "》" in line:
            continue

        # Try to parse a simple "Title (2014)" or "Title（2014）" prefix.
        year = None
        ym = _YEAR_RE.search(line)
        if ym:
            try:
                year = int(ym.group(1))
            except Exception:
                year = None

        # Keep only the leading part before separators that usually start descriptions.
        candidate = re.split(r"[：:—-]\s+", line, maxsplit=1)[0].strip()
        candidate = re.sub(r"[\(（].*$", "", candidate).strip()

        # Very conservative filters to avoid garbage.
        if len(candidate) < 2 or len(candidate) > 80:
            continue
        # Avoid partial bracketed titles like "《Star Wa" (missing closing bracket).
        if "《" in candidate or "》" in candidate:
            continue
        if any(p in candidate for p in ("，", "。", "！", "？", "；", "、")):
            continue
        if any(x in candidate for x in ("http://", "https://", "Chunks", "source_id")):
            continue
        if candidate.startswith(("推荐", "根据")):
            continue
        # Avoid treating plain sentences as titles (requires at least one letter/number/CJK).
        if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", candidate):
            continue

        out.append((candidate, year))

    # Dedup by normalized title+year preference (keep first yearful item).
    seen: dict[str, tuple[str, Optional[int]]] = {}
    for title, year in out:
        key = f"{_normalize_title(title)}|{year or ''}"
        if key in seen:
            continue
        seen[key] = (title, year)
    return list(seen.values())


def _should_capture(user_message: str) -> bool:
    m = (user_message or "").strip().lower()
    if not m:
        return False
    # Avoid capturing for Q&A about a single title (usually not "want to watch").
    if "导演" in m or "演员" in m or "剧情" in m:
        if "推荐" not in m and "片单" not in m and "清单" not in m and "想看" not in m and "加入" not in m:
            return False

    keywords = [
        # explicit add intent (highest precision)
        "加入",
        "加到",
        "放到",
        "加入watchlist",
        "watchlist",
        "想看清单",
        # recommendation intent
        "推荐",
        "片单",
        "清单",
        "有哪些电影",
        "有什么电影",
        "想看点",
        "想看一些",
        "想看",
        "待看",
    ]
    return any(k in m for k in keywords)


def _include_assistant(user_message: str) -> bool:
    """Whether to parse assistant recommendations for candidates.

    For explicit 'add this title' requests, only parse user message to reduce noise.
    """
    m = (user_message or "").strip().lower()
    explicit_add = any(k in m for k in ("加入", "加到", "放到", "加入watchlist", "watchlist"))
    # "想看清单" contains "清单" but is still an explicit add; don't treat it as recommendation.
    if explicit_add and (
        "推荐" not in m
        and "片单" not in m
        and "有哪些电影" not in m
        and "有什么电影" not in m
    ):
        return False
    return True


@dataclass(frozen=True)
class WatchlistCaptureResult:
    added: list[WatchlistItem]
    candidates: list[tuple[str, Optional[int]]]


class WatchlistCaptureService:
    """Best-effort watchlist auto-capture from conversation turns (MVP).

    Goal:
    - When users ask for recommendations / express interest, we capture the
      mentioned/recommended movie titles into the user's watchlist.
    - Keep this conservative; noisy auto-add hurts UX more than missing items.
    """

    def __init__(
        self,
        *,
        store: WatchlistStorePort,
        enabled: bool = True,
        max_items_per_turn: int = 5,
    ) -> None:
        self._store = store
        self._enabled = bool(enabled)
        self._max_items_per_turn = max(0, int(max_items_per_turn or 0))

    async def maybe_capture(
        self,
        *,
        user_id: str,
        conversation_id: UUID | None = None,
        user_message_id: UUID | None = None,
        assistant_message_id: UUID | None = None,
        user_message: str,
        assistant_message: str,
    ) -> WatchlistCaptureResult:
        if not self._enabled or self._max_items_per_turn <= 0:
            return WatchlistCaptureResult(added=[], candidates=[])
        if not _should_capture(user_message):
            return WatchlistCaptureResult(added=[], candidates=[])

        # Candidates:
        # - always consider explicit titles in user message
        candidates: list[tuple[str, Optional[int]]] = []
        candidates.extend(_extract_titles_from_text(user_message))
        if _include_assistant(user_message):
            candidates.extend(_extract_titles_from_text(assistant_message))

        # Dedup vs existing watchlist (simple best-effort: scan first page).
        try:
            existing = await self._store.list_items(user_id=str(user_id), limit=200, offset=0)
        except Exception:
            existing = []
        existing_keys = {_normalize_title(i.title) for i in (existing or []) if i.title}

        added: list[WatchlistItem] = []
        for title, year in candidates:
            if len(added) >= self._max_items_per_turn:
                break
            norm = _normalize_title(title)
            if not norm or norm in existing_keys:
                continue
            try:
                metadata = {
                    "source": "auto_capture",
                    "conversation_id": str(conversation_id) if conversation_id else None,
                    "user_message_id": str(user_message_id) if user_message_id else None,
                    "assistant_message_id": str(assistant_message_id) if assistant_message_id else None,
                }
                # Strip None values to keep payload clean.
                metadata = {k: v for k, v in metadata.items() if v is not None}
                item = await self._store.add_item(
                    user_id=str(user_id),
                    title=title,
                    year=year,
                    metadata=metadata or None,
                )
            except Exception:
                continue
            added.append(item)
            existing_keys.add(norm)

        return WatchlistCaptureResult(added=added, candidates=candidates)

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from application.ports.conversation_episode_store_port import ConversationEpisodeStorePort
from application.ports.conversation_episodic_memory_port import ConversationEpisodicMemoryPort
from application.ports.conversation_store_port import ConversationStorePort
from infrastructure.chat_history.episodic_task_manager import EpisodicTaskManager
from infrastructure.models import get_embeddings_model

logger = logging.getLogger(__name__)


def _l2_normalize(vec: Sequence[float]) -> List[float]:
    # Keep it dependency-light; stores may assume embeddings are already normalized.
    s = 0.0
    out: List[float] = []
    for v in vec:
        fv = float(v)
        out.append(fv)
        s += fv * fv
    if s <= 0.0:
        return out
    inv = s**0.5
    if inv == 0.0:
        return out
    return [v / inv for v in out]


_AUTO_RECALL_HINT_RE = re.compile(
    r"(之前|刚才|上次|前面|前边|你说过|你提到|记得|回到|继续|那个|这(个|些)|他|她|它|他们|她们|它们)"
)


def _should_recall_auto(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    # A small heuristic gate to avoid an embeddings call on every turn.
    if _AUTO_RECALL_HINT_RE.search(q):
        return True
    # Very short follow-ups often rely on earlier context.
    if len(q) <= 12:
        return True
    return False


def _format_episode_lines(episodes: List[Dict[str, Any]], *, max_chars: int = 1200) -> str:
    lines: List[str] = []
    used = 0
    for ep in episodes:
        u = str(ep.get("user_message") or "").strip()
        a = str(ep.get("assistant_message") or "").strip()
        if not u and not a:
            continue
        line = f"- {u} → {a}".strip()
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


class ConversationEpisodicMemory(ConversationEpisodicMemoryPort):
    """Phase 2: episodic semantic recall within a conversation.

    Minimal baseline:
    - Index each completed turn asynchronously (user + assistant).
    - Recall top-K similar episodes (best-effort, gated by recall_mode).
    """

    def __init__(
        self,
        *,
        store: ConversationEpisodeStorePort,
        task_manager: EpisodicTaskManager,
        conversation_store: ConversationStorePort | None = None,
        top_k: int = 3,
        scan_limit: int = 200,
        min_score: float = 0.25,
        recall_mode: str = "auto",  # auto | always | never
        max_context_chars: int = 1200,
    ) -> None:
        self._store = store
        self._tasks = task_manager
        self._conversation_store = conversation_store
        self._top_k = int(top_k)
        self._scan_limit = int(scan_limit)
        self._min_score = float(min_score)
        self._recall_mode = (recall_mode or "auto").strip().lower()
        self._max_context_chars = int(max_context_chars)

    async def recall_relevant(
        self,
        *,
        conversation_id: UUID,
        query: str,
        top_k: int | None = None,
        exclude_assistant_message_ids: Optional[Sequence[UUID]] = None,
    ) -> List[Dict[str, Any]]:
        mode = self._recall_mode
        if mode == "never":
            return []
        if mode == "auto" and not _should_recall_auto(query):
            return []

        try:
            embeddings = get_embeddings_model()
            query_vec = await asyncio.to_thread(embeddings.embed_query, str(query))
            q = _l2_normalize(query_vec)
        except Exception as e:
            logger.warning("episodic recall: embed failed: %s", e)
            return []

        try:
            k = int(top_k) if top_k is not None else self._top_k
            rows = await self._store.search_episodes(
                conversation_id=conversation_id,
                query_embedding=q,
                limit=max(k * 2, 0),
                scan_limit=self._scan_limit,
                exclude_assistant_message_ids=list(exclude_assistant_message_ids or []),
            )
        except Exception as e:
            logger.warning("episodic recall: search failed: %s", e)
            return []

        filtered = [dict(r) for r in rows if float(r.get("similarity") or 0.0) >= self._min_score]
        filtered.sort(key=lambda x: float(x.get("similarity") or 0.0), reverse=True)
        k = int(top_k) if top_k is not None else self._top_k
        picked = filtered[: max(k, 0)]

        # Hydrate messages from the conversation store when the vector store only keeps ids.
        if picked and self._conversation_store is not None:
            needs_hydration = False
            for ep in picked:
                if not str(ep.get("user_message") or "").strip() or not str(ep.get("assistant_message") or "").strip():
                    needs_hydration = True
                    break
            if needs_hydration:
                try:
                    ids: list[UUID] = []
                    for ep in picked:
                        for key in ("user_message_id", "assistant_message_id"):
                            mid = ep.get(key)
                            if isinstance(mid, UUID):
                                ids.append(mid)
                            elif isinstance(mid, str):
                                try:
                                    ids.append(UUID(mid))
                                except Exception:
                                    pass
                    # Deduplicate while keeping order (small N).
                    seen: set[UUID] = set()
                    uniq_ids = []
                    for mid in ids:
                        if mid in seen:
                            continue
                        seen.add(mid)
                        uniq_ids.append(mid)
                    rows2 = await self._conversation_store.get_messages_by_ids(
                        conversation_id=conversation_id,
                        message_ids=uniq_ids,
                    )
                    id_map: dict[UUID, dict[str, Any]] = {}
                    for r in rows2 or []:
                        if not isinstance(r, dict):
                            continue
                        rid = r.get("id")
                        if isinstance(rid, UUID):
                            id_map[rid] = r
                    for ep in picked:
                        uid = ep.get("user_message_id")
                        aid = ep.get("assistant_message_id")
                        if isinstance(uid, str):
                            try:
                                uid = UUID(uid)
                            except Exception:
                                uid = None
                        if isinstance(aid, str):
                            try:
                                aid = UUID(aid)
                            except Exception:
                                aid = None
                        if isinstance(uid, UUID) and uid in id_map and not str(ep.get("user_message") or "").strip():
                            ep["user_message"] = str(id_map[uid].get("content") or "")
                        if isinstance(aid, UUID) and aid in id_map and not str(ep.get("assistant_message") or "").strip():
                            ep["assistant_message"] = str(id_map[aid].get("content") or "")
                except Exception as e:
                    logger.warning("episodic recall: hydrate failed: %s", e)

        return picked

    def format_context(self, *, episodes: List[Dict[str, Any]]) -> str | None:
        if not episodes:
            return None
        text = _format_episode_lines(episodes, max_chars=self._max_context_chars)
        if not text.strip():
            return None
        return f"【相关历史】\n{text}".strip()

    async def schedule_index_episode(
        self,
        *,
        conversation_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        user_message: str,
        assistant_message: str,
    ) -> bool:
        """Index is best-effort and must never block the main chat flow."""
        return await self._tasks.schedule(
            key=assistant_message_id,
            coro_factory=lambda: self._index_episode(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                user_message=user_message,
                assistant_message=assistant_message,
            ),
        )

    async def _index_episode(
        self,
        *,
        conversation_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
        user_message: str,
        assistant_message: str,
    ) -> None:
        text = f"{str(user_message).strip()}\n{str(assistant_message).strip()}".strip()
        if not text:
            return

        try:
            embeddings = get_embeddings_model()
            vec = await asyncio.to_thread(embeddings.embed_query, text)
            normalized = _l2_normalize(vec)
        except Exception as e:
            logger.warning("episodic index: embed failed: %s", e)
            return

        try:
            await self._store.upsert_episode(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                user_message=user_message,
                assistant_message=assistant_message,
                embedding=normalized,
                created_at=datetime.utcnow(),
            )
        except Exception as e:
            logger.warning("episodic index: save failed: %s", e)
            return

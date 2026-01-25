from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable
from uuid import UUID

from langchain_core.prompts import ChatPromptTemplate

from application.ports.conversation_summary_store_port import ConversationSummaryStorePort
from infrastructure.chat_history.task_manager import SummaryTaskManager
from infrastructure.models import get_llm_model

logger = logging.getLogger(__name__)


def _format_messages(messages: Iterable[dict[str, Any]], *, max_chars: int = 6000) -> str:
    parts: list[str] = []
    used = 0
    for m in messages:
        role = str(m.get("role") or "user")
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        line = f"{role}: {content}"
        if used + len(line) + 1 > max_chars:
            break
        parts.append(line)
        used += len(line) + 1
    return "\n".join(parts)


class ConversationSummarizer:
    """Phase 1: Sliding window + summary (async update, sync read)."""

    def __init__(
        self,
        *,
        store: ConversationSummaryStorePort,
        task_manager: SummaryTaskManager,
        min_messages: int = 10,
        update_delta: int = 5,
        window_size: int = 6,
        max_summary_chars: int = 1200,
    ) -> None:
        self._store = store
        self._tasks = task_manager
        self._min_messages = int(min_messages)
        self._update_delta = int(update_delta)
        self._window_size = int(window_size)
        self._max_summary_chars = int(max_summary_chars)

    async def get_summary_text(self, *, conversation_id: UUID) -> str | None:
        row = await self._store.get_summary(conversation_id=conversation_id)
        if not row:
            return None
        text = str(row.get("summary") or "").strip()
        return text or None

    async def schedule_update(self, *, conversation_id: UUID) -> bool:
        """Best-effort background update."""
        return await self._tasks.schedule(
            conversation_id=conversation_id,
            coro_factory=lambda: self.try_trigger_update(conversation_id=conversation_id),
        )

    async def try_trigger_update(self, *, conversation_id: UUID) -> None:
        total_completed = await self._store.count_completed_messages(conversation_id=conversation_id)
        if total_completed < self._min_messages:
            return

        summary_row = await self._store.get_summary(conversation_id=conversation_id)
        existing_summary = str(summary_row.get("summary") or "") if summary_row else ""
        expected_version = int(summary_row.get("summary_version")) if summary_row and summary_row.get("summary_version") is not None else None
        covered_at = summary_row.get("covered_through_created_at") if summary_row else None
        covered_id = summary_row.get("covered_through_message_id") if summary_row else None

        # Identify the "window start" cursor: the oldest message in the recent window.
        recent = await self._store.list_recent_messages(conversation_id=conversation_id, limit=self._window_size)
        if not recent:
            return
        # recent is newest-first; window_start is the oldest in window.
        window_start = recent[-1]
        window_start_at: datetime = window_start["created_at"]
        window_start_id: UUID = window_start["id"]

        # Fetch eligible messages: messages after covered cursor and strictly before window_start.
        eligible: list[dict[str, Any]] = []
        page_limit = 200
        cursor_at = covered_at if isinstance(covered_at, datetime) else None
        cursor_id = covered_id if isinstance(covered_id, UUID) else None

        while True:
            page = await self._store.list_messages_since(
                conversation_id=conversation_id,
                since_created_at=cursor_at,
                since_message_id=cursor_id,
                limit=page_limit,
            )
            if not page:
                break

            stop = False
            for m in page:
                m_at: datetime = m["created_at"]
                m_id: UUID = m["id"]
                if (m_at, m_id) >= (window_start_at, window_start_id):
                    stop = True
                    break
                eligible.append(m)
                cursor_at, cursor_id = m_at, m_id

                # Hard cap: avoid prompt bloat in one update.
                if len(eligible) >= 200:
                    stop = True
                    break

            if stop:
                break

        if not eligible:
            return

        # If we already have a summary, only update when enough new messages moved out of the window.
        if existing_summary.strip() and len(eligible) < self._update_delta:
            return

        llm = get_llm_model()
        if existing_summary.strip():
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        (
                            "你是一个对话摘要器。请在不改变原含义的前提下，"
                            "把【旧摘要】与【新增对话】合并为一个更新后的摘要。"
                            "摘要要求：只保留对话背景、用户偏好/约束、关键事实与决定；"
                            "忽略寒暄与重复；用中文，简洁、结构化（可用短句/要点）。"
                        ),
                    ),
                    ("human", "【旧摘要】\n{old_summary}\n\n【新增对话】\n{new_messages}\n\n输出更新后的摘要："),
                ]
            )
            rendered_messages = prompt.format_messages(
                old_summary=existing_summary.strip(),
                new_messages=_format_messages(eligible),
            )
        else:
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        (
                            "你是一个对话摘要器。请把以下对话历史浓缩为简洁的摘要。"
                            "摘要要求：保留对话背景、用户偏好/约束、关键事实与决定；"
                            "忽略寒暄与重复；用中文，简洁、结构化（可用短句/要点）。"
                        ),
                    ),
                    ("human", "{conversation}\n\n输出摘要："),
                ]
            )
            rendered_messages = prompt.format_messages(conversation=_format_messages(eligible))

        # llm.invoke is sync for some providers; use ainvoke when available.
        try:
            if hasattr(llm, "ainvoke"):
                resp = await llm.ainvoke(rendered_messages)  # type: ignore[call-arg]
            else:
                resp = llm.invoke(rendered_messages)  # type: ignore[call-arg]
        except Exception as e:
            logger.warning("summary generation failed: %s", e)
            return

        summary_text = str(getattr(resp, "content", resp) or "").strip()
        if not summary_text:
            return
        if len(summary_text) > self._max_summary_chars:
            summary_text = summary_text[: self._max_summary_chars].rstrip()

        # Cursor of last eligible message.
        last = eligible[-1]
        last_at: datetime = last["created_at"]
        last_id: UUID = last["id"]
        prev_count = int(summary_row.get("covered_message_count") or 0) if summary_row else 0

        await self._store.save_summary_upsert(
            conversation_id=conversation_id,
            summary=summary_text,
            covered_through_created_at=last_at,
            covered_through_message_id=last_id,
            covered_message_count=prev_count + len(eligible),
            expected_version=expected_version,
        )

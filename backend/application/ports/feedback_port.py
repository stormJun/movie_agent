from __future__ import annotations

from typing import Dict, Protocol


class FeedbackPort(Protocol):
    async def process_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str,
        request_id: str | None = None,
    ) -> Dict[str, str]:
        ...

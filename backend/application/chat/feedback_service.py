from __future__ import annotations

from typing import Dict

from application.ports.feedback_port import FeedbackPort


class FeedbackService:
    def __init__(self, *, port: FeedbackPort) -> None:
        self._port = port

    async def process_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str = "graph_agent",
    ) -> Dict[str, str]:
        return await self._port.process_feedback(
            message_id=message_id,
            query=query,
            is_positive=is_positive,
            thread_id=thread_id,
            agent_type=agent_type,
        )


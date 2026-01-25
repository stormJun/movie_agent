from __future__ import annotations

import asyncio

from application.ports.chat_completion_port import ChatCompletionPort
from infrastructure.llm.completion import generate_general_answer


class LLMChatCompletionAdapter(ChatCompletionPort):
    async def generate(
        self,
        *,
        message: str,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict] | None = None,
    ) -> str:
        return await asyncio.to_thread(
            generate_general_answer,
            question=message,
            memory_context=memory_context,
            summary=summary,
            episodic_context=episodic_context,
            history=history,
        )

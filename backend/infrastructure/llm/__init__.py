"""LLM completion helpers and adapters."""

from .completion import (
    generate_general_answer,
    generate_general_answer_stream,
    generate_rag_answer,
    generate_rag_answer_stream,
)
from .chat_completion_adapter import LLMChatCompletionAdapter

__all__ = [
    "generate_general_answer",
    "generate_general_answer_stream",
    "generate_rag_answer",
    "generate_rag_answer_stream",
    "LLMChatCompletionAdapter",
]

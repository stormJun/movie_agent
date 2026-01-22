from __future__ import annotations

from typing import Any, Protocol


class ModelProvider(Protocol):
    def get_llm_model(self) -> Any:
        ...

    def get_stream_llm_model(self) -> Any:
        ...

    def get_embeddings_model(self) -> Any:
        ...

    def count_tokens(self, text: str) -> int:
        ...


_model_provider: ModelProvider | None = None


def set_model_provider(provider: ModelProvider) -> None:
    global _model_provider
    _model_provider = provider


def _resolve_model_provider() -> ModelProvider:
    if _model_provider is None:
        raise RuntimeError(
            "Model provider not configured. "
            "Call graphrag_agent.ports.set_model_provider(...) before using models."
        )
    return _model_provider


def get_llm_model() -> Any:
    return _resolve_model_provider().get_llm_model()


def get_stream_llm_model() -> Any:
    return _resolve_model_provider().get_stream_llm_model()


def get_embeddings_model() -> Any:
    return _resolve_model_provider().get_embeddings_model()


def count_tokens(text: str) -> int:
    return _resolve_model_provider().count_tokens(text)


__all__ = [
    "ModelProvider",
    "set_model_provider",
    "get_llm_model",
    "get_stream_llm_model",
    "get_embeddings_model",
    "count_tokens",
]

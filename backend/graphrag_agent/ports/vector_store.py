from __future__ import annotations

from typing import Any, Protocol


class VectorStoreProvider(Protocol):
    def from_existing_index(
        self,
        embeddings: Any,
        index_name: str,
        retrieval_query: str | None = None,
    ) -> Any:
        ...


_vector_store_provider: VectorStoreProvider | None = None


def set_vector_store_provider(provider: VectorStoreProvider) -> None:
    global _vector_store_provider
    _vector_store_provider = provider


def _resolve_vector_store_provider() -> VectorStoreProvider:
    if _vector_store_provider is None:
        raise RuntimeError(
            "Vector store provider not configured. "
            "Call graphrag_agent.ports.set_vector_store_provider(...) before using vector stores."
        )
    return _vector_store_provider


def from_existing_index(
    embeddings: Any,
    index_name: str,
    retrieval_query: str | None = None,
) -> Any:
    return _resolve_vector_store_provider().from_existing_index(
        embeddings,
        index_name=index_name,
        retrieval_query=retrieval_query,
    )


__all__ = [
    "VectorStoreProvider",
    "set_vector_store_provider",
    "from_existing_index",
]

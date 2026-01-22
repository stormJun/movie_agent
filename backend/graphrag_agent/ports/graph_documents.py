from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from graphrag_agent.graph.extraction.graph_types import GraphDocumentData


class GraphDocumentProvider(Protocol):
    def add_graph_documents(
        self,
        documents: list[GraphDocumentData],
        *,
        base_entity_label: bool = True,
        include_source: bool = True,
    ) -> None:
        ...


_graph_document_provider: GraphDocumentProvider | None = None


def set_graph_document_provider(provider: GraphDocumentProvider) -> None:
    global _graph_document_provider
    _graph_document_provider = provider


def _resolve_graph_document_provider() -> GraphDocumentProvider:
    if _graph_document_provider is None:
        raise RuntimeError(
            "Graph document provider not configured. "
            "Call graphrag_agent.ports.set_graph_document_provider(...) before writing graph documents."
        )
    return _graph_document_provider


def add_graph_documents(
    documents: list[GraphDocumentData],
    *,
    base_entity_label: bool = True,
    include_source: bool = True,
) -> None:
    _resolve_graph_document_provider().add_graph_documents(
        documents,
        base_entity_label=base_entity_label,
        include_source=include_source,
    )


__all__ = [
    "GraphDocumentProvider",
    "set_graph_document_provider",
    "add_graph_documents",
]

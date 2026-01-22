from __future__ import annotations

"""Graph document provider for graphrag_agent ports.

Canonical provider location. Injected via `backend/infrastructure/bootstrap.py`.
"""

from typing import Dict

from langchain_core.documents import Document
from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship

from graphrag_agent.graph.extraction.graph_types import (
    GraphDocumentData,
    GraphNodeData,
    GraphRelationshipData,
)
from infrastructure.providers.neo4jdb import get_db_manager


def _build_node_map(nodes: list[GraphNodeData]) -> Dict[str, Node]:
    node_map: Dict[str, Node] = {}
    for node in nodes:
        node_map[node.node_id] = Node(
            id=node.node_id,
            type=node.node_type,
            properties=node.properties,
        )
    return node_map


def _build_relationship(
    rel: GraphRelationshipData, node_map: Dict[str, Node]
) -> Relationship:
    if rel.source_id not in node_map:
        node_map[rel.source_id] = Node(
            id=rel.source_id,
            type="unknown",
            properties={"description": "No additional data"},
        )
    if rel.target_id not in node_map:
        node_map[rel.target_id] = Node(
            id=rel.target_id,
            type="unknown",
            properties={"description": "No additional data"},
        )
    return Relationship(
        source=node_map[rel.source_id],
        target=node_map[rel.target_id],
        type=rel.rel_type,
        properties=rel.properties,
    )


def _to_graph_document(doc: GraphDocumentData) -> GraphDocument:
    node_map = _build_node_map(doc.nodes)
    relationships = [_build_relationship(rel, node_map) for rel in doc.relationships]
    source = Document(page_content=doc.source.content, metadata=doc.source.metadata)
    return GraphDocument(
        nodes=list(node_map.values()),
        relationships=relationships,
        source=source,
    )


def add_graph_documents(
    documents: list[GraphDocumentData],
    *,
    base_entity_label: bool = True,
    include_source: bool = True,
) -> None:
    if not documents:
        return
    graph = get_db_manager().get_graph()
    graph_documents = [_to_graph_document(doc) for doc in documents]
    graph.add_graph_documents(
        graph_documents,
        baseEntityLabel=base_entity_label,
        include_source=include_source,
    )


__all__ = ["add_graph_documents"]

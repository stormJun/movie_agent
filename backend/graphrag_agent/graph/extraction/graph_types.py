from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GraphNodeData:
    node_id: str
    node_type: str
    properties: dict[str, Any]


@dataclass
class GraphRelationshipData:
    source_id: str
    target_id: str
    rel_type: str
    properties: dict[str, Any]


@dataclass
class GraphSourceData:
    content: str
    metadata: dict[str, Any]


@dataclass
class GraphDocumentData:
    nodes: list[GraphNodeData]
    relationships: list[GraphRelationshipData]
    source: GraphSourceData


__all__ = [
    "GraphNodeData",
    "GraphRelationshipData",
    "GraphSourceData",
    "GraphDocumentData",
]

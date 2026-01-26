"""
Data models for Query-Time Enrichment.

This module defines the in-memory graph structures used for real-time knowledge
enrichment from external APIs like TMDB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TransientNode:
    """A transient graph node (in-memory, not persisted).

    Attributes:
        id: Unique node identifier (e.g., "tmdb:movie:123")
        labels: Set of node labels (e.g., {"Movie", "Entity"})
        properties: Dictionary of node properties
    """

    id: str
    labels: set[str] = field(default_factory=set)
    properties: dict[str, Any] = field(default_factory=dict)

    def to_context_text(self) -> str:
        """Convert node to text format for LLM context.

        Returns:
            A human-readable text representation of the node.
        """
        label = list(self.labels)[0] if self.labels else "Entity"
        name = self.properties.get("name", self.id)
        desc = self.properties.get("description", "")

        parts = [f"{label}: {name}"]
        if desc:
            parts.append(f" - {desc}")

        return "".join(parts)


@dataclass(frozen=True)
class TransientEdge:
    """A transient graph edge (in-memory, not persisted).

    Attributes:
        source: Source node ID
        target: Target node ID
        relationship_type: Type of relationship (e.g., "DIRECTED", "ACTED_IN")
        properties: Dictionary of edge properties
    """

    source: str
    target: str
    relationship_type: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_context_text(self) -> str:
        """Convert edge to text format for LLM context.

        Returns:
            A human-readable text representation of the edge.
        """
        return f"{self.source} -[{self.relationship_type}]-> {self.target}"


@dataclass
class TransientGraph:
    """A transient in-memory graph for real-time enrichment.

    This graph is constructed from external API data and fused with
    GraphRAG retrieval results to provide enhanced context to the LLM.

    Attributes:
        nodes: List of graph nodes
        edges: List of graph edges
        metadata: Additional metadata about the graph
        source: Data source identifier (e.g., "tmdb")
        created_at: Timestamp when the graph was created
    """

    nodes: list[TransientNode] = field(default_factory=list)
    edges: list[TransientEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "tmdb"
    created_at: datetime = field(default_factory=datetime.now)

    def to_context_text(self) -> str:
        """Convert the entire graph to text format for LLM context.

        This method generates a structured text representation that can be
        injected into the LLM's context to provide enriched information.

        Returns:
            A formatted text representation of the graph with entities and relationships.
        """
        lines = [f"# Enriched from {self.source}"]

        # Add entities section
        if self.nodes:
            lines.append("\n## Entities:")
            for node in self.nodes:
                lines.append(f"- {node.to_context_text()}")

        # Add relationships section
        if self.edges:
            lines.append("\n## Relationships:")
            for edge in self.edges:
                # Use readable node names instead of IDs
                source_name = self._get_node_name(edge.source)
                target_name = self._get_node_name(edge.target)
                lines.append(f"- {source_name} -[{edge.relationship_type}]-> {target_name}")

        return "\n".join(lines)

    def is_empty(self) -> bool:
        """Check if the graph is empty.

        Returns:
            True if the graph has no nodes or edges, False otherwise.
        """
        return len(self.nodes) == 0 and len(self.edges) == 0

    def _get_node_name(self, node_id: str) -> str:
        """Get a human-readable name for a node.

        Args:
            node_id: The node ID to look up

        Returns:
            The node's name property, or the ID if not found.
        """
        for node in self.nodes:
            if node.id == node_id:
                return node.properties.get("name", node.id)
        return node_id


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation.

    Attributes:
        success: Whether the enrichment operation succeeded
        transient_graph: The enriched transient graph
        extracted_entities: List of entities that were extracted from the query
        api_errors: List of error messages from API calls
        cached: Whether the result came from cache
        duration_ms: Time taken for the enrichment operation in milliseconds
    """

    success: bool
    transient_graph: TransientGraph
    extracted_entities: list[str] = field(default_factory=list)
    api_errors: list[str] = field(default_factory=list)
    cached: bool = False
    duration_ms: float = 0.0

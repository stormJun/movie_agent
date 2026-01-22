from __future__ import annotations

from typing import Iterable

from graphrag_agent.ports.neo4jdb import GraphClient, get_graph


def resolve_graph(graph: GraphClient | None = None) -> GraphClient:
    return graph or get_graph()


def create_index(graph: GraphClient, index_query: str) -> None:
    graph.query(index_query)


def create_multiple_indexes(graph: GraphClient, index_queries: Iterable[str]) -> None:
    for query in index_queries:
        create_index(graph, query)


def drop_index(graph: GraphClient, index_name: str) -> None:
    try:
        graph.query(f"DROP INDEX {index_name} IF EXISTS")
        print(f"已删除索引 {index_name}（如果存在）")
    except Exception as exc:
        print(f"删除索引 {index_name} 时出错 (可忽略): {exc}")


__all__ = [
    "resolve_graph",
    "create_index",
    "create_multiple_indexes",
    "drop_index",
]

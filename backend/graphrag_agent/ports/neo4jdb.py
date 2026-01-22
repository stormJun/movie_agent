from __future__ import annotations

from typing import Any, Protocol


class GraphClient(Protocol):
    def query(self, query: str, params: dict | None = None) -> Any:
        ...

    def refresh_schema(self) -> None:
        ...


class Neo4jProvider(Protocol):
    def get_db_manager(self) -> Any:
        ...

    def get_config(self) -> dict[str, Any]:
        ...

    def __getattr__(self, name: str) -> Any:
        ...


class GraphQueryPort(Protocol):
    def execute_query(self, cypher: str, params: dict | None = None) -> Any:
        ...

    def query(self, cypher: str, params: dict | None = None) -> Any:
        ...


_neo4j_provider: Neo4jProvider | None = None


def set_neo4j_provider(provider: Neo4jProvider) -> None:
    global _neo4j_provider
    _neo4j_provider = provider


def _resolve_neo4j_provider() -> Neo4jProvider:
    if _neo4j_provider is None:
        raise RuntimeError(
            "Neo4j provider not configured. "
            "Call graphrag_agent.ports.set_neo4j_provider(...) before using Neo4j."
        )
    return _neo4j_provider


def get_db_manager() -> Any:
    return _resolve_neo4j_provider().get_db_manager()


def get_neo4j_config() -> dict[str, Any]:
    return _resolve_neo4j_provider().get_config()


def get_graph() -> GraphClient:
    return get_db_manager().get_graph()


def get_graph_query() -> GraphQueryPort:
    return _GraphQueryAdapter(_resolve_neo4j_provider())


class _GraphQueryAdapter:
    def __init__(self, provider: Neo4jProvider) -> None:
        self._provider = provider

    def execute_query(self, cypher: str, params: dict | None = None) -> Any:
        return self._provider.get_db_manager().execute_query(cypher, params or {})

    def query(self, cypher: str, params: dict | None = None) -> Any:
        return self._provider.get_db_manager().query(cypher, params or {})


def __getattr__(name: str) -> Any:
    if _neo4j_provider is None:
        raise AttributeError(
            "Neo4j provider not configured. "
            "Call graphrag_agent.ports.set_neo4j_provider(...) before using Neo4j."
        )
    provider = _neo4j_provider
    try:
        return getattr(provider, name)
    except AttributeError as exc:
        raise AttributeError(f"Neo4j provider has no attribute {name!r}") from exc


__all__ = [
    "GraphClient",
    "GraphQueryPort",
    "Neo4jProvider",
    "set_neo4j_provider",
    "get_db_manager",
    "get_neo4j_config",
    "get_graph",
    "get_graph_query",
]

from __future__ import annotations

"""Vector store provider for graphrag_agent ports.

Canonical provider location. Injected via `backend/infrastructure/bootstrap.py`.
"""

from typing import Any

from langchain_community.vectorstores import Neo4jVector

from infrastructure.config.settings import NEO4J_CONFIG


def from_existing_index(
    embeddings: Any,
    index_name: str,
    retrieval_query: str | None = None,
) -> Any:
    kwargs: dict[str, Any] = {}
    if retrieval_query:
        kwargs["retrieval_query"] = retrieval_query
    return Neo4jVector.from_existing_index(
        embeddings,
        index_name=index_name,
        url=NEO4J_CONFIG["uri"],
        username=NEO4J_CONFIG["username"],
        password=NEO4J_CONFIG["password"],
        **kwargs,
    )


__all__ = ["from_existing_index"]


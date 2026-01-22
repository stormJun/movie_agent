from __future__ import annotations

"""Neo4j provider for graphrag_agent ports.

Canonical provider location. Injected via `backend/infrastructure/bootstrap.py`.
"""

from infrastructure.config.neo4jdb import (  # noqa: F401
    DBConnectionManager,
    get_db_manager,
    has_db_manager,
)
from infrastructure.config.settings import NEO4J_CONFIG

Neo4jConnection = DBConnectionManager
Neo4jDBManager = DBConnectionManager


def get_config() -> dict[str, str]:
    return dict(NEO4J_CONFIG)


__all__ = [
    "DBConnectionManager",
    "Neo4jConnection",
    "Neo4jDBManager",
    "get_db_manager",
    "has_db_manager",
    "get_config",
]


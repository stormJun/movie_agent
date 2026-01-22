from __future__ import annotations

"""Compatibility shim for Neo4j provider.

Canonical provider module: `infrastructure.providers.neo4jdb`.
"""

import warnings

DEPRECATED_REMOVE_MILESTONE = "Phase2.6"

from infrastructure.providers.neo4jdb import *  # noqa: F403

warnings.warn(
    "Importing from `infrastructure.neo4jdb` is deprecated; "
    "use `infrastructure.providers.neo4jdb` instead.",
    DeprecationWarning,
    stacklevel=2,
)

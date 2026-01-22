from __future__ import annotations

"""Compatibility shim for vector store provider.

Canonical provider module: `infrastructure.providers.vector_store`.
"""

import warnings

DEPRECATED_REMOVE_MILESTONE = "Phase2.6"

from infrastructure.providers.vector_store import *  # noqa: F403

warnings.warn(
    "Importing from `infrastructure.vector_store` is deprecated; "
    "use `infrastructure.providers.vector_store` instead.",
    DeprecationWarning,
    stacklevel=2,
)

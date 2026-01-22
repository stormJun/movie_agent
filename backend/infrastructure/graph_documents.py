from __future__ import annotations

"""Compatibility shim for graph document provider.

Canonical provider module: `infrastructure.providers.graph_documents`.
"""

import warnings

DEPRECATED_REMOVE_MILESTONE = "Phase2.6"

from infrastructure.providers.graph_documents import *  # noqa: F403

warnings.warn(
    "Importing from `infrastructure.graph_documents` is deprecated; "
    "use `infrastructure.providers.graph_documents` instead.",
    DeprecationWarning,
    stacklevel=2,
)

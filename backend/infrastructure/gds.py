from __future__ import annotations

"""Compatibility shim for GDS provider.

Canonical provider module: `infrastructure.providers.gds`.
"""

import warnings

DEPRECATED_REMOVE_MILESTONE = "Phase2.6"

from infrastructure.providers.gds import *  # noqa: F403

warnings.warn(
    "Importing from `infrastructure.gds` is deprecated; "
    "use `infrastructure.providers.gds` instead.",
    DeprecationWarning,
    stacklevel=2,
)

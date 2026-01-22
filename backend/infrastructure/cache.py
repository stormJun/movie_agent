from __future__ import annotations

"""Backward-compatible cache provider import path.

Canonical provider lives at `infrastructure.providers.cache`.
"""

import warnings

DEPRECATED_REMOVE_MILESTONE = "Phase2.6"

from infrastructure.providers.cache import *  # noqa: F403

warnings.warn(
    "Importing from `infrastructure.cache` is deprecated; "
    "use `infrastructure.providers.cache` instead.",
    DeprecationWarning,
    stacklevel=2,
)

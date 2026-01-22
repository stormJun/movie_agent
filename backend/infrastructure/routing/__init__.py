"""Routing infrastructure components."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .types import KBPrefix, KBRoutingResult

if TYPE_CHECKING:
    from .router import RouterGraphAdapter


def __getattr__(name: str):
    if name == "RouterGraphAdapter":
        from .router import RouterGraphAdapter

        return RouterGraphAdapter
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["RouterGraphAdapter", "KBPrefix", "KBRoutingResult"]

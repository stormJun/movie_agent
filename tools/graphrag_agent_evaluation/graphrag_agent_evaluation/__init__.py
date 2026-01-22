from __future__ import annotations

# Tools-layer evaluation package (not shipped with core-only distribution).

DEBUG_MODE = True


def debug_print(*args, **kwargs):
    """Print debug logs when DEBUG_MODE is enabled."""

    if DEBUG_MODE:
        print(*args, **kwargs)


def set_debug_mode(enabled: bool = True) -> None:
    """Toggle global debug mode for evaluation helpers."""

    global DEBUG_MODE
    DEBUG_MODE = enabled


__all__ = [
    "DEBUG_MODE",
    "debug_print",
    "set_debug_mode",
]


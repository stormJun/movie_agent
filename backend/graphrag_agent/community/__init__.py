"""
Community subpackage.

Phase2.5: keep this module importable in a core-only install (minimal deps).
Concrete detectors/summarizers may require optional dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Tuple


_LAZY_IMPORTS: Dict[str, Tuple[str, str]] = {
    "CommunityDetectorFactory": ("graphrag_agent.community.detector", "CommunityDetectorFactory"),
    "CommunitySummarizerFactory": ("graphrag_agent.community.summary", "CommunitySummarizerFactory"),
}

_INSTALL_HINT = (
    "Optional dependencies required. "
    "Install one of: `pip install 'graphrag-agent[search,langchain]'` or "
    "`pip install 'graphrag-agent[full]'`."
)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr_name = _LAZY_IMPORTS[name]
    try:
        module = import_module(module_path)
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("graphrag_agent"):
            raise
        raise ImportError(f"{_INSTALL_HINT} Missing: {exc.name}") from exc
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> Any:
    return sorted(set(list(globals().keys()) + list(_LAZY_IMPORTS.keys())))


__all__ = list(_LAZY_IMPORTS.keys())

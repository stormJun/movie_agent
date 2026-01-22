"""
Search tools package.

Phase2.5: keep this package importable in a core-only install (minimal deps).
Concrete tools require optional dependencies (langchain/langgraph/numpy/pandas/...).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Tuple


_LAZY_IMPORTS: Dict[str, Tuple[str, str]] = {
    "BaseSearchTool": ("graphrag_agent.search.tool.base", "BaseSearchTool"),
    "LocalSearchTool": ("graphrag_agent.search.tool.local_search_tool", "LocalSearchTool"),
    "GlobalSearchTool": ("graphrag_agent.search.tool.global_search_tool", "GlobalSearchTool"),
    "HybridSearchTool": ("graphrag_agent.search.tool.hybrid_tool", "HybridSearchTool"),
    "NaiveSearchTool": ("graphrag_agent.search.tool.naive_search_tool", "NaiveSearchTool"),
    "DeepResearchTool": ("graphrag_agent.search.tool.deep_research_tool", "DeepResearchTool"),
    "DeeperResearchTool": ("graphrag_agent.search.tool.deeper_research_tool", "DeeperResearchTool"),
    "ChainOfExplorationTool": ("graphrag_agent.search.tool.chain_exploration_tool", "ChainOfExplorationTool"),
    "HypothesisGeneratorTool": ("graphrag_agent.search.tool.hypothesis_tool", "HypothesisGeneratorTool"),
    "AnswerValidationTool": ("graphrag_agent.search.tool.validation_tool", "AnswerValidationTool"),
}

_INSTALL_HINT = (
    "Optional dependencies required. "
    "Install one of: `pip install 'graphrag-agent[search,langchain,neo4j]'` or "
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


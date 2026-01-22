"""
Search tool registry.

Phase2.5: keep this module importable in a core-only install (minimal deps).
We avoid importing concrete tool modules at import time, because they depend on
optional stacks (langchain/langgraph/numpy/pandas/neo4j/...).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Dict, Type, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from graphrag_agent.search.tool.base import BaseSearchTool


_INSTALL_HINT = (
    "Optional dependencies required. "
    "Install one of: `pip install 'graphrag-agent[search,langchain,neo4j]'` or "
    "`pip install 'graphrag-agent[full]'`."
)


class LazyToolFactory:
    """
    Callable factory that lazily imports a tool class and returns an instance.

    This keeps registry imports light, while preserving the historical usage:
    - TOOL_REGISTRY[name]() -> tool instance
    - tool_cls = get_tool_class(name) -> tool class
    """

    def __init__(self, module_path: str, class_name: str) -> None:
        self._module_path = module_path
        self._class_name = class_name
        self._resolved_cls: Type[Any] | None = None

    def resolve_class(self) -> Type[Any]:
        if self._resolved_cls is not None:
            return self._resolved_cls
        try:
            module = import_module(self._module_path)
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.startswith("graphrag_agent"):
                raise
            raise ImportError(f"{_INSTALL_HINT} Missing: {exc.name}") from exc
        cls = getattr(module, self._class_name)
        self._resolved_cls = cls
        return cls

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        cls = self.resolve_class()
        try:
            return cls(*args, **kwargs)
        except ModuleNotFoundError as exc:
            # Some optional deps may be imported lazily inside __init__/methods.
            if exc.name and exc.name.startswith("graphrag_agent"):
                raise
            raise ImportError(f"{_INSTALL_HINT} Missing: {exc.name}") from exc

    def __repr__(self) -> str:  # pragma: no cover
        return f"LazyToolFactory({self._module_path}:{self._class_name})"


# Keep the public names stable. Values are callable factories (compatible with "class()").
TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "local_search": LazyToolFactory(
        "graphrag_agent.search.tool.local_search_tool", "LocalSearchTool"
    ),
    "global_search": LazyToolFactory(
        "graphrag_agent.search.tool.global_search_tool", "GlobalSearchTool"
    ),
    "hybrid_search": LazyToolFactory(
        "graphrag_agent.search.tool.hybrid_tool", "HybridSearchTool"
    ),
    "naive_search": LazyToolFactory(
        "graphrag_agent.search.tool.naive_search_tool", "NaiveSearchTool"
    ),
    "deep_research": LazyToolFactory(
        "graphrag_agent.search.tool.deep_research_tool", "DeepResearchTool"
    ),
    "deeper_research": LazyToolFactory(
        "graphrag_agent.search.tool.deeper_research_tool", "DeeperResearchTool"
    ),
}


EXTRA_TOOL_FACTORIES: Dict[str, Callable[..., Any]] = {
    "chain_exploration": LazyToolFactory(
        "graphrag_agent.search.tool.chain_exploration_tool", "ChainOfExplorationTool"
    ),
    "hypothesis_generator": LazyToolFactory(
        "graphrag_agent.search.tool.hypothesis_tool", "HypothesisGeneratorTool"
    ),
    "answer_validator": LazyToolFactory(
        "graphrag_agent.search.tool.validation_tool", "AnswerValidationTool"
    ),
}


def get_tool_class(tool_name: str) -> Type["BaseSearchTool"]:
    """Resolve and return the tool class for the given name."""
    factory = TOOL_REGISTRY[tool_name]
    if isinstance(factory, LazyToolFactory):
        return factory.resolve_class()
    # Best effort: tool registry values are expected to be classes/factories.
    if isinstance(factory, type):
        return factory
    raise TypeError(f"Tool registry entry {tool_name!r} is not a class: {factory!r}")


def available_tools() -> Dict[str, Callable[..., Any]]:
    """Return a shallow copy of the registry."""
    return dict(TOOL_REGISTRY)


def available_extra_tools() -> Dict[str, Callable[..., Any]]:
    """Return a shallow copy of extra tool factories."""
    return dict(EXTRA_TOOL_FACTORIES)


def create_extra_tool(tool_name: str, *args: Any, **kwargs: Any) -> Any:
    """Create an extra tool instance by name."""
    factory = EXTRA_TOOL_FACTORIES[tool_name]
    return factory(*args, **kwargs)


__all__ = [
    "LazyToolFactory",
    "TOOL_REGISTRY",
    "EXTRA_TOOL_FACTORIES",
    "get_tool_class",
    "available_tools",
    "available_extra_tools",
    "create_extra_tool",
]

"""
Graph subpackage.

Phase2.5: keep this module importable in a core-only install (minimal deps).
Concrete implementations may require optional dependencies (neo4j, langchain,
graphdatascience, numpy/pandas, ...).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Tuple


_LAZY_IMPORTS: Dict[str, Tuple[str, str]] = {
    # Core utils
    "BaseIndexer": ("graphrag_agent.graph.core", "BaseIndexer"),
    "timer": ("graphrag_agent.graph.core", "timer"),
    "generate_hash": ("graphrag_agent.graph.core", "generate_hash"),
    "batch_process": ("graphrag_agent.graph.core", "batch_process"),
    "retry": ("graphrag_agent.graph.core", "retry"),
    "get_performance_stats": ("graphrag_agent.graph.core", "get_performance_stats"),
    "print_performance_stats": ("graphrag_agent.graph.core", "print_performance_stats"),
    # Indexing
    "ChunkIndexManager": ("graphrag_agent.graph.indexing", "ChunkIndexManager"),
    "EntityIndexManager": ("graphrag_agent.graph.indexing", "EntityIndexManager"),
    # Structure
    "GraphStructureBuilder": ("graphrag_agent.graph.structure", "GraphStructureBuilder"),
    # Extraction
    "EntityRelationExtractor": ("graphrag_agent.graph.extraction", "EntityRelationExtractor"),
    "GraphWriter": ("graphrag_agent.graph.extraction", "GraphWriter"),
    # Processing
    "EntityMerger": ("graphrag_agent.graph.processing", "EntityMerger"),
    "SimilarEntityDetector": ("graphrag_agent.graph.processing", "SimilarEntityDetector"),
    "GDSConfig": ("graphrag_agent.graph.processing", "GDSConfig"),
    "EntityDisambiguator": ("graphrag_agent.graph.processing", "EntityDisambiguator"),
    "EntityAligner": ("graphrag_agent.graph.processing", "EntityAligner"),
    "EntityQualityProcessor": ("graphrag_agent.graph.processing", "EntityQualityProcessor"),
}

_INSTALL_HINT = (
    "Optional dependencies required. "
    "Install one of: `pip install 'graphrag-agent[neo4j,search,langchain]'` or "
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

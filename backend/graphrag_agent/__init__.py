"""
GraphRAG Agent - 基于图的综合RAG系统（Core）

Phase 2.5:
- 稳定的 public import 路径为 `graphrag_agent.*`
- 本仓库约定：所有后端代码物理位置收敛到 `backend/` 下，避免再次散落到仓库根目录
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Tuple

__version__ = "0.1.0"

_LAZY_IMPORTS: Dict[str, Tuple[str, str]] = {
    # ============ 1. 图谱构建模块 ============
    "EntityRelationExtractor": ("graphrag_agent.graph", "EntityRelationExtractor"),
    "GraphWriter": ("graphrag_agent.graph", "GraphWriter"),
    "GraphStructureBuilder": ("graphrag_agent.graph", "GraphStructureBuilder"),
    "EntityMerger": ("graphrag_agent.graph", "EntityMerger"),
    "SimilarEntityDetector": ("graphrag_agent.graph", "SimilarEntityDetector"),
    "EntityDisambiguator": ("graphrag_agent.graph", "EntityDisambiguator"),
    "EntityAligner": ("graphrag_agent.graph", "EntityAligner"),
    "EntityQualityProcessor": ("graphrag_agent.graph", "EntityQualityProcessor"),
    "ChunkIndexManager": ("graphrag_agent.graph", "ChunkIndexManager"),
    "EntityIndexManager": ("graphrag_agent.graph", "EntityIndexManager"),
    "CommunityDetectorFactory": ("graphrag_agent.community", "CommunityDetectorFactory"),
    "CommunitySummarizerFactory": ("graphrag_agent.community", "CommunitySummarizerFactory"),
    # ============ 2. 搜索模块 ============
    "LocalSearch": ("graphrag_agent.search", "LocalSearch"),
    "GlobalSearch": ("graphrag_agent.search", "GlobalSearch"),
    "LocalSearchTool": ("graphrag_agent.search", "LocalSearchTool"),
    "GlobalSearchTool": ("graphrag_agent.search", "GlobalSearchTool"),
    "HybridSearchTool": ("graphrag_agent.search", "HybridSearchTool"),
    "NaiveSearchTool": ("graphrag_agent.search", "NaiveSearchTool"),
    "DeepResearchTool": ("graphrag_agent.search", "DeepResearchTool"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr_name = _LAZY_IMPORTS[name]
    module = import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> Any:
    return sorted(set(list(globals().keys()) + list(_LAZY_IMPORTS.keys())))


__all__ = [
    "__version__",
    "EntityRelationExtractor",
    "GraphWriter",
    "GraphStructureBuilder",
    "EntityMerger",
    "SimilarEntityDetector",
    "EntityDisambiguator",
    "EntityAligner",
    "EntityQualityProcessor",
    "ChunkIndexManager",
    "EntityIndexManager",
    "CommunityDetectorFactory",
    "CommunitySummarizerFactory",
    "LocalSearch",
    "GlobalSearch",
    "LocalSearchTool",
    "GlobalSearchTool",
    "HybridSearchTool",
    "NaiveSearchTool",
    "DeepResearchTool",
]

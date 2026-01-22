from __future__ import annotations

from typing import Any

from graphrag_agent.ports.neo4jdb import GraphClient

from .base import BaseCommunityDetector
from .leiden import LeidenDetector
from .sllpa import SLLPADetector


class CommunityDetectorFactory:
    """社区检测器工厂类"""

    ALGORITHMS = {
        "leiden": LeidenDetector,
        "sllpa": SLLPADetector,
    }

    @classmethod
    def create(cls, algorithm: str, gds: Any, graph: GraphClient) -> BaseCommunityDetector:
        algorithm = (algorithm or "").lower().strip()
        if algorithm not in cls.ALGORITHMS:
            raise ValueError(f"不支持的算法: {algorithm}")
        return cls.ALGORITHMS[algorithm](gds, graph)


__all__ = ["CommunityDetectorFactory"]


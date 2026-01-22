from __future__ import annotations

from graphrag_agent.ports.neo4jdb import GraphClient

from .base import BaseSummarizer
from .leiden import LeidenSummarizer
from .sllpa import SLLPASummarizer


class CommunitySummarizerFactory:
    """社区摘要生成器工厂类"""

    SUMMARIZERS = {
        "leiden": LeidenSummarizer,
        "sllpa": SLLPASummarizer,
    }

    @classmethod
    def create_summarizer(cls, algorithm: str, graph: GraphClient) -> BaseSummarizer:
        algorithm = (algorithm or "").lower().strip()
        if algorithm not in cls.SUMMARIZERS:
            raise ValueError(f"不支持的算法类型: {algorithm}")
        return cls.SUMMARIZERS[algorithm](graph)


__all__ = ["CommunitySummarizerFactory"]


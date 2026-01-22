from __future__ import annotations

from typing import Any


class RAGAgentFactory:
    """
    RAG Agent 工厂：负责把 agent_type 映射为 graphrag_agent 的具体 Agent 类并创建实例。

    注意：缓存/会话隔离由上层 manager 负责；factory 只负责“创建”。
    """

    def create_agent(self, agent_type: str, *, kb_prefix: str, agent_mode: str) -> Any:
        from graphrag_agent.agents.graph_agent import GraphAgent
        from graphrag_agent.agents.hybrid_agent import HybridAgent
        from graphrag_agent.agents.naive_rag_agent import NaiveRagAgent
        from graphrag_agent.agents.deep_research_agent import DeepResearchAgent
        from graphrag_agent.agents.fusion_agent import FusionGraphRAGAgent

        agent_classes = {
            "graph_agent": GraphAgent,
            "hybrid_agent": HybridAgent,
            "naive_rag_agent": NaiveRagAgent,
            "deep_research_agent": DeepResearchAgent,
            "fusion_agent": FusionGraphRAGAgent,
        }

        if agent_type not in agent_classes:
            raise ValueError(f"未知的agent类型: {agent_type}")

        agent_class = agent_classes[agent_type]
        try:
            return agent_class(kb_prefix=kb_prefix, agent_mode=agent_mode)
        except TypeError:
            # 兼容未升级的 Agent（不支持 kb_prefix/agent_mode 参数）
            try:
                return agent_class(kb_prefix=kb_prefix)
            except TypeError:
                return agent_class()

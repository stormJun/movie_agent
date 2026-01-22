from __future__ import annotations

from infrastructure.agents.rag_factory.factory import RAGAgentFactory
from infrastructure.agents.rag_factory.manager import RAGAgentManager

rag_factory = RAGAgentFactory()
rag_agent_manager = RAGAgentManager(factory=rag_factory)

__all__ = [
    "RAGAgentFactory",
    "RAGAgentManager",
    "rag_factory",
    "rag_agent_manager",
]


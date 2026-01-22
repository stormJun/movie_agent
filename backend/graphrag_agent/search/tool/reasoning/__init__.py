from graphrag_agent.search.tool.reasoning.nlp import extract_between, extract_from_templates, extract_sentences
from graphrag_agent.search.tool.reasoning.prompts import kb_prompt, num_tokens_from_string
from graphrag_agent.search.tool.reasoning.thinking import ThinkingEngine
from graphrag_agent.search.tool.reasoning.validator import AnswerValidator
from graphrag_agent.search.tool.reasoning.search import DualPathSearcher, QueryGenerator
from graphrag_agent.search.tool.reasoning.kg_builder import DynamicKnowledgeGraphBuilder
from graphrag_agent.search.tool.reasoning.evidence import EvidenceChainTracker

_COMMUNITY_ENHANCE_IMPORT_ERROR: Exception | None = None
try:
    # Optional dependency chain: numpy / scikit-learn / pandas.
    from graphrag_agent.search.tool.reasoning.community_enhance import (  # noqa: F401
        CommunityAwareSearchEnhancer,
    )
except Exception as exc:  # noqa: BLE001
    _COMMUNITY_ENHANCE_IMPORT_ERROR = exc

    class CommunityAwareSearchEnhancer:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "CommunityAwareSearchEnhancer requires optional dependencies "
                "(e.g. `numpy`, `scikit-learn`, `pandas`, `jieba`). "
                "Install them or avoid importing/using this enhancer."
            ) from _COMMUNITY_ENHANCE_IMPORT_ERROR

__all__ = [
    "extract_between",
    "extract_from_templates",
    "extract_sentences",
    "kb_prompt",
    "num_tokens_from_string",
    "ThinkingEngine",
    "AnswerValidator",
    "DualPathSearcher",
    "QueryGenerator",
    "CommunityAwareSearchEnhancer",
    "DynamicKnowledgeGraphBuilder",
    "EvidenceChainTracker",
]

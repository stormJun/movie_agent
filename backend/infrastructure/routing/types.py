from dataclasses import dataclass
from typing import Any, Literal, Optional

KBPrefix = Literal["movie", "edu", "general"]
QueryIntent = Literal["qa", "recommend", "list", "compare", "unknown"]
MediaTypeHint = Literal["movie", "tv", "person", "mixed", "unknown"]
AgentType = Literal["graph_agent", "hybrid_agent", "naive_rag_agent", "fusion_agent"]


@dataclass(frozen=True)
class KBRoutingResult:
    kb_prefix: KBPrefix
    confidence: float
    method: Literal["heuristic", "llm", "fallback"]
    reason: str = ""
    # Query-level hints (used by enrichment and response shaping).
    query_intent: QueryIntent = "unknown"
    media_type_hint: MediaTypeHint = "unknown"
    # Optional structured filters for recommendation-style queries.
    # Example:
    # {"year": 2024, "origin_country": "CN", "original_language": "zh",
    #  "region": "CN", "date_range": {"gte": "2024-01-01", "lte": "2024-12-31"}}
    filters: Optional[dict[str, Any]] = None
    # 新增：提取的实体信息
    # 格式：{"low_level": ["喜宴", "导演"], "high_level": ["电影", "导演身份"]}
    extracted_entities: Optional[dict[str, Any]] = None
    # 新增：LLM 推荐的 agent_type
    # 依据：query_intent 和查询复杂度
    recommended_agent_type: AgentType = "hybrid_agent"

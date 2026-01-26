from dataclasses import dataclass, field
from typing import Literal, Optional, Any

KBPrefix = Literal["movie", "edu", "general"]


@dataclass(frozen=True)
class KBRoutingResult:
    kb_prefix: KBPrefix
    confidence: float
    method: Literal["heuristic", "llm", "fallback"]
    reason: str = ""
    # 新增：提取的实体信息
    # 格式：{"low_level": ["喜宴", "导演"], "high_level": ["电影", "导演身份"]}
    extracted_entities: Optional[dict[str, Any]] = None

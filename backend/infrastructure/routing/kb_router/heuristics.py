from typing import Optional, Dict, Any, Set

from .types import KBRoutingResult
from domain.config.kb_routing import get_kb_routing_rules


def _get_rules() -> Dict[str, Any]:
    return get_kb_routing_rules()


def _normalize_keywords(values: list[str] | None) -> Set[str]:
    return {kw.strip().lower() for kw in (values or []) if kw and kw.strip()}


def _keyword_score(text: str, keywords: set[str]) -> int:
    return sum(1 for kw in keywords if kw and kw in text)


def route_by_heuristic(message: str) -> Optional[KBRoutingResult]:
    text = (message or "").strip().lower()
    if not text:
        return None

    rules = _get_rules().get("heuristic_rules", {})
    kb_rules = rules.get("kbs", {})
    min_score = int(rules.get("min_score", 2))

    edu_keywords = _normalize_keywords(
        kb_rules.get("edu", {}).get("keywords", [])
    )
    movie_keywords = _normalize_keywords(
        kb_rules.get("movie", {}).get("keywords", [])
    )

    edu_score = _keyword_score(text, edu_keywords)
    movie_score = _keyword_score(text, movie_keywords)

    if edu_score >= min_score and edu_score > movie_score:
        return KBRoutingResult(
            kb_prefix="edu",
            confidence=0.95,
            method="heuristic",
            reason=f"edu_keywords={edu_score} > movie_keywords={movie_score}",
        )
    if movie_score >= min_score and movie_score > edu_score:
        return KBRoutingResult(
            kb_prefix="movie",
            confidence=0.95,
            method="heuristic",
            reason=f"movie_keywords={movie_score} > edu_keywords={edu_score}",
        )

    return None

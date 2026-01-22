import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Optional, Tuple

from infrastructure.models import get_llm_model

from .heuristics import route_by_heuristic
from .types import KBPrefix, KBRoutingResult
from .utils import normalize_kb_prefix, parse_loose_json_dict


_ROUTER_LLM_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_ROUTER_LLM_TIMEOUT_S = 15.0


def route_kb_prefix(
    message: str, requested_kb_prefix: Optional[str] = None
) -> Tuple[KBPrefix, KBRoutingResult]:
    """
    Decide which KB to use (movie vs edu vs general).

    Returns:
        (kb_prefix, routing_result)
    """
    requested = normalize_kb_prefix(requested_kb_prefix)

    heuristic = route_by_heuristic(message)
    if heuristic is not None:
        return heuristic.kb_prefix, heuristic

    llm = get_llm_model()
    prompt = (
        "你是一个知识库路由器，只在 movie / edu / general 三个选项中选择一个。\n"
        "规则：\n"
        "- 电影/演员/导演/剧情/片单推荐 => movie\n"
        "- 学生管理/课程/考勤/学籍/退学/处分/成绩 => edu\n"
        "- 其他无法匹配以上领域的问题 => general\n"
        "只输出 JSON，不要输出其他文字：\n"
        "{\"kb_prefix\": \"movie|edu|general\", \"confidence\": 0~1, \"reason\": \"...\"}\n"
        f"用户问题：{message}"
    )

    try:
        future = _ROUTER_LLM_EXECUTOR.submit(llm.invoke, prompt)
        resp = future.result(timeout=_ROUTER_LLM_TIMEOUT_S)
        content = resp.content if hasattr(resp, "content") else str(resp)
    except TimeoutError:
        fallback = requested if requested in {"movie", "edu", "general"} else "general"
        result = KBRoutingResult(
            kb_prefix=fallback,
            confidence=0.0,
            method="timeout",
            reason=f"route timeout after {_ROUTER_LLM_TIMEOUT_S}s",
        )
        return fallback, result
    except Exception as exc:
        fallback = requested if requested in {"movie", "edu", "general"} else "general"
        result = KBRoutingResult(
            kb_prefix=fallback,
            confidence=0.0,
            method="fallback",
            reason=str(exc),
        )
        return fallback, result

    parsed = parse_loose_json_dict(content)
    kb = str(parsed.get("kb_prefix", "")).strip() if parsed else ""
    kb = normalize_kb_prefix(kb)
    if kb not in {"movie", "edu", "general"}:
        kb = requested if requested in {"movie", "edu", "general"} else "general"

    try:
        conf = float(parsed.get("confidence", 0.6)) if parsed else 0.6
    except Exception:
        conf = 0.6
    conf = max(0.0, min(1.0, conf))

    reason = str(parsed.get("reason", "")).strip() if parsed else ""
    reason = re.sub(r"\s+", " ", reason)[:200]

    result = KBRoutingResult(
        kb_prefix=kb,
        confidence=conf,
        method="llm",
        reason=reason,
    )
    return kb, result

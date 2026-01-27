import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Optional, Tuple

from infrastructure.models import get_llm_model

from .types import KBPrefix, KBRoutingResult
from .utils import normalize_kb_prefix, parse_loose_json_dict


_ROUTER_LLM_EXECUTOR = ThreadPoolExecutor(max_workers=1)
_ROUTER_LLM_TIMEOUT_S = 15.0


def route_kb_prefix(
    message: str, requested_kb_prefix: Optional[str] = None
) -> Tuple[KBPrefix, KBRoutingResult]:
    """
    Decide which KB to use (movie vs edu vs general) and extract entities.

    All routing decisions are made by LLM for more accurate and nuanced classification.

    Returns:
        (kb_prefix, routing_result)
    """
    requested = normalize_kb_prefix(requested_kb_prefix)

    # 直接使用 LLM 路由，不再使用启发式关键词匹配
    llm = get_llm_model()
    prompt = (
        "你是一个知识库路由器和意图/实体提取器。请完成五个任务：\n"
        "1. 路由判断：在 movie / edu / general 三个选项中选择一个\n"
        "2. 意图识别：判断用户是问答(qa)还是推荐(recommend)等\n"
        "3. 媒体类型提示：电影/电视剧/人物等，用于后续 enrichment\n"
        "4. 实体提取：提取用户问题中的关键实体\n"
        "5. 结构化筛选条件(filters)：从用户表达中抽取年份/地区/语言等约束（用于推荐/发现接口）\n"
        "6. Agent推荐：根据查询类型推荐最合适的检索 Agent\n\n"
        "路由规则：\n"
        "- 电影/电视剧/演员/导演/剧情/片单推荐 => movie\n"
        "- 学生管理/课程/考勤/学籍/退学/处分/成绩 => edu\n"
        "- 其他无法匹配以上领域的问题 => general\n\n"
        "意图(query_intent) 取值：qa / recommend / list / compare / unknown\n"
        "- qa: 询问事实、解释、是谁/是什么/为什么\n"
        "- recommend: 推荐、安利、给我几部/给我一些\n"
        "- list: 列举、有哪些、都有哪些、列出\n"
        "- compare: 对比、哪个好、区别\n\n"
        "媒体类型(media_type_hint) 取值：movie / tv / person / mixed / unknown\n"
        "- tv: 明确在问电视剧/剧集\n"
        "- person: 明确在问某个人（导演/演员/编剧等）\n"
        "- mixed: 同时包含人物+作品 或 多种媒体\n\n"
        "Agent 推荐(recommended_agent_type) 取值：graph_agent / hybrid_agent / naive_rag_agent / fusion_agent\n\n"
        "**Agent 选择规则**：\n"
        "- graph_agent: 适合需要快速响应的简单事实查询\n"
        "  * 示例：某部电影哪一年上映？、谁导演了XX？、XX的主演是谁？\n"
        "  * 特点：LocalSearch 向量检索 + GlobalSearch 社区摘要，速度快\n\n"
        "- hybrid_agent: 适合需要深度理解的分析性查询\n"
        "  * 示例：李安的导演风格是怎样的？、XX电影的主题是什么？、分析XX和YY的相似之处\n"
        "  * 特点：双级检索（低级实体+高级概念），理解深入\n\n"
        "- naive_rag_agent: 适合纯语义匹配的查询\n"
        "  * 示例：有哪些类似XX的电影？、找一些关于XX的内容\n"
        "  * 特点：纯向量检索，适合模糊匹配\n\n"
        "- fusion_agent: 适合需要综合多个角度的推荐/比较类查询\n"
        "  * 示例：推荐几部类似XX的电影、对比一下XX和YY的区别\n"
        "  * 特点：融合多个 Agent 的检索结果，全面综合\n\n"
        "**Agent 推荐策略**：\n"
        "- 如果 query_intent=qa 且问题简单明确 → graph_agent\n"
        "- 如果 query_intent=qa 但需要分析解读 → hybrid_agent\n"
        "- 如果 query_intent=recommend/compare/list → fusion_agent\n"
        "- 如果 query_intent=unknown 且问题模糊 → naive_rag_agent 或 hybrid_agent\n\n"
        "filters 规则：\n"
        "- 推荐类问题尽量抽取 filters\n"
        "- year: 4位年份，例如 2024\n"
        "- origin_country: 国家/地区两位代码（如 中国=CN、美国=US、日本=JP、韩国=KR）\n"
        "- original_language: 语言两位代码（如 中文=zh、英文=en、日文=ja、韩文=ko）\n"
        "- region: 发行/地区两位代码（如 CN/US）\n"
        "- date_range: {\"gte\": \"YYYY-MM-DD\", \"lte\": \"YYYY-MM-DD\"}（可选）\n\n"
        "实体提取规则：\n"
        "- low_level: 具体实体（如电影名、人名）\n"
        "- high_level: 抽象概念（如类型、关系）\n\n"
        "只输出 JSON，不要输出其他文字：\n"
        "{\"kb_prefix\": \"movie|edu|general\", \"confidence\": 0~1, \"reason\": \"...\", "
        "\"query_intent\": \"qa|recommend|list|compare|unknown\", "
        "\"media_type_hint\": \"movie|tv|person|mixed|unknown\", "
        "\"filters\": {\"year\": 2024, \"origin_country\": \"CN\", \"original_language\": \"zh\", \"region\": \"CN\", "
        "\"date_range\": {\"gte\": \"2024-01-01\", \"lte\": \"2024-12-31\"}}, "
        "\"extracted_entities\": {\"low_level\": [...], \"high_level\": [...]}, "
        "\"recommended_agent_type\": \"graph_agent|hybrid_agent|naive_rag_agent|fusion_agent\"}\n"
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
            extracted_entities=None,
        )
        return fallback, result
    except Exception as exc:
        fallback = requested if requested in {"movie", "edu", "general"} else "general"
        result = KBRoutingResult(
            kb_prefix=fallback,
            confidence=0.0,
            method="fallback",
            reason=str(exc),
            extracted_entities=None,
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

    query_intent = "unknown"
    media_type_hint = "unknown"
    filters: dict[str, Any] | None = None
    if parsed:
        qi = str(parsed.get("query_intent", "")).strip().lower()
        if qi in {"qa", "recommend", "list", "compare", "unknown"}:
            query_intent = qi
        mt = str(parsed.get("media_type_hint", "")).strip().lower()
        if mt in {"movie", "tv", "person", "mixed", "unknown"}:
            media_type_hint = mt
        raw_filters = parsed.get("filters")
        if isinstance(raw_filters, dict):
            # Best-effort sanitation: keep only expected keys and normalize types.
            cleaned: dict[str, Any] = {}
            if "year" in raw_filters:
                try:
                    y = int(raw_filters.get("year"))
                    if 1900 <= y <= 2100:
                        cleaned["year"] = y
                except Exception:
                    pass
            for k in ("origin_country", "original_language", "region", "sort_by"):
                v = raw_filters.get(k)
                if isinstance(v, str) and v.strip():
                    cleaned[k] = v.strip()
            dr = raw_filters.get("date_range")
            if isinstance(dr, dict):
                gte = dr.get("gte")
                lte = dr.get("lte")
                date_range: dict[str, str] = {}
                if isinstance(gte, str) and gte.strip():
                    date_range["gte"] = gte.strip()
                if isinstance(lte, str) and lte.strip():
                    date_range["lte"] = lte.strip()
                if date_range:
                    cleaned["date_range"] = date_range
            if cleaned:
                filters = cleaned

    # 提取实体信息
    extracted_entities = None
    if parsed and "extracted_entities" in parsed:
        try:
            entities = parsed["extracted_entities"]
            if isinstance(entities, dict):
                low_level = entities.get("low_level", [])
                high_level = entities.get("high_level", [])
                if isinstance(low_level, list) and isinstance(high_level, list):
                    extracted_entities = {
                        "low_level": low_level,
                        "high_level": high_level,
                    }
        except Exception:
            extracted_entities = None

    # 提取推荐的 agent_type
    recommended_agent_type = "hybrid_agent"  # 默认值
    if parsed and "recommended_agent_type" in parsed:
        try:
            raw_agent = str(parsed["recommended_agent_type"]).strip().lower()
            # 验证是否为有效的 agent_type
            valid_agents = {"graph_agent", "hybrid_agent", "naive_rag_agent", "fusion_agent"}
            if raw_agent in valid_agents:
                recommended_agent_type = raw_agent  # type: ignore[assignment]
        except Exception:
            pass

    result = KBRoutingResult(
        kb_prefix=kb,
        confidence=conf,
        method="llm",
        reason=reason,
        query_intent=query_intent,  # type: ignore[arg-type]
        media_type_hint=media_type_hint,  # type: ignore[arg-type]
        filters=filters,
        extracted_entities=extracted_entities,
        recommended_agent_type=recommended_agent_type,  # type: ignore[arg-type]
    )
    return kb, result

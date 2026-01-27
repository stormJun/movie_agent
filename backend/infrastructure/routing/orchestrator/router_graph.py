from __future__ import annotations

from typing import Optional

from langgraph.graph import END, StateGraph

from infrastructure.config.settings import (
    KB_AUTO_ROUTE,
    KB_AUTO_ROUTE_MIN_CONFIDENCE,
    KB_AUTO_ROUTE_OVERRIDE,
)
from infrastructure.routing.kb_router import route_kb_prefix

from .state import ChatRouteState, RouteDecision


def _normalize_kb_prefix(kb_prefix: Optional[str]) -> str:
    raw = (kb_prefix or "").strip()
    if raw.endswith(":"):
        raw = raw[:-1]
    return raw.strip()


def _intent_detect_node(state: ChatRouteState) -> ChatRouteState:
    if not KB_AUTO_ROUTE:
        return {}

    routed_prefix, routing_info = route_kb_prefix(
        state["message"], requested_kb_prefix=state.get("requested_kb_prefix")
    )

    return {
        "routed_kb_prefix": routed_prefix,
        "confidence": getattr(routing_info, "confidence", 0.0) or 0.0,
        "method": getattr(routing_info, "method", "") or "",
        "reason": getattr(routing_info, "reason", "") or "",
        "query_intent": getattr(routing_info, "query_intent", "unknown") or "unknown",
        "media_type_hint": getattr(routing_info, "media_type_hint", "unknown") or "unknown",
        "filters": getattr(routing_info, "filters", None),
        # 保留路由阶段抽取的实体（extracted_entities），供后续 enrichment 直接使用（减少二次抽取误差）。
        "extracted_entities": getattr(routing_info, "extracted_entities", None),
        # LLM 推荐的 agent：主链路优先使用该值（避免前端/调用方传错或默认值不合适）。
        "resolved_agent_type": getattr(routing_info, "recommended_agent_type", None),
    }


def _apply_override_policy_node(state: ChatRouteState) -> ChatRouteState:
    requested = _normalize_kb_prefix(state.get("requested_kb_prefix"))
    routed = _normalize_kb_prefix(state.get("routed_kb_prefix") or "")

    if not KB_AUTO_ROUTE:
        # When auto routing is disabled and the caller didn't specify a KB,
        # treat it as "general" (no retrieval).
        return {"kb_prefix": requested or "general"}

    if not requested:
        return {"kb_prefix": routed or "general"}

    if not routed:
        return {"kb_prefix": requested or "general"}

    if not KB_AUTO_ROUTE_OVERRIDE:
        return {"kb_prefix": requested}

    confidence = float(state.get("confidence") or 0.0)
    if confidence < KB_AUTO_ROUTE_MIN_CONFIDENCE:
        return {"kb_prefix": requested}

    return {"kb_prefix": routed}


def _worker_select_node(state: ChatRouteState) -> ChatRouteState:
    kb_raw = _normalize_kb_prefix(state.get("kb_prefix") or "")
    if not kb_raw or kb_raw == "general":
        # Explicit "no retrieval" path: keep worker_name empty so downstream
        # components don't accidentally treat it as a retrieval worker.
        return {"worker_name": ""}

    # agent 选择优先级：
    # 1) resolved_agent_type：路由 LLM 推荐（主路径默认以此为准）
    # 2) agent_type：调用方显式指定（保留兼容，但前端已不再传）
    # 3) 默认 hybrid_agent
    resolved_agent = state.get("resolved_agent_type")
    if resolved_agent and isinstance(resolved_agent, str) and resolved_agent.strip():
        agent_type = resolved_agent.strip()
    else:
        agent_type = (state.get("agent_type") or "").strip() or "hybrid_agent"

    # worker_name v2: {kb_prefix}:{agent_type}:{agent_mode}
    return {"worker_name": f"{kb_raw}:{agent_type}:retrieve_only"}


def build_router_graph():
    graph = StateGraph(ChatRouteState)
    graph.add_node("intent_detect", _intent_detect_node)
    graph.add_node("apply_override_policy", _apply_override_policy_node)
    graph.add_node("worker_select", _worker_select_node)

    graph.set_entry_point("intent_detect")
    graph.add_edge("intent_detect", "apply_override_policy")
    graph.add_edge("apply_override_policy", "worker_select")
    graph.add_edge("worker_select", END)
    return graph.compile()


_ROUTER_GRAPH = build_router_graph()


def invoke_router_graph(
    *,
    message: str,
    session_id: str,
    agent_type: str,
    requested_kb_prefix: Optional[str] = None,
) -> RouteDecision:
    requested = _normalize_kb_prefix(requested_kb_prefix)

    initial: ChatRouteState = {
        "message": message,
        "session_id": session_id,
        "agent_type": agent_type,
        "requested_kb_prefix": requested,
    }
    final_state: ChatRouteState = _ROUTER_GRAPH.invoke(initial)

    routed = _normalize_kb_prefix(final_state.get("routed_kb_prefix") or "")
    effective = _normalize_kb_prefix(final_state.get("kb_prefix") or "")

    # Extract the agent_type that was actually used
    worker_name = str(final_state.get("worker_name") or "")
    actual_agent_type = None
    if worker_name and ":" in worker_name:
        # worker_name format: {kb_prefix}:{agent_type}:{agent_mode}
        parts = worker_name.split(":")
        if len(parts) >= 2:
            actual_agent_type = parts[1]

    return RouteDecision(
        requested_kb_prefix=requested,
        routed_kb_prefix=routed,
        kb_prefix=effective,
        confidence=float(final_state.get("confidence") or 0.0),
        method=str(final_state.get("method") or ""),
        reason=str(final_state.get("reason") or ""),
        worker_name=worker_name,
        query_intent=str(final_state.get("query_intent") or "unknown"),  # type: ignore[arg-type]
        media_type_hint=str(final_state.get("media_type_hint") or "unknown"),  # type: ignore[arg-type]
        filters=final_state.get("filters"),
        extracted_entities=final_state.get("extracted_entities"),
        recommended_agent_type=final_state.get("resolved_agent_type"),
        resolved_agent_type=actual_agent_type,
    )

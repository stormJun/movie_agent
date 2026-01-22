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

    return RouteDecision(
        requested_kb_prefix=requested,
        routed_kb_prefix=routed,
        kb_prefix=effective,
        confidence=float(final_state.get("confidence") or 0.0),
        method=str(final_state.get("method") or ""),
        reason=str(final_state.get("reason") or ""),
        worker_name=str(final_state.get("worker_name") or ""),
    )

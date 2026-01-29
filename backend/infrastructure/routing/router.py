from __future__ import annotations

from typing import Optional

from application.ports.router_port import RouterPort
from domain.chat.entities.route_decision import RouteDecision
from infrastructure.routing.orchestrator import invoke_router_graph


class RouterGraphAdapter(RouterPort):
    def route(
        self,
        *,
        message: str,
        session_id: str,
        requested_kb: Optional[str],
    ) -> RouteDecision:
        return invoke_router_graph(
            message=message,
            session_id=session_id,
            requested_kb_prefix=requested_kb,
        )

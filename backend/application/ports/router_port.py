from __future__ import annotations

from typing import Optional, Protocol

from domain.chat.entities.route_decision import RouteDecision


class RouterPort(Protocol):
    def route(
        self,
        *,
        message: str,
        session_id: str,
        requested_kb: Optional[str],
    ) -> RouteDecision:
        ...

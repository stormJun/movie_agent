from __future__ import annotations

from typing import Any, Protocol


class GDSProvider(Protocol):
    def get_gds_client(self, uri: str, username: str, password: str) -> Any:
        ...


_gds_provider: GDSProvider | None = None


def set_gds_provider(provider: GDSProvider) -> None:
    global _gds_provider
    _gds_provider = provider


def _resolve_gds_provider() -> GDSProvider:
    if _gds_provider is None:
        raise RuntimeError(
            "GDS provider not configured. "
            "Call graphrag_agent.ports.set_gds_provider(...) before using GDS."
        )
    return _gds_provider


def get_gds_client(uri: str, username: str, password: str) -> Any:
    return _resolve_gds_provider().get_gds_client(uri, username, password)


__all__ = [
    "GDSProvider",
    "set_gds_provider",
    "get_gds_client",
]

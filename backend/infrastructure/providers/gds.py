from __future__ import annotations

"""GDS provider for graphrag_agent ports.

Canonical provider location. Injected via `backend/infrastructure/bootstrap.py`.

Important:
  - `graphdatascience` (and its transitive deps like pandas) are optional.
  - Avoid importing them at module import time so "core-only" usage and
    lightweight test runs don't require them.
"""

from typing import Any


def get_gds_client(uri: str, username: str, password: str) -> Any:
    try:
        from graphdatascience import GraphDataScience  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "GraphDataScience provider requires optional dependency `graphdatascience` "
            "(and a working `pandas` installation). "
            "Install with: `pip install graphdatascience pandas`."
        ) from exc
    return GraphDataScience(uri, auth=(username, password))


__all__ = ["get_gds_client"]

from __future__ import annotations

"""Semantic bridge for infrastructure.

Rule:
- "Semantic defaults" are defined in `backend/config/rag_semantics.py`
- Infra must not import `config.*` directly (to keep boundaries clear)
- At runtime, infra injects semantic overrides into `graphrag_agent.config.settings`
  via `backend/infrastructure/config/graphrag_settings.py`

This module provides a stable, explicit place for infra components to read
semantic values (read-only) from core settings.
"""

from graphrag_agent.config import settings as core_settings


def get_response_type() -> str:
    return (getattr(core_settings, "response_type", None) or "多个段落").strip() or "多个段落"


__all__ = ["get_response_type"]


from __future__ import annotations

import json
from typing import Any, Iterable


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        # Quote strings so spaces/symbols stay readable and unambiguous
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


def format_kv(**fields: Any) -> str:
    """
    Render a compact single-line key=value log string.

    Example:
      seq=1 event="start" elapsed_seconds=0.12 session_id="..."
    """
    items: Iterable[tuple[str, Any]] = fields.items()
    parts: list[str] = []
    for key, value in items:
        if value is None:
            continue
        parts.append(f"{key}={_format_value(value)}")
    return " ".join(parts)


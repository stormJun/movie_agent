from __future__ import annotations

from typing import Any


def build_context_from_runs(*, runs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for run in runs:
        agent_type = (run.get("agent_type") or "unknown").strip()
        context = (run.get("context") or "").strip()
        if not context:
            continue
        parts.append(f"### Strategy: {agent_type}\n\n{context}")
    return "\n\n---\n\n".join(parts).strip()

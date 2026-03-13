from __future__ import annotations

from typing import Any, Dict, Optional


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_stream_event(event: Any) -> Dict[str, Any]:
    """
    Normalize backend-emitted stream events into a stable SSE payload contract.

    Contract (P0 for React):
      - progress.content always contains: stage, completed, total, error
      - error is present even when not failing (null)
    """
    if not isinstance(event, dict):
        return {"status": "token", "content": str(event)}

    # Backward-compat: some executors yield {"execution_log": {...}} directly.
    if "execution_log" in event:
        return {"status": "execution_log", "content": event.get("execution_log")}

    status = str(event.get("status") or "")
    if not status:
        # Fallback to a safe token-ish payload.
        return {"status": "token", "content": str(event)}

    if status == "progress":
        content = _as_dict(event.get("content"))
        stage = str(content.get("stage") or "progress")

        completed_raw = content.get("completed")
        total_raw = content.get("total")

        completed = int(completed_raw) if isinstance(completed_raw, (int, float)) else 0
        total = int(total_raw) if isinstance(total_raw, (int, float)) else 0

        error: Optional[str]
        error_raw = content.get("error")
        error = str(error_raw) if isinstance(error_raw, str) and error_raw.strip() else None

        agent_type_raw = content.get("agent_type")
        agent_type = str(agent_type_raw) if isinstance(agent_type_raw, str) and agent_type_raw.strip() else ""

        retrieval_count_raw = content.get("retrieval_count")
        retrieval_count = (
            int(retrieval_count_raw)
            if isinstance(retrieval_count_raw, (int, float))
            else None
        )

        return {
            "status": "progress",
            "content": {
                "stage": stage,
                "completed": completed,
                "total": total,
                "error": error,
                # Optional but stabilized for UI consumption.
                "agent_type": agent_type,
                "retrieval_count": retrieval_count,
            },
        }

    if status == "token":
        return {"status": "token", "content": str(event.get("content") or "")}

    if status == "error":
        # Contract: `message` is always present and is a string.
        message = event.get("message")
        if isinstance(message, str) and message.strip():
            return {"status": "error", "message": message.strip()}

        content = event.get("content")
        if isinstance(content, str) and content.strip():
            return {"status": "error", "message": content.strip()}

        if isinstance(content, dict):
            nested = content.get("message")
            if isinstance(nested, str) and nested.strip():
                return {"status": "error", "message": nested.strip(), "content": content}
            return {"status": "error", "message": "unknown error", "content": content}

        return {"status": "error", "message": "unknown error"}

    # Pass-through for other statuses (start/done/error/...).
    return event

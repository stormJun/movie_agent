from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union


class DebugDataCollector:
    """Per-request debug data collector.

    Notes:
    - Create a new instance per request (not thread-safe by design).
    - Only store JSON-serializable content (dict/list/str/int/float/bool/None).
    """

    def __init__(self, request_id: str, user_id: str, session_id: str) -> None:
        self.request_id = request_id
        self.user_id = user_id
        self.session_id = session_id
        self.timestamp = datetime.now()

        self.execution_log: List[Dict[str, Any]] = []
        self.progress_events: List[Dict[str, Any]] = []
        self.error_events: List[Dict[str, Any]] = []
        self.route_decision: Optional[Dict[str, Any]] = None
        self.rag_runs: List[Dict[str, Any]] = []
        self.trace: List[Dict[str, Any]] = []
        self.kg_data: Optional[Dict[str, Any]] = None

    def add_event(self, event_type: str, content: Union[Dict[str, Any], List[Any]]) -> None:
        if event_type == "execution_log":
            if isinstance(content, dict):
                entry = dict(content)
                entry["timestamp"] = datetime.now().isoformat()
                self.execution_log.append(entry)
            return

        if event_type == "progress":
            if isinstance(content, dict):
                self.progress_events.append(dict(content))
            return

        if event_type == "error":
            if isinstance(content, dict):
                self.error_events.append(
                    {
                        "message": str(content.get("message") or ""),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            return

        if event_type == "route_decision":
            if isinstance(content, dict):
                self.route_decision = dict(content)
            return

        if event_type == "rag_runs":
            if isinstance(content, list):
                # Expect List[Dict[str, Any]].
                self.rag_runs = [x for x in content if isinstance(x, dict)]
            return

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "execution_log": self.execution_log,
            "progress_events": self.progress_events,
            "error_events": self.error_events,
            "route_decision": self.route_decision,
            "rag_runs": self.rag_runs,
            "trace": self.trace,
            "kg_data": self.kg_data,
        }


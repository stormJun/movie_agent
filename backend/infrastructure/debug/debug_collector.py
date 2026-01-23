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

    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calculate aggregated performance metrics from execution log.
        
        Returns:
            Dict with total_duration_ms, retrieval_duration_ms, generation_duration_ms,
            routing_duration_ms, node_count, and error_count.
        """
        if not self.execution_log:
            return {
                "total_duration_ms": 0,
                "retrieval_duration_ms": 0,
                "generation_duration_ms": 0,
                "routing_duration_ms": 0,
                "node_count": 0,
                "error_count": 0,
            }

        retrieval_duration = 0
        generation_duration = 0
        routing_duration = 0
        error_count = 0

        for entry in self.execution_log:
            duration_raw = entry.get("duration_ms", 0)
            duration = int(duration_raw) if isinstance(duration_raw, (int, float)) else 0
            node_name = str(entry.get("node", "")).lower()
            node_type = str(entry.get("node_type", "")).lower()

            # Prefer explicit node_type. Only fall back to node name when node_type is missing.
            if node_type in ("retrieval", "search"):
                retrieval_duration += duration
            elif node_type in ("generation", "llm"):
                generation_duration += duration
            elif node_type in ("routing", "route", "decision", "plan"):
                routing_duration += duration
            elif not node_type and duration:
                if any(kw in node_name for kw in ("retrieval", "search", "rag")):
                    retrieval_duration += duration
                elif any(kw in node_name for kw in ("generation", "llm", "generate", "answer")):
                    generation_duration += duration
                elif any(kw in node_name for kw in ("route", "decision", "plan")):
                    routing_duration += duration

            # Count errors
            if entry.get("error") or entry.get("status") == "error":
                error_count += 1

        # Calculate total duration from timestamp difference
        total_duration = 0
        if len(self.execution_log) >= 2:
            try:
                from dateutil import parser
                first_ts = parser.parse(self.execution_log[0].get("timestamp", ""))
                last_ts = parser.parse(self.execution_log[-1].get("timestamp", ""))
                total_duration = int((last_ts - first_ts).total_seconds() * 1000)
            except Exception:
                # Fallback: sum all durations
                total_duration = sum(e.get("duration_ms", 0) for e in self.execution_log)
        elif len(self.execution_log) == 1:
            duration_raw = self.execution_log[0].get("duration_ms", 0)
            total_duration = int(duration_raw) if isinstance(duration_raw, (int, float)) else 0

        return {
            "total_duration_ms": total_duration,
            "retrieval_duration_ms": retrieval_duration,
            "generation_duration_ms": generation_duration,
            "routing_duration_ms": routing_duration,
            "node_count": len(self.execution_log),
            "error_count": error_count,
        }

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
            "performance_metrics": self._calculate_performance_metrics(),
        }

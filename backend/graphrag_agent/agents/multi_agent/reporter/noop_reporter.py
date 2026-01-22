"""
No-op reporter for retrieve_only mode.

We still need to provide a reporter instance to the orchestrator, but in
retrieve_only mode we explicitly disable report generation, so this reporter
should never be invoked. Keeping it lightweight avoids pulling model providers
in tests/core-only contexts.
"""

from __future__ import annotations

from typing import Optional

from graphrag_agent.agents.multi_agent.core.state import PlanExecuteState
from graphrag_agent.agents.multi_agent.reporter.base_reporter import ReportResult


class NoopReporter:
    def generate_report(
        self, state: PlanExecuteState, *, report_type: Optional[str] = None
    ) -> Optional[ReportResult]:
        return None


__all__ = ["NoopReporter"]


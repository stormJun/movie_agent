"""
Retrieve-only planner.

This is used by Phase 2 "retrieve_only" paths to avoid LLM planning and to emit a
single deterministic retrieval task, so the orchestration stack can be reused
without generating a final answer/report inside the agent.
"""

from __future__ import annotations

from graphrag_agent.agents.multi_agent.core.plan_spec import (
    AcceptanceCriteria,
    PlanExecutionSignal,
    PlanSpec,
    ProblemStatement,
    TaskGraph,
    TaskNode,
)
from graphrag_agent.agents.multi_agent.core.state import (
    ExecutionContext,
    PlanContext,
    PlanExecuteState,
)
from graphrag_agent.agents.multi_agent.planner.clarifier import ClarificationResult
from graphrag_agent.agents.multi_agent.planner.base_planner import PlannerResult


class RetrieveOnlyPlanner:
    """
    Deterministic planner for retrieve_only mode.

    It always returns a minimal plan consisting of a single retrieval task,
    defaulting to "hybrid_search".
    """

    def __init__(self, *, task_type: str = "hybrid_search") -> None:
        self._task_type = (task_type or "hybrid_search").strip() or "hybrid_search"

    def generate_plan(
        self,
        state: PlanExecuteState,
        *,
        assumptions: list[str] | None = None,
    ) -> PlannerResult:
        query = (state.input or "").strip()
        if not query and state.messages:
            query = str(getattr(state.messages[-1], "content", "") or "").strip()

        state.plan_context = state.plan_context or PlanContext(original_query=query or "")
        state.execution_context = state.execution_context or ExecutionContext()

        task = TaskNode(
            task_type=self._task_type,  # must match tool registry keys
            description=query or "retrieve_only",
            parameters={"query": query} if query else {},
            priority=1,
        )
        plan_spec = PlanSpec(
            problem_statement=ProblemStatement(original_query=query or ""),
            assumptions=list(assumptions or []),
            task_graph=TaskGraph(nodes=[task], execution_mode="sequential"),
            acceptance_criteria=AcceptanceCriteria(min_evidence_count=0, min_confidence=0.0),
            status="approved",
        )
        state.plan = plan_spec
        state.update_timestamp()

        signal: PlanExecutionSignal = plan_spec.to_execution_signal()
        return PlannerResult(
            plan_spec=plan_spec,
            clarification=ClarificationResult(needs_clarification=False, questions=[]),
            task_decomposition=None,
            review_outcome=None,
            executor_signal=signal,
        )


__all__ = ["RetrieveOnlyPlanner"]


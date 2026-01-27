from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from infrastructure.agents.rag_factory import rag_agent_manager as agent_manager
from infrastructure.config.settings import RAG_ANSWER_TIMEOUT_S
from infrastructure.rag.aggregator import aggregate_run_results
from infrastructure.llm.completion import generate_rag_answer
from infrastructure.rag.answer_generator import build_context_from_runs
from infrastructure.rag.specs import RagRunResult, RagRunSpec
from infrastructure.routing.orchestrator.worker_registry import (
    get_agent_for_worker_name,
    parse_worker_name,
)

logger = logging.getLogger(__name__)


class RagManager:
    async def run_retrieval_for_spec(
        self,
        *,
        spec: RagRunSpec,
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
    ) -> RagRunResult:
        def _invoke() -> RagRunResult:
            try:
                worker_name = str(spec.worker_name or "").strip()
                if worker_name:
                    parsed = parse_worker_name(worker_name)
                    agent = get_agent_for_worker_name(
                        worker_name=worker_name,
                        session_id=session_id,
                        agent_mode="retrieve_only",
                    )
                    effective_agent_type = parsed.agent_type or spec.agent_type or "unknown"
                else:
                    agent = agent_manager.get_agent(
                        spec.agent_type,
                        session_id=session_id,
                        kb_prefix=kb_prefix,
                        agent_mode="retrieve_only",
                    )
                    effective_agent_type = spec.agent_type
                if not hasattr(agent, "retrieve_with_trace"):
                    return RagRunResult(
                        agent_type=effective_agent_type,
                        answer="",
                        error="agent does not support retrieve_with_trace()",
                    )

                call = getattr(agent, "retrieve_with_trace")
                raw = call(message, thread_id=session_id)
                if not isinstance(raw, dict):
                    return RagRunResult(
                        agent_type=effective_agent_type,
                        answer=str(raw),
                        error="unexpected agent result type",
                    )

                return RagRunResult(
                    agent_type=effective_agent_type,
                    context=str(raw.get("context") or ""),
                    answer=str(raw.get("answer") or ""),
                    reference=raw.get("reference"),
                    retrieval_results=raw.get("retrieval_results"),
                    execution_log=raw.get("execution_log") if debug else None,
                    error=raw.get("error"),
                )
            except Exception as e:
                return RagRunResult(agent_type=spec.agent_type, answer="", error=str(e))

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_invoke),
                timeout=spec.timeout_s,
            )
        except asyncio.TimeoutError:
            return RagRunResult(
                agent_type=spec.agent_type,
                answer="",
                error=f"timeout after {spec.timeout_s}s",
            )

    async def run_plan_retrieval(
        self,
        *,
        plan: list[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
    ) -> tuple[list[RagRunResult], RagRunResult, str]:
        runs = await asyncio.gather(
            *[
                self.run_retrieval_for_spec(
                    spec=spec,
                    message=message,
                    session_id=session_id,
                    kb_prefix=kb_prefix,
                    debug=debug,
                )
                for spec in plan
            ]
        )
        aggregated = aggregate_run_results(results=list(runs))

        combined_context = build_context_from_runs(
            runs=[
                {"agent_type": r.agent_type, "context": r.context or ""}
                for r in runs
                if not r.error
            ]
        )
        return list(runs), aggregated, combined_context

    async def run_plan_blocking(
        self,
        *,
        plan: list[RagRunSpec],
        message: str,
        session_id: str,
        kb_prefix: str,
        debug: bool,
        user_id: str | None = None,
        request_id: str | None = None,
        conversation_id: Any | None = None,
        user_message_id: Any | None = None,
        incognito: bool = False,
        memory_context: str | None = None,
        summary: str | None = None,
        episodic_context: str | None = None,
        history: list[dict[str, Any]] | None = None,
        extracted_entities: dict[str, Any] | None = None,
        query_intent: str | None = None,
        media_type_hint: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> tuple[RagRunResult, list[RagRunResult]]:
        runs, aggregated, combined_context = await self.run_plan_retrieval(
            plan=plan,
            message=message,
            session_id=session_id,
            kb_prefix=kb_prefix,
            debug=debug,
        )
        generation_question = message
        generation_history = history

        # Query-time enrichment for non-streaming /chat as well.
        # Keep this conservative: only enrich in movie KB when GraphRAG likely missed the entity.
        if (kb_prefix or "").strip() == "movie":
            try:
                if _should_enrich_by_entity_matching(
                    query=message,
                    graphrag_context=combined_context,
                    extracted_entities=extracted_entities,
                    query_intent=query_intent,
                    media_type_hint=media_type_hint,
                    filters=filters,
                ):
                    from infrastructure.enrichment import get_tmdb_enrichment_service

                    svc = get_tmdb_enrichment_service()
                    if svc is None:
                        logger.debug("enrichment skipped: tmdb service not configured")
                    else:
                        result = await svc.enrich_query(
                            message=message,
                            kb_prefix="movie",
                            extracted_entities=extracted_entities,
                            query_intent=query_intent,
                            media_type_hint=media_type_hint,
                            filters=filters,
                            user_id=user_id,
                            session_id=session_id,
                            request_id=request_id,
                            conversation_id=conversation_id,
                            user_message_id=user_message_id,
                            incognito=incognito,
                        )
                        if result.success and result.transient_graph and not result.transient_graph.is_empty():
                            enriched_text = result.transient_graph.to_context_text().strip()
                            if enriched_text:
                                combined_context = f"{combined_context}\n\n{enriched_text}".strip()
            except Exception as e:
                logger.debug("query-time enrichment failed: %s", e, exc_info=True)

        answer_error: Optional[str] = None
        try:
            answer = await asyncio.wait_for(
                asyncio.to_thread(
                    generate_rag_answer,
                    question=generation_question,
                    context=combined_context,
                    memory_context=memory_context,
                    summary=summary,
                    episodic_context=episodic_context,
                    history=generation_history,
                ),
                timeout=RAG_ANSWER_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            answer_error = f"answer generation timeout after {RAG_ANSWER_TIMEOUT_S}s"
            answer = f"生成答案超时: {RAG_ANSWER_TIMEOUT_S}s"
        except Exception as e:
            answer_error = f"answer generation failed: {e}"
            answer = f"生成答案失败: {e}"

        aggregated_error = aggregated.error or answer_error
        aggregated = RagRunResult(
            agent_type="rag_executor",
            context=combined_context,
            answer=answer,
            reference=aggregated.reference,
            retrieval_results=aggregated.retrieval_results,
            execution_log=aggregated.execution_log,
            error=aggregated_error,
        )
        return aggregated, list(runs)


def _should_enrich_by_entity_matching(
    *,
    query: str,
    graphrag_context: str,
    extracted_entities: dict[str, Any] | None,
    query_intent: str | None,
    media_type_hint: str | None,
    filters: dict[str, Any] | None,
) -> bool:
    """Conservative fallback: enrich only when GraphRAG likely missed key entities."""
    from infrastructure.enrichment.entity_extractor import EntityExtractor

    if (query_intent or "").strip().lower() == "recommend" and (media_type_hint or "").strip().lower() == "tv":
        # Router-directed path: TV recommendations should use TMDB /discover/tv.
        return True
    if (query_intent or "").strip().lower() == "recommend" and (media_type_hint or "").strip().lower() == "movie":
        # For movies, only do discover when the user gave explicit filter constraints.
        if isinstance(filters, dict) and any(
            k in filters for k in ("year", "origin_country", "original_language", "region", "date_range")
        ):
            return True

    names: list[str] = []
    if isinstance(extracted_entities, dict):
        low = extracted_entities.get("low_level")
        if isinstance(low, list):
            names = [str(x).strip() for x in low if str(x).strip()]

    if not names:
        names = EntityExtractor.extract_movie_entities(query)
    if not names:
        return True

    ctx = (graphrag_context or "").lower()
    for name in names:
        n = name.lower().strip()
        if n and n in ctx:
            return False
    return True

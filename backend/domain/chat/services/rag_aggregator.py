from __future__ import annotations

from typing import Any, Iterable, Optional, Type, TypeVar

from domain.chat.entities.rag_run import RagRunResult

RagRunResultT = TypeVar("RagRunResultT", bound=RagRunResult)
_DEFAULT_SYNTHESIZE_MAX_CHARS = 1500
_DEFAULT_SYNTHESIZE_MAX_EVIDENCE = 3
_DEFAULT_SYNTHESIZE_EVIDENCE_STRATEGY = "score"


def _is_low_quality_answer(answer: Any) -> bool:
    if not isinstance(answer, str):
        return True
    text = answer.strip()
    if not text:
        return True
    if text.startswith(("不知道", "我不知道", "未找到相关信息", "没有找到相关")):
        return True
    return False


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _merge_reference(references: Iterable[Optional[dict[str, Any]]]) -> dict[str, Any]:
    chunks: set[str] = set()
    entities: set[str] = set()
    relationships: set[str] = set()

    for ref in references:
        if not isinstance(ref, dict):
            continue
        for chunk in ref.get("chunks", []) or []:
            if isinstance(chunk, dict) and chunk.get("chunk_id"):
                chunks.add(str(chunk["chunk_id"]))
        for entity in ref.get("entities", []) or []:
            if isinstance(entity, dict) and entity.get("id"):
                entities.add(str(entity["id"]))
        for rel in ref.get("relationships", []) or []:
            if isinstance(rel, dict) and rel.get("id"):
                relationships.add(str(rel["id"]))

    return {
        "chunks": [{"chunk_id": cid} for cid in sorted(chunks)],
        "entities": [{"id": eid} for eid in sorted(entities)],
        "relationships": [{"id": rid} for rid in sorted(relationships)],
    }


def _dedupe_retrieval_results(
    results: Iterable[Optional[list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for group in results:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") or {}
            source_id = str(metadata.get("source_id") or "").strip()
            granularity = str(item.get("granularity") or "").strip()
            if not source_id or not granularity:
                continue

            key = (source_id, granularity)
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue

            try:
                score_new = float(item.get("score", 0.0))
                score_old = float(existing.get("score", 0.0))
            except Exception:
                score_new = 0.0
                score_old = 0.0

            if score_new > score_old:
                merged[key] = item

    deduped = list(merged.values())

    def _score_value(item: dict[str, Any]) -> float:
        try:
            return float(item.get("score", 0.0))
        except Exception:
            return 0.0

    return sorted(deduped, key=_score_value, reverse=True)


def _build_synthesized_answer(
    *,
    merged_context: str,
    merged_retrieval: list[dict[str, Any]],
    max_chars: int,
    max_evidence: int,
    evidence_strategy: str,
) -> str:
    text = (merged_context or "").strip()
    if not text:
        candidates = list(merged_retrieval or [])
        if evidence_strategy == "score":
            candidates = sorted(
                candidates, key=lambda item: _safe_float(item.get("score")), reverse=True
            )
        elif evidence_strategy == "confidence":
            candidates = sorted(
                candidates,
                key=lambda item: _safe_float((item.get("metadata") or {}).get("confidence")),
                reverse=True,
            )

        snippets: list[str] = []
        for item in candidates:
            evidence = item.get("evidence") or item.get("text") or item.get("content")
            if isinstance(evidence, str) and evidence.strip():
                snippets.append(evidence.strip())
            if max_evidence > 0 and len(snippets) >= max_evidence:
                break
        text = "\n\n".join(snippets).strip()

    if not text:
        return ""
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text


def aggregate_run_results(
    *,
    results: list[RagRunResultT],
    preferred_agent_order: Optional[list[str]] = None,
    result_cls: Optional[Type[RagRunResultT]] = None,
    synthesize_max_chars: Optional[int] = None,
    synthesize_max_evidence: Optional[int] = None,
    synthesize_evidence_strategy: Optional[str] = None,
) -> RagRunResultT:
    if result_cls is None:
        result_cls = RagRunResult  # type: ignore[assignment]

    if not results:
        return result_cls(agent_type="unknown", answer="", error="no results")

    order = preferred_agent_order or ["hybrid_agent", "graph_agent", "naive_rag_agent"]
    ranked: list[RagRunResultT] = sorted(
        results,
        key=lambda r: order.index(r.agent_type) if r.agent_type in order else len(order),
    )

    candidates = [c for c in ranked if not c.error]
    chosen = candidates[0] if candidates else ranked[0]
    high_quality = next(
        (c for c in candidates if not _is_low_quality_answer(c.answer)), None
    )
    if high_quality is not None:
        chosen = high_quality

    merged_reference = _merge_reference(r.reference for r in ranked)
    merged_retrieval = _dedupe_retrieval_results(r.retrieval_results for r in ranked)
    merged_context = "\n\n---\n\n".join(
        [
            f"### {r.agent_type}\n\n{(r.context or '').strip()}"
            for r in ranked
            if isinstance(r.context, str) and r.context.strip()
        ]
    ).strip()

    answer = chosen.answer or ""
    max_chars = (
        synthesize_max_chars
        if synthesize_max_chars is not None and synthesize_max_chars > 0
        else _DEFAULT_SYNTHESIZE_MAX_CHARS
    )
    max_evidence = (
        synthesize_max_evidence
        if synthesize_max_evidence is not None and synthesize_max_evidence > 0
        else _DEFAULT_SYNTHESIZE_MAX_EVIDENCE
    )
    strategy = (
        (synthesize_evidence_strategy or _DEFAULT_SYNTHESIZE_EVIDENCE_STRATEGY)
        .strip()
        .lower()
    )
    if strategy not in {"score", "confidence", "first"}:
        strategy = _DEFAULT_SYNTHESIZE_EVIDENCE_STRATEGY

    if _is_low_quality_answer(answer):
        synthesized = _build_synthesized_answer(
            merged_context=merged_context,
            merged_retrieval=merged_retrieval,
            max_chars=max_chars,
            max_evidence=max_evidence,
            evidence_strategy=strategy,
        )
        if synthesized:
            answer = synthesized

    return result_cls(
        agent_type=chosen.agent_type,
        context=merged_context or None,
        answer=answer,
        reference=merged_reference,
        retrieval_results=merged_retrieval,
        execution_log=chosen.execution_log,
        error=chosen.error,
    )


__all__ = ["aggregate_run_results"]

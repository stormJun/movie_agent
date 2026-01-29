from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


from graphrag_agent.config.prompts import LC_SYSTEM_PROMPT, HYBRID_AGENT_GENERATE_PROMPT
from infrastructure.models import get_llm_model, get_stream_llm_model
from infrastructure.observability import (
    get_current_langfuse_stateful_client,
    get_langfuse_callback,
    langfuse_observe,
)

from infrastructure.config.semantics import get_response_type

_GENERAL_SYSTEM_PROMPT = (
    "你是一个有用、谨慎的助手。\n"
    "安全规则：\n"
    "1) 不提供违法、危险、仇恨、暴力、自残等内容。\n"
    "2) 不索取、推断或暴露个人隐私。\n"
    "3) 不编造事实或来源，不确定就说明。\n"
    "4) 对医疗/法律/金融等高风险问题给出一般性信息，并建议咨询专业人士。\n"
    "5) 尊重版权，不提供侵权内容。\n"
    "6) 若用户意图不明确，先澄清问题。\n"
)
_GENERAL_HUMAN_PROMPT = "{question}"

_REWRITE_QUERY_SYSTEM_PROMPT = (
    "你是一个查询改写器（Query Rewriter）。\n"
    "任务：根据【对话历史】与【当前用户问题】，把当前问题改写成一个“自包含”的检索查询。\n"
    "要求：\n"
    "1) 消解指代（它/那个/这部/这位/前者/后者/你刚才说的等），补齐必要上下文。\n"
    "2) 保持原意，不要编造事实；如果历史不足以消解指代，则尽量保留原问题并补充最小上下文提示。\n"
    "3) 只输出改写后的查询文本，不要解释，不要加引号，不要 Markdown。\n"
)

_TMDB_RECO_SELECTOR_SYSTEM_PROMPT = (
    "你是一个“电影推荐选择器”。\n"
    "你将收到用户的推荐需求，以及一组候选电影列表（每个候选都带 tmdb_id）。\n"
    "任务：从候选列表中选出最适合用户需求的 5 部电影，并为每部写 2-3 句简介/推荐理由。\n"
    "严格约束：\n"
    "1) 只能从候选列表里选择；不允许输出候选列表之外的电影。\n"
    "2) 必须输出严格 JSON（不要 Markdown，不要代码块），字段必须为 selected_movies。\n"
    "3) selected_movies 长度固定为 5（不足则尽量补齐到 5）。\n"
    "4) 每个 item 必须包含：tmdb_id（整数）、title、year（整数或 null）、blurb（字符串）。\n"
)


def _coerce_text(value: Any) -> str:
    """Best-effort coercion for optional prompt context fields.

    Upstream integrations should pass strings for memory/summary/episodic context,
    but in practice dict/list payloads can leak through (especially around debug
    plumbing). Prefer degrading to empty text rather than crashing requests.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ("summary", "content", "text"):
            v = value.get(k)
            if isinstance(v, str):
                return v
        return ""
    if isinstance(value, list):
        # Avoid dumping structured objects into the prompt.
        parts: list[str] = []
        for x in value:
            if isinstance(x, str) and x.strip():
                parts.append(x.strip())
        return "\n".join(parts)
    return str(value)


def _preview_text(value: Any, limit: int = 200) -> str:
    text = _coerce_text(value).strip()
    if not text:
        return ""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)] + "…"

def rewrite_multiturn_query(
    *,
    question: str,
    history: list[dict] | None = None,
    max_history_messages: int = 10,
) -> str:
    """Rewrite a multi-turn question into a standalone retrieval query.

    Notes:
    - This is intentionally retrieval-only (we do NOT replace the user-visible question).
    - Best-effort: on any error/empty output, fall back to the original question.
    """
    started_at = time.monotonic()
    q = str(question or "").strip()
    if not q:
        return ""

    # Keep only the last N messages to avoid prompt bloat.
    raw_history = list(history or [])
    if max_history_messages > 0 and len(raw_history) > max_history_messages:
        raw_history = raw_history[-int(max_history_messages) :]

    # Convert dict history to compact "role: content" text. Rewriter needs both
    # user+assistant to resolve pronouns ("它/那个" usually refers to assistant output).
    lines: list[str] = []
    for m in raw_history:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip()
        if role not in {"user", "assistant"}:
            continue
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    history_text = "\n".join(lines).strip()

    # If we have no usable history, rewriting is pointless.
    if not history_text:
        return q

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _REWRITE_QUERY_SYSTEM_PROMPT),
            (
                "human",
                "【对话历史】\n{history}\n\n【当前用户问题】\n{question}\n\n输出改写后的检索查询：",
            ),
        ]
    )
    llm = get_llm_model()
    chain = prompt | llm | StrOutputParser()

    parent = get_current_langfuse_stateful_client()
    span = None
    if parent is not None:
        span = parent.span(
            name="rewrite_multiturn_query",
            input={
                "question_preview": _preview_text(q),
                "history_lines": len(lines),
            },
        )

    langfuse_handler = get_langfuse_callback(stateful_client=span or parent)
    callbacks = [langfuse_handler] if langfuse_handler else []

    try:
        rewritten = chain.invoke(
            {"history": history_text, "question": q},
            config={"callbacks": callbacks},
        )
    except Exception as e:
        if span is not None:
            span.end(level="ERROR", status_message=str(e), output={"error": str(e)})
        return q

    out = str(rewritten or "").strip()
    # Defensive cleanup: avoid LLM returning quotes or code fences.
    out = out.strip().strip('"').strip("'").strip("`").strip()
    if not out:
        return q

    if span is not None:
        span.end(
            output={"rewritten_preview": _preview_text(out), "rewritten_chars": len(out)},
            metadata={"elapsed_ms": int((time.monotonic() - started_at) * 1000)},
        )
    return out


def _safe_json_extract(text: str) -> dict[str, Any] | None:
    """Best-effort parse a JSON object from LLM output."""
    if not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None
    # Remove common wrappers (code fences / quotes).
    s = s.strip().strip("`").strip()
    if s.startswith("```"):
        # Keep the inside of the fence if present.
        parts = s.split("```")
        if len(parts) >= 3:
            s = parts[1].strip()
    s = s.strip().strip('"').strip("'").strip()

    # Try direct JSON first.
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # Fallback: attempt to extract the first {...} block.
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(s[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def _normalize_tmdb_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a TMDB candidate movie into a compact dict used by the selector."""
    if not isinstance(candidate, dict):
        return None
    tid = candidate.get("tmdb_id")
    try:
        tmdb_id = int(tid)
    except Exception:
        return None
    title = candidate.get("title") or candidate.get("name") or ""
    title = str(title).strip()
    if not title:
        return None
    year = candidate.get("year")
    if year is None:
        rd = candidate.get("release_date") or ""
        if isinstance(rd, str) and len(rd) >= 4 and rd[:4].isdigit():
            year = int(rd[:4])
    if isinstance(year, str) and year.isdigit():
        year = int(year)
    if not isinstance(year, int):
        year = None

    overview = str(candidate.get("overview") or "").strip()
    vote_average = candidate.get("vote_average")
    if not isinstance(vote_average, (int, float)):
        vote_average = None
    genres = candidate.get("genres")
    genre_names: list[str] = []
    if isinstance(genres, list):
        for g in genres:
            if isinstance(g, dict) and isinstance(g.get("name"), str) and g["name"].strip():
                genre_names.append(g["name"].strip())
            elif isinstance(g, str) and g.strip():
                genre_names.append(g.strip())

    directors = candidate.get("directors")
    director_names: list[str] = []
    if isinstance(directors, list):
        for d in directors:
            if isinstance(d, str) and d.strip():
                director_names.append(d.strip())

    return {
        "tmdb_id": tmdb_id,
        "title": title,
        "year": year,
        "overview": overview,
        "vote_average": float(vote_average) if isinstance(vote_average, (int, float)) else None,
        "genres": genre_names,
        "directors": director_names,
    }


async def select_tmdb_recommendation_movies(
    *,
    question: str,
    candidates: list[dict[str, Any]],
    k: int = 5,
) -> list[dict[str, Any]]:
    """Select k movies from TMDB candidates and generate blurbs (strict ids only).

    Returns a list of normalized dicts:
      {"tmdb_id": int, "title": str, "year": int|None, "blurb": str}

    Best-effort:
    - On any failure, fall back to first k candidates with template blurbs.
    """
    q = str(question or "").strip()
    if not q:
        return []

    normalized: list[dict[str, Any]] = []
    for c in candidates or []:
        nc = _normalize_tmdb_candidate(c)
        if nc is not None:
            normalized.append(nc)

    if not normalized:
        return []

    k = int(k) if isinstance(k, int) and k > 0 else 5
    # Keep the prompt small and deterministic.
    pool = normalized[: max(10, min(len(normalized), 20))]
    allowed_ids = {int(x["tmdb_id"]) for x in pool if isinstance(x.get("tmdb_id"), int)}
    by_id = {int(x["tmdb_id"]): x for x in pool if isinstance(x.get("tmdb_id"), int)}

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _TMDB_RECO_SELECTOR_SYSTEM_PROMPT),
            (
                "human",
                "【用户需求】\n{question}\n\n"
                "【候选电影（只能从这里选）】\n{candidates}\n\n"
                "输出 JSON：",
            ),
        ]
    )
    llm = get_llm_model()
    chain = prompt | llm | StrOutputParser()

    candidates_text = json.dumps(pool, ensure_ascii=False)

    parent = get_current_langfuse_stateful_client()
    span = None
    if parent is not None:
        span = parent.span(
            name="select_tmdb_recommendation_movies",
            input={"question_preview": _preview_text(q), "candidates_count": len(pool)},
        )
    langfuse_handler = get_langfuse_callback(stateful_client=span or parent)
    callbacks = [langfuse_handler] if langfuse_handler else []

    raw_text: str | None = None
    try:
        raw_text = await chain.ainvoke(
            {"question": q, "candidates": candidates_text},
            config={"callbacks": callbacks},
        )
    except Exception as e:
        if span is not None:
            span.end(level="ERROR", status_message=str(e), output={"error": str(e)})
        raw_text = None

    obj = _safe_json_extract(str(raw_text or ""))
    selected: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        sm = obj.get("selected_movies")
        if isinstance(sm, list):
            selected = [x for x in sm if isinstance(x, dict)]

    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in selected:
        tid = item.get("tmdb_id")
        try:
            tmdb_id = int(tid)
        except Exception:
            continue
        if tmdb_id not in allowed_ids or tmdb_id in seen:
            continue
        seen.add(tmdb_id)
        base = by_id.get(tmdb_id, {})
        title = item.get("title") if isinstance(item.get("title"), str) and item["title"].strip() else base.get("title")
        title = str(title or "").strip()
        year = item.get("year")
        if isinstance(year, str) and year.isdigit():
            year = int(year)
        if not isinstance(year, int):
            year = base.get("year")
        if not isinstance(year, int):
            year = None
        blurb = item.get("blurb") if isinstance(item.get("blurb"), str) else ""
        blurb = blurb.strip()
        if not blurb:
            ov = str(base.get("overview") or "").strip()
            blurb = ov[:160] + ("…" if len(ov) > 160 else "")
        out.append({"tmdb_id": tmdb_id, "title": title, "year": year, "blurb": blurb})
        if len(out) >= k:
            break

    # Fallback: top-k from pool.
    if len(out) < k:
        for c in pool:
            tmdb_id = int(c["tmdb_id"])
            if tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            ov = str(c.get("overview") or "").strip()
            blurb = ov[:160] + ("…" if len(ov) > 160 else "")
            out.append({"tmdb_id": tmdb_id, "title": c["title"], "year": c.get("year"), "blurb": blurb})
            if len(out) >= k:
                break

    if span is not None:
        span.end(output={"selected_count": len(out), "ids": [x["tmdb_id"] for x in out]})
    return out



def _convert_history_to_messages(history: list[dict] | None) -> list[BaseMessage]:
    """Convert raw dict history to LangChain messages."""
    if not history:
        return []
    messages = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def _build_general_prompt(*, with_memory: bool, with_history: bool) -> ChatPromptTemplate:
    # Use system blocks for memory/summary to avoid treating them as user content.
    msgs = [("system", _GENERAL_SYSTEM_PROMPT)]
    if with_memory:
        msgs.append(("system", "{memory_context}"))
    # Phase 1: conversation summary (optional)
    msgs.append(("system", "{conversation_summary}"))  # safe even when empty
    # Phase 2: episodic memory context (optional)
    msgs.append(("system", "{episodic_context}"))  # safe even when empty
    if with_history:
        msgs.append(MessagesPlaceholder(variable_name="history"))
    msgs.append(("human", "{question}"))
    
    return ChatPromptTemplate.from_messages(msgs)


def _build_rag_prompt(with_history: bool = False) -> ChatPromptTemplate:
    msgs = [("system", LC_SYSTEM_PROMPT)]
    # Keep memory/summary as system blocks to avoid treating them as user content.
    msgs.append(("system", "{memory_context}"))  # safe even when empty
    msgs.append(("system", "{conversation_summary}"))  # safe even when empty
    msgs.append(("system", "{episodic_context}"))  # safe even when empty
    if with_history:
        msgs.append(MessagesPlaceholder(variable_name="history"))
    msgs.append(("human", HYBRID_AGENT_GENERATE_PROMPT))
    
    return ChatPromptTemplate.from_messages(msgs)


@langfuse_observe(name="generate_general_answer")
def generate_general_answer(
    *,
    question: str,
    memory_context: str | None = None,
    summary: str | None = None,
    episodic_context: str | None = None,
    history: list[dict] | None = None,
) -> str:
    started_at = time.monotonic()
    memory_text = _coerce_text(memory_context).strip()
    with_memory = bool(memory_text)
    summary_text = _coerce_text(summary).strip()
    chat_history = _convert_history_to_messages(history)
    with_history = bool(chat_history)
    
    prompt = _build_general_prompt(with_memory=with_memory, with_history=with_history)
    llm = get_llm_model()
    chain = prompt | llm | StrOutputParser()
    payload = {
        "question": question,
        "conversation_summary": summary_text,
        "episodic_context": _coerce_text(episodic_context).strip(),
    }
    if with_memory:
        payload["memory_context"] = memory_text
    if with_history:
        payload["history"] = chat_history

    parent = get_current_langfuse_stateful_client()
    span = None
    if parent is not None:
        span = parent.span(
            name="generate_general_answer",
            input={
                "question_preview": _preview_text(question),
                "with_memory": with_memory,
                "with_history": with_history,
                "history_len": len(chat_history),
                "has_summary": bool(summary_text),
                "has_episodic": bool(_coerce_text(episodic_context).strip()),
            },
        )
        
    # Bind LangChain callbacks to the existing trace/span to avoid trace splitting.
    langfuse_handler = get_langfuse_callback(stateful_client=span or parent)
    callbacks = [langfuse_handler] if langfuse_handler else []
    
    error_message: str | None = None
    try:
        result = chain.invoke(payload, config={"callbacks": callbacks})
    except Exception as e:
        if span is not None:
            span.end(level="ERROR", status_message=str(e), output={"error": str(e)})
        raise
    else:
        if span is not None:
            span.end(
                output={"answer_chars": len(str(result or ""))},
                metadata={"elapsed_ms": int((time.monotonic() - started_at) * 1000)},
            )
        return result


@langfuse_observe(name="generate_general_answer_stream")
async def generate_general_answer_stream(
    *,
    question: str,
    memory_context: str | None = None,
    summary: str | None = None,
    episodic_context: str | None = None,
    history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    started_at = time.monotonic()
    memory_text = _coerce_text(memory_context).strip()
    with_memory = bool(memory_text)
    summary_text = _coerce_text(summary).strip()
    chat_history = _convert_history_to_messages(history)
    with_history = bool(chat_history)

    prompt = _build_general_prompt(with_memory=with_memory, with_history=with_history)
    llm = get_stream_llm_model()
    chain = prompt | llm | StrOutputParser()
    payload = {
        "question": question,
        "conversation_summary": summary_text,
        "episodic_context": _coerce_text(episodic_context).strip(),
    }
    if with_memory:
        payload["memory_context"] = memory_text
    if with_history:
        payload["history"] = chat_history

    parent = get_current_langfuse_stateful_client()
    span = None
    if parent is not None:
        span = parent.span(
            name="generate_general_answer_stream",
            input={
                "question_preview": _preview_text(question),
                "with_memory": with_memory,
                "with_history": with_history,
                "history_len": len(chat_history),
                "has_summary": bool(summary_text),
                "has_episodic": bool(_coerce_text(episodic_context).strip()),
            },
        )
        
    langfuse_handler = get_langfuse_callback(stateful_client=span or parent)
    callbacks = [langfuse_handler] if langfuse_handler else []

    # Phase 3: prefer astream_events so we can later surface structured events if needed.
    first_token_at: float | None = None
    chunk_count = 0
    generated_chars = 0
    error_message: str | None = None
    try:
        if hasattr(chain, "astream_events"):
            async for event in chain.astream_events(payload, version="v1", config={"callbacks": callbacks}):
                if not isinstance(event, dict):
                    continue
                if event.get("event") != "on_parser_stream":
                    continue
                data = event.get("data") or {}
                chunk = data.get("chunk")
                if not chunk:
                    continue
                if first_token_at is None:
                    first_token_at = time.monotonic()
                chunk_str = str(chunk)
                chunk_count += 1
                generated_chars += len(chunk_str)
                yield chunk_str
            return

        async for chunk in chain.astream(payload, config={"callbacks": callbacks}):
            if not chunk:
                continue
            if first_token_at is None:
                first_token_at = time.monotonic()
            chunk_str = str(chunk)
            chunk_count += 1
            generated_chars += len(chunk_str)
            yield chunk_str
    except Exception as e:
        error_message = str(e)
        raise
    finally:
        if span is not None:
            ttft_ms = None
            if first_token_at is not None:
                ttft_ms = int((first_token_at - started_at) * 1000)
            level = "ERROR" if error_message else None
            span.end(
                level=level,  # type: ignore[arg-type]
                status_message=error_message,
                output={"generated_chars": generated_chars, "chunk_count": chunk_count},
                metadata={
                    "elapsed_ms": int((time.monotonic() - started_at) * 1000),
                    "ttft_ms": ttft_ms,
                },
            )


@langfuse_observe(name="generate_rag_answer")
def generate_rag_answer(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    summary: str | None = None,
    episodic_context: str | None = None,
    response_type: str | None = None,
    history: list[dict] | None = None,
) -> str:
    started_at = time.monotonic()
    chat_history = _convert_history_to_messages(history)
    with_history = bool(chat_history)
    summary_text = _coerce_text(summary).strip()
    memory_text = _coerce_text(memory_context).strip()

    prompt = _build_rag_prompt(with_history=with_history)
    llm = get_llm_model()
    chain = prompt | llm | StrOutputParser()
        
    payload = {
        "context": context,
        "question": question,
        "response_type": response_type or get_response_type(),
        "conversation_summary": summary_text,
        "memory_context": memory_text,
        "episodic_context": _coerce_text(episodic_context).strip(),
    }
    if with_history:
        payload["history"] = chat_history
    
    parent = get_current_langfuse_stateful_client()
    span = None
    if parent is not None:
        span = parent.span(
            name="generate_rag_answer",
            input={
                "question_preview": _preview_text(question),
                "context_chars": len(context or ""),
                "with_history": with_history,
                "history_len": len(chat_history),
                "response_type": response_type or get_response_type(),
                "has_summary": bool(summary_text),
                "has_memory": bool(memory_text),
                "has_episodic": bool(_coerce_text(episodic_context).strip()),
            },
        )

    langfuse_handler = get_langfuse_callback(stateful_client=span or parent)
    callbacks = [langfuse_handler] if langfuse_handler else []

    try:
        result = chain.invoke(payload, config={"callbacks": callbacks})
    except Exception as e:
        if span is not None:
            span.end(level="ERROR", status_message=str(e), output={"error": str(e)})
        raise
    else:
        if span is not None:
            span.end(
                output={"answer_chars": len(str(result or ""))},
                metadata={"elapsed_ms": int((time.monotonic() - started_at) * 1000)},
            )
        return result


@langfuse_observe(name="generate_rag_answer_stream")
async def generate_rag_answer_stream(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    summary: str | None = None,
    episodic_context: str | None = None,
    response_type: str | None = None,
    history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    started_at = time.monotonic()
    chat_history = _convert_history_to_messages(history)
    with_history = bool(chat_history)
    summary_text = _coerce_text(summary).strip()
    memory_text = _coerce_text(memory_context).strip()

    prompt = _build_rag_prompt(with_history=with_history)
    llm = get_stream_llm_model()
    chain = prompt | llm | StrOutputParser()
    payload = {
        "context": context,
        "question": question,
        "response_type": response_type or get_response_type(),
        "conversation_summary": summary_text,
        "memory_context": memory_text,
        "episodic_context": _coerce_text(episodic_context).strip(),
    }
    if with_history:
        payload["history"] = chat_history
    
    parent = get_current_langfuse_stateful_client()
    span = None
    if parent is not None:
        span = parent.span(
            name="generate_rag_answer_stream",
            input={
                "question_preview": _preview_text(question),
                "context_chars": len(context or ""),
                "with_history": with_history,
                "history_len": len(chat_history),
                "response_type": response_type or get_response_type(),
                "has_summary": bool(summary_text),
                "has_memory": bool(memory_text),
                "has_episodic": bool(_coerce_text(episodic_context).strip()),
            },
        )

    langfuse_handler = get_langfuse_callback(stateful_client=span or parent)
    callbacks = [langfuse_handler] if langfuse_handler else []

    # Phase 3: prefer astream_events so we can later surface structured events if needed.
    first_token_at: float | None = None
    chunk_count = 0
    generated_chars = 0
    error_message: str | None = None
    try:
        if hasattr(chain, "astream_events"):
            async for event in chain.astream_events(payload, version="v1", config={"callbacks": callbacks}):
                if not isinstance(event, dict):
                    continue
                if event.get("event") != "on_parser_stream":
                    continue
                data = event.get("data") or {}
                chunk = data.get("chunk")
                if not chunk:
                    continue
                if first_token_at is None:
                    first_token_at = time.monotonic()
                chunk_str = str(chunk)
                chunk_count += 1
                generated_chars += len(chunk_str)
                yield chunk_str
            return

        async for chunk in chain.astream(payload, config={"callbacks": callbacks}):
            if not chunk:
                continue
            if first_token_at is None:
                first_token_at = time.monotonic()
            chunk_str = str(chunk)
            chunk_count += 1
            generated_chars += len(chunk_str)
            yield chunk_str
    except Exception as e:
        error_message = str(e)
        raise
    finally:
        if span is not None:
            ttft_ms = None
            if first_token_at is not None:
                ttft_ms = int((first_token_at - started_at) * 1000)
            level = "ERROR" if error_message else None
            span.end(
                level=level,  # type: ignore[arg-type]
                status_message=error_message,
                output={"generated_chars": generated_chars, "chunk_count": chunk_count},
                metadata={
                    "elapsed_ms": int((time.monotonic() - started_at) * 1000),
                    "ttft_ms": ttft_ms,
                },
            )

from __future__ import annotations

import time
from typing import AsyncGenerator

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


def _preview_text(value: str | None, limit: int = 200) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)] + "…"



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
    human = "{question}"
    if with_memory:
        human = "{memory_context}\n\n{question}"
    
    msgs = [("system", _GENERAL_SYSTEM_PROMPT)]
    if with_history:
        msgs.append(MessagesPlaceholder(variable_name="history"))
    msgs.append(("human", human))
    
    return ChatPromptTemplate.from_messages(msgs)


def _build_rag_prompt(with_history: bool = False) -> ChatPromptTemplate:
    msgs = [("system", LC_SYSTEM_PROMPT)]
    if with_history:
        msgs.append(MessagesPlaceholder(variable_name="history"))
    msgs.append(("human", HYBRID_AGENT_GENERATE_PROMPT))
    
    return ChatPromptTemplate.from_messages(msgs)


@langfuse_observe(name="generate_general_answer")
def generate_general_answer(
    *,
    question: str,
    memory_context: str | None = None,
    history: list[dict] | None = None,
) -> str:
    started_at = time.monotonic()
    with_memory = bool((memory_context or "").strip())
    chat_history = _convert_history_to_messages(history)
    with_history = bool(chat_history)
    
    prompt = _build_general_prompt(with_memory=with_memory, with_history=with_history)
    llm = get_llm_model()
    chain = prompt | llm | StrOutputParser()
    payload = {"question": question}
    if with_memory:
        payload["memory_context"] = memory_context
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
    history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    started_at = time.monotonic()
    with_memory = bool((memory_context or "").strip())
    chat_history = _convert_history_to_messages(history)
    with_history = bool(chat_history)

    prompt = _build_general_prompt(with_memory=with_memory, with_history=with_history)
    llm = get_stream_llm_model()
    chain = prompt | llm | StrOutputParser()
    payload = {"question": question}
    if with_memory:
        payload["memory_context"] = memory_context
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
            },
        )
        
    langfuse_handler = get_langfuse_callback(stateful_client=span or parent)
    callbacks = [langfuse_handler] if langfuse_handler else []

    # Phase 3: prefer astream_events so we can later surface structured events if needed.
    first_token_at: float | None = None
    chunk_count = 0
    generated_chars = 0
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
    response_type: str | None = None,
    history: list[dict] | None = None,
) -> str:
    started_at = time.monotonic()
    chat_history = _convert_history_to_messages(history)
    with_history = bool(chat_history)

    prompt = _build_rag_prompt(with_history=with_history)
    llm = get_llm_model()
    chain = prompt | llm | StrOutputParser()
    if (memory_context or "").strip():
        context = f"{memory_context}\n\n{context}"
        
    payload = {
        "context": context,
        "question": question,
        "response_type": response_type or get_response_type(),
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
    response_type: str | None = None,
    history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    started_at = time.monotonic()
    chat_history = _convert_history_to_messages(history)
    with_history = bool(chat_history)

    prompt = _build_rag_prompt(with_history=with_history)
    llm = get_stream_llm_model()
    chain = prompt | llm | StrOutputParser()
    if (memory_context or "").strip():
        context = f"{memory_context}\n\n{context}"
    payload = {
        "context": context,
        "question": question,
        "response_type": response_type or get_response_type(),
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

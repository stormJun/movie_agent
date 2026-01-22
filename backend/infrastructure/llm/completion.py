from __future__ import annotations

from typing import AsyncGenerator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from graphrag_agent.config.prompts import LC_SYSTEM_PROMPT, HYBRID_AGENT_GENERATE_PROMPT
from infrastructure.models import get_llm_model, get_stream_llm_model

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


def _build_general_prompt(*, with_memory: bool) -> ChatPromptTemplate:
    human = "{question}"
    if with_memory:
        human = "{memory_context}\n\n{question}"
    return ChatPromptTemplate.from_messages(
        [
            ("system", _GENERAL_SYSTEM_PROMPT),
            ("human", human),
        ]
    )


def _build_rag_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", LC_SYSTEM_PROMPT),
            ("human", HYBRID_AGENT_GENERATE_PROMPT),
        ]
    )


def generate_general_answer(*, question: str, memory_context: str | None = None) -> str:
    with_memory = bool((memory_context or "").strip())
    prompt = _build_general_prompt(with_memory=with_memory)
    llm = get_llm_model()
    chain = prompt | llm | StrOutputParser()
    payload = {"question": question}
    if with_memory:
        payload["memory_context"] = memory_context
    return chain.invoke(payload)


async def generate_general_answer_stream(
    *,
    question: str,
    memory_context: str | None = None,
) -> AsyncGenerator[str, None]:
    with_memory = bool((memory_context or "").strip())
    prompt = _build_general_prompt(with_memory=with_memory)
    llm = get_stream_llm_model()
    chain = prompt | llm | StrOutputParser()
    payload = {"question": question}
    if with_memory:
        payload["memory_context"] = memory_context
    # Phase 3: prefer astream_events so we can later surface structured events if needed.
    if hasattr(chain, "astream_events"):
        async for event in chain.astream_events(payload, version="v1"):
            if not isinstance(event, dict):
                continue
            if event.get("event") != "on_parser_stream":
                continue
            data = event.get("data") or {}
            chunk = data.get("chunk")
            if chunk:
                yield str(chunk)
        return

    async for chunk in chain.astream(payload):
        if chunk:
            yield str(chunk)


def generate_rag_answer(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    response_type: str | None = None,
) -> str:
    prompt = _build_rag_prompt()
    llm = get_llm_model()
    chain = prompt | llm | StrOutputParser()
    if (memory_context or "").strip():
        context = f"{memory_context}\n\n{context}"
    return chain.invoke(
        {
            "context": context,
            "question": question,
            "response_type": response_type or get_response_type(),
        }
    )


async def generate_rag_answer_stream(
    *,
    question: str,
    context: str,
    memory_context: str | None = None,
    response_type: str | None = None,
) -> AsyncGenerator[str, None]:
    prompt = _build_rag_prompt()
    llm = get_stream_llm_model()
    chain = prompt | llm | StrOutputParser()
    if (memory_context or "").strip():
        context = f"{memory_context}\n\n{context}"
    payload = {
        "context": context,
        "question": question,
        "response_type": response_type or get_response_type(),
    }

    # Phase 3: prefer astream_events so we can later surface structured events if needed.
    if hasattr(chain, "astream_events"):
        async for event in chain.astream_events(payload, version="v1"):
            if not isinstance(event, dict):
                continue
            if event.get("event") != "on_parser_stream":
                continue
            data = event.get("data") or {}
            chunk = data.get("chunk")
            if chunk:
                yield str(chunk)
        return

    async for chunk in chain.astream(payload):
        if chunk:
            yield str(chunk)

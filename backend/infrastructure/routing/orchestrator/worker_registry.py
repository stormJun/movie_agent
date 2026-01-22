from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedWorkerName:
    kb_prefix: str
    agent_type: str
    agent_mode: str


def parse_worker_name(worker_name: str) -> ParsedWorkerName:
    raw = (worker_name or "").strip()
    if not raw:
        return ParsedWorkerName(kb_prefix="", agent_type="", agent_mode="retrieve_only")

    parts = [p.strip() for p in raw.split(":") if p is not None]
    if len(parts) == 1:
        # Historical/compat: "<agent_type>"
        return ParsedWorkerName(kb_prefix="", agent_type=parts[0], agent_mode="retrieve_only")
    if len(parts) == 2:
        # Compat: "{kb_prefix}:{agent_type}"
        kb_prefix, agent_type = parts
        return ParsedWorkerName(kb_prefix=kb_prefix, agent_type=agent_type, agent_mode="retrieve_only")
    if len(parts) == 3:
        kb_prefix, agent_type, agent_mode = parts
        agent_mode = agent_mode or "retrieve_only"
        if agent_mode != "retrieve_only":
            raise ValueError(f"unsupported agent_mode in worker_name: {worker_name}")
        return ParsedWorkerName(kb_prefix=kb_prefix, agent_type=agent_type, agent_mode=agent_mode)

    raise ValueError(f"invalid worker_name format: {worker_name}")


def get_agent_for_worker_name(
    *, worker_name: str, session_id: str, agent_mode: str | None = None
):
    parsed = parse_worker_name(worker_name)

    kb_prefix = parsed.kb_prefix
    if kb_prefix == "default":
        # Historical placeholder. RouterGraph no longer emits it; treat any
        # remaining usage as a config/compat bug and force callers to fix it.
        raise ValueError(
            "kb_prefix='default' in worker_name is no longer supported. "
            "Use kb_prefix='general' for no-retrieval, or specify a real kb_prefix "
            "(e.g. 'movie'/'edu')."
        )

    from infrastructure.agents.rag_factory import rag_agent_manager as agent_manager

    return agent_manager.get_agent(
        parsed.agent_type,
        session_id=session_id,
        kb_prefix=kb_prefix,
        # Keep explicit argument for callers, but default to parsed mode.
        agent_mode=(agent_mode or parsed.agent_mode),
    )

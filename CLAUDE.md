# CLAUDE.md

Guidance for Claude Code when working in this repo.

Primary rules live in `AGENTS.md` (structure, testing, data handling). If this file conflicts with `AGENTS.md`, follow `AGENTS.md`.

## Repo Map (High Level)

- Backend (all backend code): `backend/`
  - FastAPI service: `backend/server/`
  - GraphRAG core runtime (agents/graph/search/ports): `backend/graphrag_agent/`
  - Integrations/pipelines/providers: `backend/infrastructure/`
- Frontend (React/Vite): `frontend-react/`
- Docker compose assets: `docker/`
- Tests: `test/`
- Inputs: `datasets/`, `documents/`
- Generated artifacts: `files/` (should not be committed in normal workflows)

## Common Commands

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Start dependencies (Neo4j + Postgres):
```bash
docker compose -f docker/docker-compose.yaml up -d
```

Start dev servers:
```bash
bash scripts/dev.sh backend
bash scripts/dev.sh frontend
```

Run tests:
```bash
bash scripts/test.sh
```

Run graph build pipeline:
```bash
bash scripts/py.sh infrastructure.integrations.build.main --help
bash scripts/py.sh infrastructure.integrations.build.main
```

Incremental update:
```bash
bash scripts/py.sh infrastructure.integrations.build.incremental_update --once
```

## Working On Agents

- Core agent code: `backend/graphrag_agent/agents/` (see `backend/graphrag_agent/agents/base.py`).
- Multi-agent orchestration: `backend/graphrag_agent/agents/multi_agent/` (planner/executor/reporter).
- Tool registry: `backend/graphrag_agent/search/tool_registry.py`.
- API wiring/factories typically live in `backend/infrastructure/agents/` and `backend/server/`.

Keep agents stateless (no conversation/memory stored inside core agents). Prefer retrieve-only, structured evidence outputs; service layer owns formatting/generation.

## Guardrails

- Do not add backend code outside `backend/`.
- Do not commit secrets (`.env`, API keys) or large runtime artifacts (`files/`, caches).
- Keep docs/commands consistent with repo wrappers (`bash scripts/test.sh`, `bash scripts/py.sh ...`).


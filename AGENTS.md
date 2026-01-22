# Repository Guidelines

## Project Structure & Module Organization
Hard rule: all backend code must live under `backend/` (no `server/`, `application/`, `domain/`, `infrastructure/`, `graphrag_agent/` at repo root). Core runtime sits in `backend/graphrag_agent/`: `agents/` implements GraphRAG agents (multi-agent flows under `multi_agent/`), and `graph/` owns the core ingestion primitives. Build/ingestion pipelines live under `backend/infrastructure/integrations/` and `backend/infrastructure/pipelines/`. The FastAPI backend lives in `backend/server/`; the React UI in `frontend-react/`. Tests and evaluation scripts reside in `test/`. Data inputs (`datasets/`, `documents/`) and generated artifacts (`files/`) stay separated—do not mix sources and outputs.

Docker assets live under `docker/` (e.g. `docker/docker-compose.yaml`, `docker/docker-compose.mem0.yaml`).

## Agent System (GraphRAG Core)

### Where Agent Code Lives
- Core agents: `backend/graphrag_agent/agents/`
- Multi-agent orchestration (Plan-Execute-Report): `backend/graphrag_agent/agents/multi_agent/`
- Search tools registry: `backend/graphrag_agent/search/tool_registry.py`
- Community detection (GDS-based): `backend/graphrag_agent/community/`
- Service wiring (factories, providers, API integration): `backend/infrastructure/agents/`, `backend/server/`

### BaseAgent Contract (Core)
- Base class: `backend/graphrag_agent/agents/base.py`
- Agents should be stateless: do not store chat history or long-term memory inside core agents (service side owns conversation/memory).
- Prefer retrieve-only behavior for tools/agents when configured: return structured evidence (sources + snippets + metadata), then let the service decide how to format/generate.
- Streaming: token streaming is generation-time; retrieval typically completes first, then the model streams tokens (progress events may be emitted during retrieval).

### Built-in Agents (Typical Use)
- `NaiveRagAgent`: vector-only retrieval for simple Q&A.
- `GraphAgent`: graph-centric retrieval/reasoning for relationship-heavy queries.
- `HybridAgent`: combines vector retrieval + graph expansion + community context.
- `DeepResearchAgent`: multi-step evidence gathering (think-search-reason) for complex queries.
- `FusionAgent`: multi-agent orchestration / comprehensive responses.

### Multi-Agent (Plan-Execute-Report) Layout
- Planner: `backend/graphrag_agent/agents/multi_agent/planner/` (clarify, decompose, review plan)
- Executor: `backend/graphrag_agent/agents/multi_agent/executor/` (dispatch retrieval/research work; optional reflection)
- Reporter: `backend/graphrag_agent/agents/multi_agent/reporter/` (outline/sections; optional map-reduce; consistency checks)
- Core models: `backend/graphrag_agent/agents/multi_agent/core/` (`PlanSpec`, `State`, `ExecutionRecord`, `RetrievalResult`)

### Adding/Modifying an Agent (Checklist)
- Implement/extend under `backend/graphrag_agent/agents/` (follow `BaseAgent` patterns).
- Register/compose tools via `backend/graphrag_agent/search/tool_registry.py` (avoid eager imports of optional deps; keep lazy-import error hints intact).
- If the agent must be selectable via API, wire it through `backend/infrastructure/agents/` (factory/registry) and expose it via `backend/server/` routes as needed.
- Add tests under `test/`:
  - import/lazy-import guardrails (e.g. `test/test_agents_import_hints.py`)
  - behavior/contract tests for retrieve-only or streaming where relevant
  - run `bash scripts/test.sh` before pushing changes

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` creates an isolated Python 3.10+ environment.
- `pip install -r requirements.txt` installs runtime and evaluation deps; install the OS packages noted in the file for DOC/PDF support.
- `bash scripts/dev.sh backend` starts the FastAPI service (uvicorn + reload); it consumes `.env` variables for Neo4j and LLM access.
- `bash scripts/dev.sh frontend` starts the React UI (Vite).
- `docker compose -f docker/docker-compose.yaml up -d` starts local Neo4j + Postgres dependencies.
- `bash scripts/py.sh infrastructure.integrations.build.main --help` shows build pipeline help (docs should not hand-write `PYTHONPATH=backend ...` variants).
- `bash scripts/test.sh` runs the default regression suite prior to any PR.

## Coding Style & Naming Conventions
Adhere to PEP 8: 4-space indentation, `snake_case` modules and functions, `PascalCase` classes, and upper-snake constants. Public methods should carry type hints and concise docstrings. Keep prompt templates readable and avoid trailing-space churn. Format locally with `black` and `isort` (no repo config, but matching their defaults keeps diffs clean).

## Testing Guidelines
Tests rely on `unittest` scripts in `test/`. Name new cases `test_{feature}.py` and mirror the package layout so discovery works. Run the suite with `bash scripts/test.sh`; exercise targeted flows via `bash scripts/ut.sh ...` (e.g., `bash scripts/ut.sh test.test_deep_agent -v`). Document any external prerequisites (Neo4j, API keys, cached embeddings) in your PR and offer fallbacks or skips when they are unavailable.

Prefer the wrappers to keep docs/CI stable:
- default suite: `bash scripts/test.sh`
- custom unittest args: `bash scripts/ut.sh ...`

## Commit & Pull Request Guidelines
Follow the short, imperative commit style in history (`add multi-agent config`, `unify configs`). Scope each logical change to one commit and use optional prefixes (`agents:`) when clarifying impact. PRs should include: summary, linked issue/TODO, test results, and configuration changes. Attach screenshots for `frontend-react/` changes and describe migration steps for datasets, caches, or graph indexes.

## Configuration & Data Handling
Clone `.env.example` when adding settings; never commit secrets. When introducing new knobs/services, update `.env.example` and the relevant docs (typically `readme.md` and/or `docs/`). Keep raw corpora in `documents/` or `datasets/`; persist generated artifacts under `files/` and avoid adding them to git. Note required ports or Docker services in `docker/docker-compose.yaml` for reviewers.

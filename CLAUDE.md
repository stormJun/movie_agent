# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a GraphRAG + Deep Search implementation with multi-agent collaboration system. The project combines knowledge graph construction, entity disambiguation, community detection, and multiple agent types (NaiveRAG, GraphAgent, HybridAgent, DeepResearchAgent, FusionGraphRAGAgent) to build an explainable and reasoning-capable Q&A system.

**Language**: Primarily Chinese (comments, docs, UI) with English code structures.

**Hard Rule**: All backend code lives under `backend/` directory. No backend code at repo root.

## Architecture

### Layered Architecture

The project follows a clean architecture pattern with clear layer boundaries:

**Core Package** (`backend/graphrag_agent/`):
- **agents/**: Agent implementations with Plan-Execute-Report multi-agent orchestration
  - All agents inherit from `base.py` (BaseAgent with LangGraph integration)
  - `multi_agent/`: Plan-Execute-Report architecture (planner → executor → reporter)
- **graph/**: Knowledge graph construction (extraction, processing, indexing)
- **search/**: Multi-level search strategies (local/global/hybrid)
- **community/**: Graph community detection (Leiden, SLLPA) and summarization
- **config/**: Core defaults and type definitions (DO NOT modify directly for business needs)
- **ports/**: Abstract interfaces for models, cache, database (dependency inversion)

**Infrastructure Layer** (`backend/infrastructure/`):
- Provides concrete implementations of ports (models, Neo4j, cache, vector stores)
- `config/`: Reads `.env` and injects runtime configuration into core
- `integrations/build/`: Graph construction orchestration pipelines
- `pipelines/ingestion/`: Multi-format document processors (TXT, PDF, MD, DOCX, DOC, CSV, JSON, YAML)
- `rag/`, `routing/`, `agents/`, `streaming/`: Runtime execution components
- Bootstrap entry point: `backend/infrastructure/bootstrap.py`

**Application Layer** (`backend/application/`):
- Business orchestration and use cases
- Handlers for chat/agent/knowledge graph operations

**Services Layer** (`backend/server/`):
- FastAPI REST API (`main.py`)
- Routers for different API endpoints

**Configuration Layer** (`backend/config/`):
- Server-facing configuration (settings, database, RAG semantics)
- `rag_semantics.py`: Domain schema (entity_types, relationship_types, examples)
- `rag.py`: Server-facing semantic exports (avoid direct core dependencies)

**Presentation Layer**:
- `frontend/`: Streamlit UI with debug mode, trace visualization, graph interaction
- `frontend-react/`: React-based UI (Vite dev server)

### Integration Entry Points

**Graph Construction**:
- `backend/infrastructure/integrations/build/main.py`: Full pipeline (KnowledgeGraphBuilder → IndexCommunityBuilder → ChunkIndexBuilder)
  - Run via: `bash scripts/py.sh infrastructure.integrations.build.main`
  - **CRITICAL**: Must run in order; chunk index depends on entity index
- `backend/infrastructure/integrations/build/incremental_update.py`: Incremental updates
  - `--once`: Single incremental build
  - `--daemon`: Background daemon mode

**Bootstrap & Dependency Injection**:
- Core depends only on `ports/` interfaces (never on infrastructure directly)
- Infrastructure provides implementations and injects them via `infrastructure.bootstrap.bootstrap_core_ports()`
- Custom implementations can be injected via `ports.set_*_provider()` methods

## Configuration

### Three-Tier Config System

**IMPORTANT**: Never modify `backend/graphrag_agent/config/settings.py` for business needs. It contains only core defaults and type definitions.

1. **`.env`**: Runtime parameters, API keys, performance tuning
   - Copy from `.env.example` before first run
   - Never commit secrets to git
   - Update `.env.example` when adding new settings

2. **`backend/config/rag_semantics.py`**: RAG semantic/domain schema
   - Entity types, relationship types, theme, examples, response formats
   - Server-facing semantic configuration
   - Consumed by API and application layers

3. **`backend/infrastructure/config/`**: Infrastructure configuration
   - `graphrag_settings.py`: Injects `.env` overrides into core settings
   - `settings.py`: Infrastructure defaults (routing, KB auto-selection, etc.)
   - `semantics.py`: Semantic bridge (infrastructure reads semantics here)
   - `neo4jdb.py`: Database connection management

### Configuration Rules

- **Interface behavior/API settings** → `backend/config/settings.py`
- **Domain schema/semantics** → `backend/config/rag_semantics.py` (or via `.env`)
- **External dependencies/infrastructure** → `backend/infrastructure/config/*`
- **Core defaults** → `backend/graphrag_agent/config/settings.py` (READ-ONLY for business)

### Key Environment Variables

```env
# LLM Configuration
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=http://localhost:13000/v1  # One-API or compatible proxy
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-large
OPENAI_LLM_MODEL=gpt-4o

# Neo4j Configuration
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=12345678

# PostgreSQL (Chat history persistence - optional, falls back to in-memory)
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433  # Note: docker-compose binds to 5433 to avoid conflicts
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=graphrag_chat

# Build Mode Selection
GRAPH_BUILD_MODE=document  # 'document' or 'structured' (movie data)
DOCUMENT_KB_PREFIX=''      # Empty for default, or prefix like 'edu'
STRUCTURED_KB_PREFIX='movie'

# Domain Schema (can also be set in backend/config/rag_semantics.py)
GRAPH_ENTITY_TYPES='学生类型,奖学金类型,处分类型,部门,学生职责,管理规定'
GRAPH_RELATIONSHIP_TYPES='申请,评选,违纪,资助,申诉,管理,权利义务,互斥'
GRAPH_THEME='华东理工大学学生管理'
KB_NAME='华东理工大学'
RESPONSE_TYPE='多个段落'
```

**Build Mode Selection**:
- `document`: Standard document ingestion flow (files/ → chunks → LLM extraction → entities)
- `structured`: Structured data import (e.g., movie dataset with pre-generated canonical entities)

## Common Commands

### Environment Setup

```bash
# Create Python 3.10+ environment
conda create -n graphrag python==3.10
conda activate graphrag

# Install dependencies
pip install -r requirements.txt

# Install in editable mode (for development)
pip install -e .

# Copy environment template
cp .env.example .env
# Edit .env with your API keys and settings
```

### Docker Services

```bash
# Start Neo4j and PostgreSQL
docker compose up -d

# Neo4j browser: http://localhost:7474 (neo4j/12345678)
# PostgreSQL on port 5433 (not 5432 to avoid conflicts)

# Optional: Start One-API proxy
docker run --name one-api -d --restart always \
  -p 13000:3000 \
  -e TZ=Asia/Shanghai \
  -v /home/ubuntu/data/one-api:/data \
  justsong/one-api
```

### Development Servers

```bash
# Start backend only (FastAPI with auto-reload)
bash scripts/dev.sh backend

# Start React frontend only (Vite dev server)
bash scripts/dev.sh frontend

# Start both backend + frontend
bash scripts/dev.sh start

# Stop all services
bash scripts/dev.sh stop

# Check status
bash scripts/dev.sh status

# Environment knobs:
# BACKEND_PORT (default 8324)
# FRONTEND_PORT (default 5174)
# PYTHON_BIN (default .venv/bin/python3)
```

**Alternative Streamlit UI**:
```bash
streamlit run frontend/app.py
```

### Knowledge Graph Construction

```bash
# Place source files in files/ directory first

# Full build (must run in this order)
bash scripts/py.sh infrastructure.integrations.build.main

# Incremental update (single run)
bash scripts/py.sh infrastructure.integrations.build.incremental_update --once

# Incremental update (daemon mode for continuous updates)
bash scripts/py.sh infrastructure.integrations.build.incremental_update --daemon

# Show build help
bash scripts/py.sh infrastructure.integrations.build.main --help
```

**CRITICAL**: Entity index must be completed before chunk index. If running individual steps, complete entity indexing before chunk indexing to avoid errors.

### Testing

```bash
# Run default test suite
bash scripts/test.sh

# Run specific test with unittest args
bash scripts/ut.sh test.test_deep_agent -v

# Run agent tests (non-streaming)
cd test/
python search_without_stream.py

# Run agent tests (streaming)
python search_with_stream.py

# Evaluation tests
cd test/evaluation/

# Evaluate specific agent
python evaluate_graph_agent.py --questions_file questions.json --verbose
python evaluate_hybrid_agent.py --questions_file questions.json --golden_answers_file answer.json
python evaluate_fusion_agent.py --questions_file questions.json --golden_answers_file answer.json

# Compare all agents
python evaluate_all_agents.py --questions_file questions.json --golden_answers_file answer.json --verbose

# Compare subset of agents
python evaluate_all_agents.py --questions_file questions.json --agents graph,hybrid,fusion
```

## Agent System

### BaseAgent Architecture

All agents inherit from `backend/graphrag_agent/agents/base.py`:
- **v3 strict (retrieve-only)**: Agents only do retrieval and return structured evidence
- **No agent-side caching**: retrieval results are not cached inside core agents
- **No agent-side chat state**: conversation/memory are managed at the service side

### Adding New Agents

1. Inherit from `BaseAgent` in `backend/graphrag_agent/agents/`
2. Implement `retrieve_with_trace()` to return structured evidence
3. Register in `backend/infrastructure/agents/` if needed for API access

### Agent Types & Use Cases

- **NaiveRagAgent**: Basic vector retrieval (simple Q&A)
- **GraphAgent**: Graph-structure reasoning (relationship queries)
- **HybridAgent**: Multi-strategy search (combines vector + graph)
- **DeepResearchAgent**: Multi-step think-search-reasoning (complex queries)
- **FusionGraphRAGAgent**: Full Plan-Execute-Report orchestration (comprehensive reports)

### Streaming Implementation

**Important**: Streaming uses LLM `astream()` for token-level streaming. Retrieval still executes to completion before generation starts. Progress events are emitted for UI visibility during retrieval.

To test agents without long runtimes, comment out unwanted agents in test scripts (`test/search_*.py`).

## Search Strategies

- **Local Search**: Entity-centric with neighborhood expansion
  - Starts from query entities, explores graph neighborhoods
  - Returns related entities, relationships, and community context

- **Global Search**: Community-level aggregation
  - Uses community summaries for high-level overviews
  - Controlled by `GLOBAL_SEARCH_LEVEL` (0 = all communities)

- **Hybrid Search**: Combines multiple search modes
  - Vector search + local graph exploration + community context
  - Configurable hop depth (`HYBRID_SEARCH_MAX_HOP`)

- **Deep Research**: Chain of Exploration with evidence tracking
  - Multi-step reasoning on knowledge graph
  - Maintains evidence chain for explainability

Search tools are registered in `backend/graphrag_agent/search/tool_registry.py` and consumed by agents.

## Known Issues & Compatibility

### Model Compatibility
- **Tested & Working**: DeepSeek (20241226), GPT-4o
- **Known Issues**:
  - DeepSeek (20250324): Severe hallucination, entity extraction failures
  - Qwen series: LangChain/LangGraph compatibility issues; use [Qwen-Agent](https://qwen.readthedocs.io/zh-cn/latest/framework/qwen_agent.html) instead

### Embedding Disambiguation Limitation
Due to embedding similarity, "优秀学生" (honor title) may be confused with "国家奖学金" (scholarship). Future work: Fine-tune embeddings for domain-specific distinctions.

### Frontend Timeout for Deep Search
For deep research queries, disable timeout in `frontend/utils/api.py`:
```python
response = requests.post(
    f"{API_URL}/chat",
    json={...},
    # timeout=120  # Comment this out
)
```

## Development Guidelines

### File Registry
`file_registry.json` tracks ingested documents for incremental updates. Do not manually edit.

### Runtime Artifacts
Generated runtime artifacts (graph build outputs, indexes, etc.) live under `files/` and should not be committed.

### Entity Quality Mechanisms
- **Entity Disambiguation**: Maps mentions to canonical entities via string recall + vector reranking + NIL detection
- **Entity Alignment**: Detects and resolves conflicts within canonical entities, preserving all relationships

### Performance Tuning
Key `.env` parameters:
```env
MAX_WORKERS=4                # Thread pool size
BATCH_SIZE=100               # General batch size
ENTITY_BATCH_SIZE=50         # Entity operations
CHUNK_BATCH_SIZE=100         # Text chunks
EMBEDDING_BATCH_SIZE=64      # Vector generation
GDS_MEMORY_LIMIT=6           # Neo4j GDS memory (GB)
GDS_CONCURRENCY=4            # GDS parallelism
```

### Adding New Agents
1. Inherit from `BaseAgent`
2. Implement `_setup_tools()` to return tool list
3. Graph setup is handled by base class via `_setup_graph()`
4. Override `ask()` and `ask_stream()` for custom behavior

### Graph Consistency
Use `backend/graphrag_agent/graph/graph_consistency_validator.py` to check and fix graph inconsistencies after bulk operations.

## Testing & Evaluation

Evaluation framework in `backend/graphrag_agent/evaluation/`:
- **Metrics**: Answer quality, retrieval precision/recall, graph structure quality, deep research evaluation
- **Preprocessing**: Question-answer pair generation
- **Test harness**: See `test/evaluation/README.md`

Example test config in `test/search_with_stream.py`:
```python
TEST_CONFIG = {
    "queries": ["旷课多少学时会被退学？", ...],
    "max_wait_time": 300
}
```

## Multi-Agent (Plan-Execute-Report) Architecture

Located in `backend/graphrag_agent/agents/multi_agent/`:

### Three-Phase Workflow

**Plan Phase** (`planner/`):
- **Clarifier**: Disambiguates user intent and identifies unclear requirements
- **TaskDecomposer**: Breaks query into subtasks with dependencies
- **PlanReviewer**: Validates plan feasibility and optimizes execution order
- **Output**: `PlanSpec` (task graph with tool assignments and priorities)

**Execute Phase** (`executor/`):
- **WorkerCoordinator**: Dispatches tasks based on signals (retrieval/research/reflection)
- **RetrievalExecutor**: Handles search tool execution (local/global/hybrid/deep)
- **ResearchExecutor**: Conducts multi-step research with evidence collection
- **ReflectionExecutor**: Validates answers and triggers retries if needed
- **Output**: `ExecutionRecord` list with evidence and metadata

**Report Phase** (`reporter/`):
- **OutlineBuilder**: Generates document structure from execution results
- **SectionWriter**: Uses Map-Reduce for long document generation
  - Map: Generates sections in parallel with evidence citations
  - Reduce: Assembles sections maintaining coherence
- **ConsistencyChecker**: Validates evidence citations and logical flow
- **Output**: Final report with references and consistency analysis

### Configuration

Key `.env` settings for multi-agent behavior:
```env
MA_PLANNER_MAX_TASKS=6              # Max tasks per plan
MA_WORKER_EXECUTION_MODE=sequential  # 'sequential' or 'parallel'
MA_WORKER_MAX_CONCURRENCY=4         # Max parallel tasks
MA_DEFAULT_REPORT_TYPE=long_document # 'short_answer' or 'long_document'
MA_ENABLE_MAPREDUCE=true            # Use Map-Reduce for long reports
MA_MAPREDUCE_THRESHOLD=20           # Evidence count to trigger Map-Reduce
MA_REFLECTION_ALLOW_RETRY=false     # Auto-retry on validation failure
```

### Integration

- **LegacyCoordinatorFacade** (`integration/`): Provides backward-compatible `process_query()` interface
- Seamless migration from old coordinator to new multi-agent system

## Incremental Updates & Graph Management

### Incremental Build System

Located in `backend/infrastructure/integrations/build/incremental/`:
- **Change Detection**: Tracks ingested documents via `file_registry.json` (DO NOT manually edit)
- **Supported Operations**: File additions, deletions, modifications
- **Conflict Resolution**: Configurable strategies via `GRAPH_CONFLICT_STRATEGY` env var:
  - `manual_first`: Prefer manually edited data
  - `auto_first`: Prefer automatically extracted data
  - `merge`: Attempt to merge both sources

### Entity Quality Mechanisms

- **Entity Disambiguation**: Maps mentions to canonical entities
  - String recall + vector reranking + NIL detection
  - Configurable thresholds: `DISAMBIG_STRING_THRESHOLD`, `DISAMBIG_VECTOR_THRESHOLD`

- **Entity Alignment**: Detects and resolves conflicts within canonical entities
  - Preserves all relationships during alignment
  - Minimum group size controlled by `ALIGNMENT_MIN_GROUP_SIZE`

### Graph Consistency

Use `backend/graphrag_agent/graph/graph_consistency_validator.py` to check and fix inconsistencies after bulk operations or manual graph edits.

## Community Detection & Summarization

### Algorithms

Two algorithms supported via `GRAPH_COMMUNITY_ALGORITHM` env var:
- **leiden**: Standard Leiden algorithm (recommended)
- **sllpa**: Speaker-Listener Label Propagation (fallback to Leiden if no communities detected)

### Community Summaries

Generated via LLM for global search context:
- **Selective Generation**: Only top N communities by rank (controlled by `COMMUNITY_SUMMARY_LIMIT`, default 200)
- **Resumable**: `COMMUNITY_SUMMARY_ONLY_MISSING=true` allows incremental summary generation
- **Batch Processing**: Configurable via `COMMUNITY_SUMMARY_MAX_BATCHES` to control memory usage
- **Size Limits**: `COMMUNITY_SUMMARY_MAX_NODES` and `COMMUNITY_SUMMARY_MAX_RELS` prevent prompt overflow

Community summaries are essential for Global Search to provide high-level contextual answers.

## Development Guidelines

### Code Style

- **PEP 8**: 4-space indentation, `snake_case` for modules/functions, `PascalCase` for classes
- **Type Hints**: Required for public methods
- **Docstrings**: Concise but informative for public APIs
- **Formatting**: Use `black` and `isort` (no repo config, match defaults)

### Module Organization

- All backend code under `backend/` (strict rule)
- Core logic in `backend/graphrag_agent/` (uses only `ports/` interfaces)
- Infrastructure in `backend/infrastructure/` (implements `ports/`)
- Tests mirror package layout in `test/`

### Testing

- Use `unittest` framework
- Name test files `test_{feature}.py`
- Run suite: `bash scripts/test.sh`
- Run specific test: `bash scripts/ut.sh test.test_deep_agent -v`
- Document external prerequisites (Neo4j, API keys) in test files

### Git & Commits

- **Commit Style**: Short, imperative (e.g., "add multi-agent config", "unify configs")
- **Logical Commits**: One feature/fix per commit
- **Optional Prefixes**: Use when clarifying scope (e.g., "agents:", "config:")
- **PRs Should Include**: Summary, linked issue, test results, config changes, migration steps
- **Never Commit**: Secrets, API keys, generated caches, large datasets

### Configuration Changes

- Update `.env.example` when adding new settings
- Update `assets/start.md` for new services/setup steps
- Keep raw data in `documents/` or `datasets/`
- Keep generated artifacts in `cache/` or `files/` (add to `.gitignore`)

### Documentation

- Each module has a `readme.md` explaining its purpose and key components
- Update module readme when adding significant features
- Keep prompt templates readable and avoid trailing whitespace

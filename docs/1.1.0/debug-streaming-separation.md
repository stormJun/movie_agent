# Debug Mode & Streaming Response Separation

**Version**: 1.1.0
**Created**: 2025-01-22
**Status**: Draft
**Type**: Design Document

---

## Executive Summary

**Problem**: Debug mode currently requires disabling streaming responses, forcing users to choose between real-time feedback and debug information.

**Solution**: Separate debug data from the streaming response by:
1. Adding `request_id` to streaming events (`start`, `done`) **at the route layer**
2. Creating a new `GET /api/v1/debug/{request_id}` endpoint for fetching debug data
3. Extending StreamHandler/ChatStreamExecutor event protocol to emit debug events (`route_decision`, `rag_runs`)
4. Caching debug data server-side (in-memory for single-worker, Redis for multi-worker production)

> [!CAUTION]
> **Naming Convention**: This document uses `request_id` (route-layer generated UUID) to avoid confusion with the existing `message_id` concept used in feedback/history features (`backend/server/models/schemas.py:59`, `frontend-react/src/pages/ChatPage.tsx:769`). The API parameter uses `request_id` consistently.

**Key Benefits**:
- ✅ Users get **both** streaming responses **and** debug information
- ✅ On-demand debug data loading (reduces bandwidth)
- ✅ Backward compatible with existing clients
- ✅ Complete debug data coverage (including route_decision and rag_runs)

**Implementation Scope**:
| Component | Changes Required | Rationale |
|-----------|-----------------|-----------|
| Backend (Route Layer) | `request_id` injection, debug data collection, new debug API | Simplest approach, no StreamHandler changes needed for ID |
| Backend (StreamHandler) | **Emit new event types**: `route_decision`, `rag_runs` | Enables complete debug data without breaking existing protocol |
| Backend (Infrastructure) | Debug cache service, debug collector | In-memory (single-worker), Redis (multi-worker production) |
| Frontend | Remove `debugMode` ↔ `streaming` mutex, add debug panel | Backend already supports debug events in streaming |
| Security | Internal-only endpoint; no auth in scope | Do NOT expose publicly without proper auth |

**Design Decisions** (this document):
1. **Message ID**: Use route-layer `request_id` (simplest, no database UUID coupling)
2. **Debug data completeness**: **Modify StreamHandler protocol** to emit `route_decision` and `rag_runs` events
3. **Cache backend**: In-memory for development (with clear warnings about multi-process limitations)
4. **Disconnect handling**: Discard debug data on client disconnect (simplest, no partial data issues)

---

## ⚠️ Prerequisites & Dependencies

> [!CAUTION]
> This design has **external dependencies** that must be addressed before or during implementation.

### 1. Frontend Streaming + Debug Toggle (Streaming Required)

Before this change, the frontend used a mutex like:
```typescript
const canStream = useMemo(() => useStream && !debugMode, [useStream, debugMode]); // old
```

This meant: **debug mode forced non-streaming**, which is incompatible with the "debug-streaming separation" design (because the design requires a stream to carry the `request_id`, then the client fetches debug data via a separate API).

**Required behavior for this design**:
1. Streaming must remain enabled even when `debugMode=true`:
   ```typescript
   const canStream = useMemo(() => useStream || debugMode, [useStream, debugMode]);
   ```
2. After receiving the SSE `done` event (which includes `request_id`), fetch debug data via:
   - `GET /api/v1/debug/{request_id}?user_id=...&session_id=...`
3. Update TypeScript types to include:
   - SSE: `start/done` carry `request_id`
   - Debug API response shape (`execution_log`, `route_decision`, `rag_runs`, ...)

> [!IMPORTANT]
> **Backend already supports debug events in streaming**:
> - Infrastructure layer already emits `execution_log` events in debug mode: `backend/infrastructure/streaming/chat_stream_executor.py:57`
> - These are normalized to `{"status": "execution_log", "content": {...}}` by: `backend/server/models/stream_events.py:22`
> - **Current behavior**: These events are forwarded to the frontend SSE handler: `frontend-react/src/pages/ChatPage.tsx:531`
> - **This design**: Route layer will **cache** these events instead of forwarding them
> - **Conclusion**: The mutex is purely a frontend limitation; backend infrastructure already generates debug events

> [!NOTE]
> **Frontend UX recommendation (implementation choice)**:
> - When a user enables debug mode, force `useStream=true` (and optionally disable turning streaming off while debug is on).
> - Default `debugMode=true` in development builds to reduce "why is my debug panel empty?" confusion.
>   - If you want end-user default behavior, set it back to `false`.
> - After `done`, automatically open a Debug drawer/panel and render:
>   - `execution_log` as a per-step timeline (not a single raw JSON blob)
>   - `route_decision`, `rag_runs`, `progress_events`, `error_events` in dedicated tabs
>
> This makes debug data visible without requiring the user to manually navigate to a settings page.

### 2. Non-Streaming Debug Mode Contract Mismatch (CURRENT BUG)

**Current problem**: When `debugMode=true` (non-streaming), frontend expects `resp.execution_log` but backend doesn't provide it.

**Frontend expectation** (`frontend-react/src/pages/ChatPage.tsx:389`):
```typescript
// Frontend expects to read execution_log from non-streaming response
const debugData = response.execution_log;  // ❌ This field doesn't exist!
```

**Backend reality** (`backend/application/chat/handlers/chat_handler.py:262`):
```python
# Non-streaming chat handler returns rag_runs and route_decision
return {
    "answer": "...",
    "rag_runs": [...],      # ✅ This exists
    "route_decision": {...}, # ✅ This exists
    # ❌ No execution_log field!
}
```

**Impact**: Users enabling debug mode see empty debug data because the frontend reads a field the backend doesn't populate.

**Fix options**:
1. **Quick fix**: Add `execution_log` field to non-streaming response (map from `rag_runs`)
2. **Unified approach**: Use streaming endpoint for both modes with optional debug panel
3. **Contract alignment**: Decide on single debug data format and enforce it across both endpoints

**This design document assumes option 2 (unified streaming approach)**:
- Debug mode uses streaming + debug API (`/api/v1/debug/{request_id}`).
- The non-streaming debug mismatch is avoided by UI policy: debug implies streaming.

### 3. Message ID Semantics (DESIGN DECISION: request_id)

**Problem**: Need a unique identifier to correlate streaming events with debug data.

**Current state**:
- Database layer generates UUID via `append_message()`: `backend/application/ports/conversation_store_port.py:19`
- StreamHandler doesn't expose this UUID: `backend/application/chat/handlers/stream_handler.py:65`

**Chosen approach**: Use route-layer generated `request_id` (NOT database UUID).

```python
# server/api/rest/v1/chat_stream.py
request_id = str(uuid.uuid4())  # Generated at request start, used for debug cache key
```

**Rationale**:
| Aspect | Route-layer `request_id` | Database UUID |
|--------|--------------------------|---------------|
| **Implementation** | ✅ Simple (no StreamHandler changes) | ❌ Requires exposing database UUID through stream |
| **Scope** | Request-scoped (ephemeral) | Persistent (stored in DB) |
| **Debug correlation** | ✅ Works for debug cache | ✅ Would work with history |
| **History lookup** | ❌ Can't correlate with past messages | ✅ Native correlation |
| **Coupling** | ✅ No database dependency | ❌ Tightly coupled to storage layer |

**Trade-off accepted**:
- Debug data is **request-scoped** and **ephemeral** (TTL: 30 minutes)
- "Show me debug for message X in history" is **not supported** in Phase 1
- Future enhancement could optionally store `request_id → message_uuid` mapping for correlation

**Naming convention**:
- API parameter: `request_id` (all APIs use this consistently)
- Internal variable: `request_id` (matches API parameter)
- This avoids confusion with database `message_id` (used in feedback/history features)

### 3.1 LLM Model Cost Control (REQUIRED: claude-sonnet-4-5 only)

To reduce cost during implementation and testing of this design, **all LLM calls MUST use the cheaper model**:

- `claude-sonnet-4-5`

This repository configures LLM selection via environment variables in the infrastructure layer:
- Model selection: `backend/infrastructure/config/settings.py` (`MODEL_TYPE`, `OPENAI_LLM_MODEL`)
- Model construction: `backend/infrastructure/models/get_models.py` (`get_llm_model()`, `get_stream_llm_model()`)

**Required `.env` settings**:
```bash
# Use OpenAI-compatible client (LangChain ChatOpenAI).
MODEL_TYPE=openai

# Force the single LLM model used by routing + generation.
OPENAI_LLM_MODEL=claude-sonnet-4-5
```

> [!NOTE]
> This assumes your OpenAI-compatible gateway/provider supports `OPENAI_LLM_MODEL=claude-sonnet-4-5`.
> If not, you must change the provider first (do NOT silently switch to a more expensive model).

### 4. Debug Data Completeness (DESIGN DECISION: Protocol Extension)

**Problem**: Need complete debug data including `route_decision` and `rag_runs`, but these aren't currently in the SSE event stream.

**Chosen approach**: **Extend StreamHandler/ChatStreamExecutor event protocol** to emit debug events.

> [!CAUTION]
> **Scope of StreamHandler modifications**:
> - ❌ **NOT modifying**: StreamHandler for `request_id` injection or debug cache collection (those stay in route layer)
> - ✅ **MODIFYING**: StreamHandler to emit `route_decision` event
> - ✅ **MODIFYING**: ChatStreamExecutor to emit `rag_runs` event
>
> This avoids the application→server reverse dependency while still getting complete debug data.

**Protocol extension** (new event types):

| Event Type | Emitted By | Shape | Purpose |
|------------|-----------|-------|---------|
| `route_decision` | StreamHandler | `{"status": "route_decision", "content": {...}}` | Route choice (graph/vector/general) |
| `rag_runs` | ChatStreamExecutor | `{"status": "rag_runs", "content": [...]}` | RAG run results |
| `execution_log` | ChatStreamExecutor | `{"status": "execution_log", "content": {...}}` | ✅ Already exists |
| `progress` | ChatStreamExecutor | `{"status": "progress", "content": {...}}` | ✅ Already exists |

**Implementation required**:

**1. StreamHandler emits route_decision**:
```python
# application/chat/handlers/stream_handler.py
#
# ⚠️ MODIFICATION REQUIRED (protocol extension)
#
# ⚠️ CRITICAL: RouteDecision is a dataclass, must convert to dict for JSON serialization
# See: backend/domain/chat/entities/route_decision.py:10

import dataclasses

async def handle(...):
    # Compute route decision (existing code at line ~89)
    # ⚠️ NOTE: Router.route() uses named parameters (message, session_id, requested_kb, agent_type)
    decision = self._router.route(
        message=message,
        session_id=session_id,
        requested_kb=kb_prefix,
        agent_type=agent_type,
    )

    # ⚠️ NEW: Emit route_decision event for caching (not forwarded to client)
    # Must convert dataclass to dict for JSON serialization!
    # Output fields: requested_kb_prefix, routed_kb_prefix, kb_prefix, confidence, method, reason, worker_name
    if debug:
        yield {
            "status": "route_decision",
            "content": dataclasses.asdict(decision)
        }

    # ... rest of existing logic ...
```

**2. ChatStreamExecutor emits rag_runs**:
```python
# infrastructure/streaming/chat_stream_executor.py
#
# ⚠️ MODIFICATION REQUIRED (protocol extension)
#
# ⚠️ CRITICAL: RagRun objects are dataclasses, must convert to dict for JSON serialization
# See: backend/domain/chat/entities/rag_run.py:8

import dataclasses

async def stream(...):
    runs = []  # Existing local variable (line ~68)

    # ... retrieval logic ...

    # ⚠️ NEW: Emit rag_runs event for caching (not forwarded to client)
    if debug:
        # Convert RagRun objects to dicts for JSON serialization
        yield {
            "status": "rag_runs",
            "content": [
                {
                    "agent_type": run.agent_type,
                    "retrieval_count": len(run.retrieval_results or []),
                    "error": str(run.error) if run.error else None,
                    "context_length": len(run.context or ""),
                }
                for run in runs
            ]
        }

    # ... rest of existing logic ...
```

> [!WARNING]
> **JSON Serialization Requirements**:
> - `RouteDecision`, `RagRun`, `RagRunSpec` are all **dataclasses** (`backend/domain/chat/entities/*.py`)
> - SSE `format_sse()` uses `json.dumps()` internally (`backend/infrastructure/streaming/sse.py:7`)
> - **Must use** `dataclasses.asdict()` or manual dict conversion before yielding
> - Failure to convert will cause: `TypeError: Object of type RouteDecision is not JSON serializable`
> - This will **crash the SSE stream** and disconnect the client

**Resulting debug data** (complete):
```json
{
  "request_id": "uuid-xxx",
  "execution_log": [...],      // ✅ From SSE events
  "progress_events": [...],    // ✅ From SSE events
  "error_events": [...],       // ✅ From SSE events
  "route_decision": {...},     // ✅ From new SSE event
  "rag_runs": [...]            // ✅ From new SSE event
}
```

**Backward compatibility**:
- ✅ **Non-debug streaming clients**: No impact (debug events only emitted when `debug=true`)
- ✅ **Existing event types**: No breaking changes to `progress`, `token`, `error`, `start`, `done` events
- ⚠️ **Debug streaming clients**: **BREAKING CHANGE** - Debug events (`execution_log`, `route_decision`, `rag_runs`) are now cache-only and NOT forwarded via SSE
  - **Migration required**: Clients that previously consumed `execution_log` from SSE must migrate to `GET /api/v1/debug/{request_id}`
  - **Current frontend example**: `frontend-react/src/pages/ChatPage.tsx:531` consumes `execution_log` from SSE - this will need updating
  - **Rationale**: Separation of concerns (streaming for real-time UX, debug API for complete data) and bandwidth optimization

### 5. Done Event request_id Injection (IMPLEMENTATION DETAIL)

**Problem**: Infrastructure layer yields `{"status": "done"}` without `request_id`. Route layer must inject it.

**Current code** (`backend/infrastructure/streaming/chat_stream_executor.py:54`):
```python
yield {"status": "done"}  # ❌ No request_id
```

**Fix required** in route layer (`server/api/rest/v1/chat_stream.py`):
```python
payload = normalize_stream_event(event)

# ⚠️ CRITICAL: Inject request_id into ALL done events (normal path + fallback)
if isinstance(payload, dict) and payload.get("status") == "done":
    if "request_id" not in payload:
        payload["request_id"] = request_id  # ✅ Add to normal path

yield format_sse(payload)
```

This is documented in the implementation section but is easy to miss during implementation.

### 6. PYTHONPATH Convention

**Project default**: `PYTHONPATH=${ROOT}/backend` (see `scripts/dev.sh:49`)

**All code examples in this document** use imports without `backend.` prefix:
```python
# ✅ CORRECT (matches dev.sh PYTHONPATH)
from server.api.rest.v1.debug import router
from infrastructure.debug.debug_cache import DebugDataCache

# ❌ WRONG (unless PYTHONPATH includes repo root)
from backend.server.api.rest.v1.debug import router
from backend.infrastructure.debug.debug_cache import DebugDataCache
```

---

## ⚠️ Critical Security Warning

**THIS DESIGN INTRODUCES A NEW DEBUG API THAT CAN EXPOSE SENSITIVE USER DATA IF NOT PROPERLY SECURED.**

### Security Measures (Internal-only, minimal scope)

This document does NOT include auth. Treat the debug API as a **local-dev / trusted-network** feature only.

Recommended minimum:
1. **Do NOT expose publicly**: keep behind localhost/VPN/firewall.
2. **User ownership check**: require callers to provide `user_id` (and optionally `session_id`) and verify it matches the cached entry.
3. **Data sanitization**: redact secrets/PII before returning debug payloads.
4. **Basic rate limiting + audit logs** (optional): helpful even in internal environments.

**Consequences of Failure**:
- PII exposure (violates GDPR, CCPA)
- Credential theft (API keys, tokens)
- Prompt injection attacks
- Legal liability and reputational damage

**See Section 9 "Security & Access Control" for complete implementation details.**

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Prerequisites & Dependencies](#-prerequisites--dependencies)

1. [Background & Problems](#1-background--problems)
2. [Design Goals](#2-design-goals)
3. [Solution Comparison](#3-solution-comparison)
4. [Technical Architecture](#4-technical-architecture)
5. [API Design](#5-api-design)
6. [Data Structures](#6-data-structures)
7. [Implementation Details](#7-implementation-details)
8. [Frontend Adaptation](#8-frontend-adaptation)
9. [Security & Access Control](#9-security--access-control)
10. [Deployment & Configuration](#10-deployment--configuration)
11. [Testing Plan](#11-testing-plan)
12. [Performance Optimization](#12-performance-optimization)
13. [Risks & Limitations](#13-risks--limitations)

**Appendix**:
- A. [Import Path Quick Reference](#a-import-path-quick-reference)
- B. [Code Quality Checklist](#b-code-quality-checklist)
- C. [Related Documentation](#c-related-documentation)
- D. [Migration Guide](#d-migration-guide)
- E. [Changelog](#e-changelog)
- F. [Review Notes](#f-review-notes)

---

## 1. Background & Problems

### 1.1 Current Issue

**Status Quo**:
- Debug mode requires disabling streaming response
- Users cannot simultaneously experience "real-time feedback" and "debug information"
- Debug data (execution logs, knowledge graphs, traces) cannot be transmitted completely in streaming mode

**Root Cause**:
```python
# Current implementation (pseudo-code)
if debug_mode:
    # Non-streaming: return all data at once
    return {
        "answer": "complete answer",
        "execution_log": [...],
        "kg_data": {...},
        "trace": {...}
    }
else:
    # Streaming: send tokens one by one, debug data lost
    async for token in stream():
        yield {"status": "token", "content": token}
```

### 1.2 Impact

| User Group | Impact |
|-----------|--------|
| Developers | Cannot see generation process in debug mode |
| QA/Testers | Difficult to debug agent behavior and retrieval performance |
| End Users | Poor UX in debug mode (long wait times) |

---

## 2. Design Goals

### 2.1 Core Goals

1. **Debug mode supports streaming**
   - Users can see real-time generation and debug info simultaneously

2. **Separation of concerns**
   - Streaming API only handles content generation
   - Debug API specifically provides debug data

   > [!IMPORTANT]
   > **Event Transmission Strategy**:
   > - **Forwarded to client**: `progress`, `token`, `start`, `done`, `error` events (required for real-time streaming UX)
   > - **Cache-only**: `execution_log`, `route_decision`, `rag_runs` events (debug data, retrieved via GET /api/v1/debug/{request_id})
   >
   > This separation ensures:
   > - Clients receive only essential streaming events for progress/token display
   > - Debug data is complete and available on-demand via the debug API
   > - Reduced bandwidth usage (debug data can be large, especially execution_log)
   >
   > **⚠️ BREAKING CHANGE**: Debug clients that previously consumed `execution_log` from SSE must now call `GET /api/v1/debug/{request_id}` after receiving `done`.

3. **On-demand loading**
   - Frontend decides whether to load debug data
   - Reduces unnecessary data transfer

4. **Backward compatibility**
   - No impact on existing non-streaming API
   - Smooth migration

### 2.2 Non-Goals

- **No change to non-debug behavior**: Non-debug mode continues to work as before (streaming or non-streaming)
- **No forcing debug mode to use non-streaming**: Debug mode **defaults to streaming** (unified approach), but non-streaming debug API remains available
- **No mandatory Redis for single-worker**: Single-worker deployments can use in-memory cache; Redis is **REQUIRED only for multi-worker production**
- **No breaking changes for non-debug clients**: Clients that don't use `debug=true` are unaffected

---

## 3. Solution Comparison

### 3.1 Solution Matrix

| Solution | Pros | Cons | Complexity | Recommendation |
|----------|------|------|------------|----------------|
| **A. Send debug package at stream end** | Simple to implement | High latency with large data | Medium | 3/5 |
| **B. Frontend reconstructs debug data** | No backend changes | Data integrity hard to guarantee | High | 1/5 |
| **C. Separate APIs (this doc)** | Clear responsibilities, scalable | Requires new APIs | Medium | 5/5 |

### 3.2 Solution C Details

| Dimension | Current | Solution C |
|-----------|---------|------------|
| Debug mode | Must disable streaming | Supports streaming |
| Data transfer | One-time full transfer | Split on-demand transfer |
| Caching strategy | None | Can cache debug data |
| API count | 1 (`POST /api/v1/chat/stream`, debug incompatible) | 2 (`POST /api/v1/chat/stream` + `GET /api/v1/debug/{request_id}`) |
| Frontend changes | None needed | New debug data query |
| Backend changes | None needed | New debug data collection + API |

---

## 4. Technical Architecture

> [!IMPORTANT]
> **Design Decision**: This document adopts **Option A (Route Layer Injection)**.
> - `request_id` is generated in `chat_stream.py` (route layer), NOT in `stream_handler.py`
> - Debug data is collected in route layer **after** `normalize_stream_event()` transforms events
> - Debug cache/collector modules live in `infrastructure/debug/` (avoids application→server reverse dependency)
> - Current `start/done` events in route layer are extended (not replaced)

### 4.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Frontend (React/Vite)                             │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────┐      ┌─────────────────────────────┐    │
│  │ Streaming UI           │      │ Debug Panel UI              │    │
│  │ - Token display        │      │ - Execution logs            │    │
│  │ - Progress bar         │      │ - Route decision            │    │
│  │ - Extract request_id   │      │ - RAG runs                  │    │
│  └────────────────────────┘      └─────────────────────────────┘    │
│           │                                    │                     │
│           │ SSE                                │ HTTP GET            │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  server/api/rest/v1/ (Route Layer) ← request_id injection here     │
├─────────────────────────────────────────────────────────────────────┤
│  chat_stream.py                    │  debug.py (NEW)                │
│  ┌──────────────────────────────┐  │  ┌───────────────────────────┐ │
│  │ POST /api/v1/chat/stream     │  │  │ GET /api/v1/debug/{id}    │ │
│  │ 1. Generate request_id       │  │  └───────────────────────────┘ │
│  │ 2. yield {"status":"start",  │  │              │                 │
│  │       "request_id": xxx}     │  │              ▼                 │
│  │ 3. Call handler.handle()     │  │  ┌───────────────────────────┐ │
│  │ 4. normalize_stream_event()  │──┼─▶│ infrastructure/debug/     │ │
│  │ 5. Collect debug events      │  │  │ - DebugDataCache          │ │
│  │ 6. yield {"status":"done",   │  │  │ - DebugDataCollector      │ │
│  │       "request_id": xxx}     │  │  └───────────────────────────┘ │
│  └──────────────────────────────┘  │                                │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  application/chat/handlers/stream_handler.py                        │
│  - Route decision, RAG orchestration                                │
│  - ❌ Does NOT yield start/done events                              │
│  - ❌ Does NOT import from server layer (no reverse dependency)     │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  infrastructure/streaming/chat_stream_executor.py                   │
│  - Yields {"execution_log": {...}} (raw, no "status" key)           │
│  - Route layer transforms via normalize_stream_event()              │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow

```
User query
    │
    ▼
POST /api/v1/chat/stream {debug: true}
    │
    │  ┌─────────────────────────────────────────────────────────────┐
    │  │ chat_stream.py (Route Layer)                                │
    │  │                                                             │
    ├──┤ 1. Generate request_id = uuid.uuid4()                       │
    │  │ 2. Create DebugDataCollector(request_id, user_id, ...)      │
    │  │ 3. yield {"status": "start", "request_id": xxx}             │
    │  │                                                             │
    │  │ 4. for event in handler.handle(...):                        │
    │  │        # handler yields raw events like:                    │
    │  │        #   {"status": "route_decision", "content": {...}}   │
    │  │        #   {"status": "token", "content": "..."}            │
    │  │        #   {"execution_log": {...}}  ← NO status field!     │
    │  │        #   {"status": "rag_runs", "content": [...]}         │
    │  │        #   {"status": "progress", ...}                      │
    │  │                                                             │
    │  │ 5. payload = normalize_stream_event(event)                  │
    │  │        # transforms {"execution_log": {...}}                │
    │  │        # into {"status": "execution_log", "content": {...}} │
    │  │                                                             │
    │  │ 6. ⚠️ CRITICAL: Inject request_id into done events        │
    │  │        if payload.get("status") == "done":                  │
    │  │            payload["request_id"] = request_id               │
    │  │                                                             │
    │  │ 7. Cache debug events (not forwarded)                       │
    │  │    if debug and payload.get("status") in [                 │
    │  │        "execution_log", "route_decision", "rag_runs"       │
    │  │    ]:                                                       │
    │  │        collector.add_event(payload.get("status"), payload.get("content")) │
    │  │                                                             │
    │  │ 8. Forward streaming events to client (progress, token, start, done, error) │
    │  │    if payload.get("status") in [                           │
    │  │        "progress", "token", "start", "done", "error"       │
    │  │    ]:                                                       │
    │  │        yield format_sse(payload)                            │
    │  │                                                             │
    │  │ 9. finally: (after loop exits)                             │
    │  │        if not sent_done:                                    │
    │  │            # Fallback: executor didn't yield done           │
    │  │            yield {"status": "done", "request_id": xxx}      │
    │  │                                                             │
    │  │ 10. debug_cache.set(request_id, collector)                  │
    │  └─────────────────────────────────────────────────────────────┘
    │
    ▼
Frontend receives done (with request_id)
    │
    ▼
GET /api/v1/debug/{request_id}
    │ (Dev mode: user_id from query param)
    │
    ├─► Read from debug_cache
    │
    └─► Return {
          "request_id": "xxx",
          "execution_log": [...],   // ✅ from streaming events
          "progress_events": [...], // ✅ from streaming events
          "error_events": [...],    // ✅ from streaming events
          "route_decision": {...},  // ✅ from NEW route_decision event
          "rag_runs": [...]         // ✅ from NEW rag_runs event
        }
```

> [!NOTE]
> **Event Collection Logic**: The route layer collects all debug events **after** `normalize_stream_event()` transforms them. This includes:
> - Existing events: `execution_log`, `progress`, `error`
> - **NEW events (Phase 1)**: `route_decision`, `rag_runs`
>
> **Protocol extension required**: StreamHandler must emit `route_decision`, ChatStreamExecutor must emit `rag_runs`. See Section "Debug Data Completeness" for implementation details.

---

### 4.3 API Path Convention

All REST APIs are prefixed with `/api/v1`:
- Streaming: `POST /api/v1/chat/stream`
- Debug: `GET /api/v1/debug/{request_id}`
- Cleanup: `DELETE /api/v1/debug/{request_id}`
- Admin cleanup: `POST /api/v1/debug/cleanup`

**⚠️ IMPORTANT**:
- All API paths use `request_id` (route-layer generated UUID) to avoid confusion with database `message_id`
- All API paths in diagrams, data flows, and code examples MUST use the full `/api/v1/` prefix

---

## 5. API Design

### 5.1 Streaming API (Backward Compatible Extension)

**Endpoint**: `POST /api/v1/chat/stream`

**⚠️ Clarification**: This is NOT a "no changes" situation. We are EXTENDING the existing streaming API by adding new fields. The changes are **backward compatible** but require code modifications.

**Backward Compatibility Guarantee**:

| Client Type | Behavior | Impact |
|-------------|----------|--------|
| **Existing clients** (deployed before this change) | Ignore `request_id` field, continue working | ✅ No impact - JSON spec allows unknown fields |
| **New clients** (with debug support) | Read `request_id` from start/done events, fetch debug data | ✅ New functionality enabled |

**What's Changing**:

✅ **NEW (Additions)**:
- `start` event: Now includes `request_id` field (UUIDv4)
- `done` event: Now includes `request_id` field (same UUIDv4)
- Backend: Generate and track `request_id` for each request

❌ **UNCHANGED**:
- `token` events: No changes
- `progress` events: No changes
- `error` events: No changes
- SSE protocol: No changes
- Request format: No changes

**Implementation Required**:

**Backend Changes** (TWO-PART CHANGE):

**Part 1: Protocol Extensions** (REQUIRED - Application & Infrastructure Layers):
- **StreamHandler** must emit `route_decision` event (see section 4.2)
- **ChatStreamExecutor** must emit `rag_runs` event (see section 4.2)
- These are NEW events that don't currently exist

**Part 2: Route Layer Collection** (REQUIRED - Route Layer):
```python
# server/api/rest/v1/chat_stream.py
#
# ⚠️ EXAMPLE CODE (REFERENCE IMPLEMENTATION)
# This shows the intended structure; actual file location and details may vary.
# Differences from current code:
# - Current: start/done events exist but don't include request_id
# - Needed: Add request_id generation and injection at route layer
# - NEW: Collect debug events including route_decision and rag_runs
# - NEW: Filter events (cache-only events NOT forwarded to client)

import uuid

# Event types to collect for debugging
# Cache-only events (NOT forwarded to client)
CACHE_ONLY_EVENT_TYPES = {"execution_log", "route_decision", "rag_runs"}

# Events to both cache AND forward (useful for debugging after done)
CACHE_AND_FORWARD_TYPES = {"progress", "error"}

# All debug event types (combined)
DEBUG_EVENT_TYPES = CACHE_ONLY_EVENT_TYPES | CACHE_AND_FORWARD_TYPES

async def event_generator():
    sent_done = False
    client_disconnected = False  # ⚠️ Track disconnection state

    # ⚠️ NEW: Generate request_id at route layer
    request_id = str(uuid.uuid4())

    # ⚠️ NEW: Create debug collector if debug mode
    collector = None
    if request.debug:
        from infrastructure.debug.debug_collector import DebugDataCollector
        collector = DebugDataCollector(request_id, request.user_id, request.session_id)

    # ⚠️ MODIFIED: Inject request_id into start event
    yield format_sse({"status": "start", "request_id": request_id})

    iterator = handler.handle(
        user_id=request.user_id,
        message=request.message,
        session_id=request.session_id,
        kb_prefix=request.kb_prefix,
        debug=request.debug,
        agent_type=request.agent_type,
    ).__aiter__()

    try:
        while True:
            # ⚠️ CRITICAL: is_disconnected() is async - requires await
            # Track state to avoid calling again in finally block
            if await raw_request.is_disconnected():
                client_disconnected = True
                break

            try:
                event = await asyncio.wait_for(
                    iterator.__anext__(),
                    timeout=max(float(SSE_HEARTBEAT_S), 1.0),
                )
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            except StopAsyncIteration:
                break

            # ⚠️ NEW: Normalize and collect debug events
            payload = normalize_stream_event(event)

            # ⚠️ CRITICAL: Inject request_id into done events (both normal and fallback)
            if isinstance(payload, dict) and payload.get("status") == "done":
                if "request_id" not in payload:
                    payload["request_id"] = request_id
                sent_done = True

                # ⚠️ CRITICAL: Set cache BEFORE forwarding done event
                # This prevents race condition where client receives done and immediately
                # calls GET /api/v1/debug/{request_id} before cache is set
                if collector and request.debug and not client_disconnected:
                    from infrastructure.debug.debug_cache import debug_cache
                    debug_cache.set(request_id, collector)
                    # Clear collector to avoid double-set in finally block
                    collector = None

            # ⚠️ NEW: Collect debug events (cache + optional forward)
            if collector and request.debug:
                status = payload.get("status")
                if status in DEBUG_EVENT_TYPES:
                    # Special handling for error events (use "message" field, not "content")
                    if status == "error":
                        collector.add_event(status, {"message": payload.get("message", "")})
                    else:
                        collector.add_event(status, payload.get("content", {}))

            # ⚠️ CRITICAL: Forward events based on type
            # - CACHE_ONLY events: NOT forwarded (only available via debug API)
            # - CACHE_AND_FORWARD events: Forwarded to client AND cached
            # - Other events: Forwarded (token, start, done, etc.)
            status = payload.get("status")
            if status not in CACHE_ONLY_EVENT_TYPES:
                # Forward everything except cache-only debug events
                yield format_sse(payload)
    finally:
        # Propagate cancellation/close to the underlying async generator
        aclose = getattr(iterator, "aclose", None)
        if callable(aclose):
            await aclose()

    # ⚠️ NEW: Store debug data only if client didn't disconnect AND not already set
    # (collector is set to None after cache set in done handler to avoid double-set)
    if collector and request.debug and not client_disconnected:
        from infrastructure.debug.debug_cache import debug_cache
        debug_cache.set(request_id, collector)

    # ⚠️ MODIFIED: Inject request_id into fallback done
    if not sent_done:
        yield format_sse({"status": "done", "request_id": request_id})
```

> [!IMPORTANT]
> **Route Layer Injection Design**: This design injects `request_id` at the route layer (`chat_stream.py`), NOT in `stream_handler.py`.
> - `stream_handler.py` does NOT yield `start`/`done` events (see current code at `backend/application/chat/handlers/stream_handler.py`)
> - Route layer is responsible for all `start`/`done` events and `request_id` injection
> - Debug collection happens AFTER `normalize_stream_event()` transforms raw events
> - Debug modules live in `infrastructure/debug/` to avoid application→server reverse dependency
> - **NEW**: Collects `route_decision` and `rag_runs` events from extended protocol

**Frontend Changes** (OPTIONAL for existing clients):

**Option A: Existing clients (no changes needed)**
```javascript
// Client continues to work - ignores unknown fields
const response = await fetch('/api/v1/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message: "..." })
});

const reader = response.body.getReader();
// ... parse SSE events, extract request_id if present ...
```

**Option B: New clients with debug support**
```javascript
// Extract request_id from start event
let requestId = null;

const eventHandler = (event) => {
  const data = JSON.parse(event.data);

  if (data.status === 'start' && data.request_id) {
    // ⚠️ NEW: Capture request_id
    requestId = data.request_id;
  }

  if (data.status === 'token') {
    // Handle tokens (unchanged)
    displayToken(data.content);
  }

  if (data.status === 'done' && data.request_id) {
    // ⚠️ NEW: Fetch debug data after stream completes
    fetchDebugData(requestId).then(debug => {
      displayDebugPanel(debug);
    });
  }
};
```

**Request Example**:
```json
{
  "message": "What movies did Nolan direct?",
  "user_id": "user123",
  "session_id": "session456",
  "debug": true,
  "agent_type": "graph_agent"
}
```

**Response (SSE event stream) - NEW fields highlighted**:
```
data: {"status": "start", "request_id": "msg_uuid_123"}
                              ^^^^^^^^^^^^^^^ NEW

data: {"status": "token", "content": "According"}
data: {"status": "token", "content": " to"}
data: {"status": "token", "content": " knowledge"}
data: {"status": "token", "content": " graph"}

data: {"status": "progress", "content": {"stage": "retrieval", "completed": 5, "total": 10}}

data: {"status": "token", "content": "..."}
data: {"status": "token", "content": "Inception"}

data: {"status": "done", "request_id": "msg_uuid_123"}
                            ^^^^^^^^^^^^^^^ NEW (same as start)
```

**Migration Path**:

1. **Phase 1: Backend Deployment**
   - Deploy new backend code with `request_id` injection
   - Existing clients continue working (ignore unknown fields)
   - No downtime required

2. **Phase 2: Frontend Rollout** (optional, gradual)
   - Update frontend clients to read `request_id`
   - Enable debug panel functionality
   - Canary release to subset of users

3. **Phase 3: Full Rollout**
   - All clients support debug mode
   - Monitor for any compatibility issues
   - Remove legacy clients if needed

### 5.2 Debug Data API (New)

**Endpoint**: `GET /api/v1/debug/{request_id}`

**Authentication**: None (internal-only; do not expose publicly)

**Authorization Rule**:
Users can ONLY access debug data for their own requests (matched by `user_id`).

**Threat Model**:
- **Risk**: Request ID guessing → expose other users' traces
- **Mitigation**:
  1. UUIDv4 request_id (128-bit entropy, impractical to guess)
  2. User ownership verification (user_id mismatch = 403 Forbidden)
  3. Short TTL (30 min) limits exposure window
  4. Rate limiting (10 requests/minute per IP)

**Request**:
```
GET /api/v1/debug/msg_uuid_123
```

**Success Response (200 OK)**:
```json
{
  "request_id": "msg_uuid_123",
  "timestamp": "2025-01-22T12:34:56Z",
  "user_id": "user123",
  "session_id": "session456",
  "execution_log": [
    {
      "node": "rag_plan",
      "input": {"message": "What movies did Nolan direct?", "kb_prefix": "movie"},
      "output": {"plan": ["graph_agent", "vector_search"]},
      "timestamp": "2025-01-22T12:34:56Z"
    },
    {
      "node": "rag_retrieval_done",
      "input": {"agent_type": "graph_agent"},
      "output": {"error": null, "retrieval_count": 15},
      "timestamp": "2025-01-22T12:34:57Z"
    },
    {
      "node": "rag_fanout_done",
      "input": {"plan": ["graph_agent", "vector_search"]},
      "output": {
        "errors": {},
        "retrieval_counts": {"graph_agent": 15, "vector_search": 8}
      },
      "timestamp": "2025-01-22T12:34:58Z"
    }
  ],
  "progress_events": [
    {
      "stage": "retrieval",
      "completed": 2,
      "total": 2,
      "error": null,
      "agent_type": "graph_agent",
      "retrieval_count": 15
    },
    {
      "stage": "generation",
      "completed": 2,
      "total": 2,
      "error": null,
      "agent_type": "",
      "retrieval_count": null
    }
  ],
  "error_events": [],
  "route_decision": {
    "requested_kb_prefix": "movie",
    "routed_kb_prefix": "movie",
    "kb_prefix": "movie",
    "confidence": 0.95,
    "method": "direct_match",
    "reason": "User explicitly requested movie knowledge base",
    "worker_name": "movie:graph_agent"
  },
  "rag_runs": [
    {
      "agent_type": "graph_agent",
      "retrieval_count": 15,
      "error": null,
      "context_length": 2340
    },
    {
      "agent_type": "vector_search",
      "retrieval_count": 8,
      "error": null,
      "context_length": 1200
    }
  ],
  "trace": [],
  "kg_data": null
}
```

> [!NOTE]
> **Response Format**:
> - `request_id`: Route-layer generated UUID (ephemeral, TTL: 30 minutes)
> - `execution_log`: From SSE events (infrastructure layer)
> - `route_decision`: From **NEW** `route_decision` SSE event (StreamHandler)
>   - ⚠️ **Format**: `dataclasses.asdict(decision)` output from RouteDecision dataclass
>   - ⚠️ **Actual fields**: `requested_kb_prefix`, `routed_kb_prefix`, `kb_prefix`, `confidence`, `method`, `reason`, `worker_name`
> - `rag_runs`: From **NEW** `rag_runs` SSE event (ChatStreamExecutor)
> - `trace`: Empty (Phase 2 feature - not currently emitted)

**Error Response (404 Not Found)**:
```json
{
  "detail": "Debug data for request_id 'msg_uuid_123' not found or expired"
}
```

**Error Response (403 Forbidden)**:
```json
{
  "detail": "Access denied: debug data belongs to a different user"
}
```

### 5.3 Debug Data Cleanup API (Optional)

**Endpoint**: `DELETE /api/v1/debug/{request_id}`

**Response**:
```json
{
  "status": "cleared",
  "request_id": "msg_uuid_123"
}
```

---

### 5.4 Code Organization

**Repository Structure**:
```
movie_agent/                         # Repository root
├── backend/                         # All backend code (PYTHONPATH points here)
│   ├── server/
│   │   ├── api/rest/v1/
│   │   │   ├── chat_stream.py       # Streaming endpoint (injects request_id)
│   │   │   └── debug.py             # Debug API endpoints (NEW)
│   │   └── models/
│   │       ├── schemas.py           # Request/Response schemas
│   │       └── stream_events.py     # normalize_stream_event()
│   ├── infrastructure/
│   │   ├── debug/                   # ⚠️ Debug modules live here (not server/)
│   │   │   ├── __init__.py
│   │   │   ├── debug_cache.py       # LRU/Redis cache
│   │   │   └── debug_collector.py   # Per-request collector
│   │   └── streaming/
│   │       └── chat_stream_executor.py  # Yields execution_log events
│   ├── application/
│   │   └── chat/handlers/
│   │       └── stream_handler.py    # ❌ Does NOT import from server/
│   └── config/
│       └── settings.py
└── frontend-react/
    └── src/
        ├── services/debugApi.ts
        ├── hooks/useChatStream.ts
        └── components/DebugPanel.tsx
```

**Import Convention**: All code examples assume `PYTHONPATH=${REPO}/backend` (as per `scripts/dev.sh:49`).

```python
# ✅ CORRECT (matches dev.sh PYTHONPATH)
from infrastructure.debug.debug_cache import DebugDataCache
from server.api.rest.v1.debug import router

# ❌ WRONG (repo-relative imports don't work with dev.sh)
from backend.infrastructure.debug.debug_cache import DebugDataCache
```

> [!NOTE]
> See [Appendix A: Import Path Quick Reference](#a-import-path-quick-reference) for detailed PYTHONPATH configuration.

---

## 6. Data Structures

### 6.1 Debug Data Structure

```python
# server/models/debug_data.py
#
# ⚠️ EXAMPLE CODE (REFERENCE IMPLEMENTATION)
# This shows the intended structure; actual file location and details may vary.
# Note: This module does not exist in the current codebase.

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class ExecutionLogEntry(BaseModel):
    """
    Single execution log entry (matches infrastructure layer format).

    ⚠️ IMPORTANT: This matches the actual format emitted by infrastructure layer:
    - backend/infrastructure/streaming/chat_stream_executor.py:57-64
    - Raw event: {"execution_log": {"node": "...", "input": {...}, "output": {...}}}
    - Normalized: {"status": "execution_log", "content": {"node": "...", "input": {...}, "output": {...}}}
    """
    node: str  # e.g., "rag_plan", "rag_retrieval_done", "rag_timeout"
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class ProgressEvent(BaseModel):
    """Progress event (matches SSE progress event format)"""
    stage: str  # e.g., "retrieval", "generation"
    completed: int
    total: int
    error: Optional[str] = None
    agent_type: str = ""
    retrieval_count: Optional[int] = None


class RAGRun(BaseModel):
    """Single RAG run result"""
    agent_type: str
    retrieval_count: int
    error: Optional[str] = None
    context_length: int


class DebugData(BaseModel):
    """
    Complete debug data for a request.

    ⚠️ NOTE: 'trace' field is marked as optional (Phase 2 feature).
    Current infrastructure layer does not emit trace events.
    """
    request_id: str  # Route-layer generated UUID (NOT database UUID)
    user_id: str
    session_id: str
    timestamp: datetime
    # ⚠️ CORRECT: Use Field(default_factory=list) for mutable defaults
    execution_log: List[ExecutionLogEntry] = Field(default_factory=list)
    progress_events: List[ProgressEvent] = Field(default_factory=list)
    error_events: List[Dict[str, Any]] = Field(default_factory=list)
    # ✅ NEW: From route_decision event (StreamHandler emits this)
    route_decision: Optional[Dict[str, Any]] = None
    # ✅ NEW: From rag_runs event (ChatStreamExecutor emits this)
    rag_runs: List[RAGRun] = Field(default_factory=list)
    # ⚠️ PHASE 2: Trace events (not currently emitted by infrastructure layer)
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    kg_data: Optional[Dict[str, Any]] = None  # ✅ OK: None is immutable
```

**⚠️ CRITICAL: Python Mutable Default Arguments Pitfall**

```python
# ❌ WRONG - This is a common Python bug!
class BadExample:
    def __init__(self, items=[]):  # Same list object reused across instances
        self.items = items

# Correct behavior:
a = BadExample()
a.items.append("x")
b = BadExample()
print(b.items)  # Prints: ["x"]  ← BUG! b.items should be empty!

# ✅ CORRECT - Use None and create new instance
class GoodExample:
    def __init__(self, items=None):
        self.items = items if items is not None else []

# ✅ CORRECT - Pydantic provides Field(default_factory=...)
class PydanticExample(BaseModel):
    items: List[str] = Field(default_factory=list)
```

**Why Pydantic requires `Field(default_factory=...)`:**
- Pydantic models are defined at class level (not in `__init__`)
- Default values are evaluated once at class definition time
- Using `[]` or `{}` directly would share the same mutable object across all instances
- `Field(default_factory=list)` calls `list()` separately for each instance

**See Also**: [Python Docs: Default Argument Values](https://docs.python.org/3/tutorial/controlflow.html#default-argument-values)

---

## 7. Implementation Details

### 7.1 Backend Implementation

#### 7.1.1 Debug Data Collector

```python
# infrastructure/debug/debug_collector.py
#
# ⚠️ EXAMPLE CODE (REFERENCE IMPLEMENTATION)
# This module does not exist in the current codebase.
# This shows the intended structure; actual implementation may vary.
#
# This module lives in infrastructure/ to allow server layer to import it
# without creating application→server reverse dependency.

from typing import Dict, List, Any, Optional
from datetime import datetime


class DebugDataCollector:
    """
    Debug data collector for tracking execution details.

    Thread-safety: NOT thread-safe. Create a new instance per request.
    Memory: Typical usage ~100KB-1MB per request depending on log length.

    ⚠️ IMPORTANT: This collector stores normalized debug events.
    - Input format (from normalize_stream_event): {"status": "...", "content": {...}}
    """

    def __init__(self, request_id: str, user_id: str, session_id: str):
        self.request_id = request_id
        self.user_id = user_id
        self.session_id = session_id
        self.timestamp = datetime.now()

        # ⚠️ NOTE: Using [] in __init__ is SAFE (creates new list per instance)
        self.execution_log: List[Dict] = []      # From execution_log events
        self.progress_events: List[Dict] = []    # From progress events
        self.error_events: List[Dict] = []       # From error events
        self.route_decision: Optional[Dict] = None  # From route_decision event (NEW!)
        self.rag_runs: List[Dict] = []           # From rag_runs event (NEW!)
        # ⚠️ PHASE 2: Trace events (not currently emitted by infrastructure layer)
        self.trace: List[Dict] = []
        self.kg_data: Optional[Dict] = None

    def add_event(self, event_type: str, content: Dict[str, Any] | List[Any]):
        """
        Add debug event (unified interface for all event types).

        Args:
            event_type: The status field (e.g., "execution_log", "progress", "route_decision", "rag_runs")
            content: The content field (event payload)
                - Most events: Dict[str, Any]
                - rag_runs: List[Dict[str, Any]] (list of run summaries)

        Example:
            payload = {"status": "execution_log", "content": {"node": "rag_plan", ...}}
            collector.add_event(payload["status"], payload["content"])

            rag_runs_payload = {"status": "rag_runs", "content": [...]}
            collector.add_event(rag_runs_payload["status"], rag_runs_payload["content"])
        """
        if event_type == "execution_log":
            # ⚠️ content is Dict for execution_log
            if isinstance(content, dict):
                content["timestamp"] = datetime.now().isoformat()
                self.execution_log.append(content)
        elif event_type == "progress":
            self.progress_events.append(content)
        elif event_type == "error":
            # ⚠️ content is Dict with "message" field for error events
            if isinstance(content, dict):
                self.error_events.append({
                    "message": content.get("message", ""),
                    "timestamp": datetime.now().isoformat()
                })
        elif event_type == "route_decision":
            self.route_decision = content
        elif event_type == "rag_runs":
            # ⚠️ content is List[Dict] for rag_runs
            self.rag_runs = content
        # else: ignore unknown event types

    def add_trace_event(self, event_type: str, data: Dict[str, Any]):
        """
        Add trace event (Phase 2 feature).

        ⚠️ NOTE: Current infrastructure layer does not emit trace events.
        This method is provided for future extensibility.
        """
        self.trace.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "execution_log": self.execution_log,
            "progress_events": self.progress_events,
            "error_events": self.error_events,
            "route_decision": self.route_decision,
            "rag_runs": self.rag_runs,
            "trace": self.trace,  # Phase 2
            "kg_data": self.kg_data
        }
```

#### 7.1.2 Debug Data Cache Manager

```python
# infrastructure/debug/debug_cache.py
#
# ⚠️ EXAMPLE CODE (REFERENCE IMPLEMENTATION)
# This module does not exist in the current codebase.
# This shows the intended structure; actual implementation may vary.
#
# Thread-safe LRU cache implementation using OrderedDict.
# For production with multiple workers, use Redis implementation instead.
#
# ⚠️ KNOWN LIMITATION (uvicorn --reload / multi-worker):
# With --reload or multiple workers, each process has its own cache.
# Debug data written by worker A may be read by worker B → 404.
# Solution: Use Redis cache for dev/prod with multiple processes.

from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict
import threading

class DebugDataCache:
    """
    Debug data cache (in-memory with LRU eviction).

    Thread-safety: Thread-safe (uses threading.Lock).
    LRU Implementation: Uses OrderedDict.move_to_end() + popitem(last=False)
    """

    def __init__(self, ttl_minutes: int = 30, max_size: int = 1000):
        self._cache: OrderedDict[str, "DebugDataCollector"] = OrderedDict()
        self._ttl = timedelta(minutes=ttl_minutes)
        self._max_size = max_size
        self._lock = threading.Lock()  # ⚠️ REQUIRED for thread safety

    def set(self, request_id: str, collector: "DebugDataCollector"):
        """Store debug data with LRU eviction"""
        with self._lock:  # ⚠️ Thread-safe critical section
            # Enforce max size with LRU eviction
            if len(self._cache) >= self._max_size:
                # ⚠️ CORRECT: Remove oldest entry (first item in OrderedDict)
                # WRONG (common bug): min(self._cache.keys()) - this is arbitrary, not oldest!
                self._cache.popitem(last=False)

            # Add/Move to end (most recently used)
            self._cache[request_id] = collector
            self._cache.move_to_end(request_id)

    def get(self, request_id: str) -> Optional["DebugDataCollector"]:
        """Get debug data if not expired"""
        with self._lock:  # ⚠️ Thread-safe critical section
            collector = self._cache.get(request_id)
            if collector is None:
                return None

            # Check expiration
            if datetime.now() - collector.timestamp > self._ttl:
                del self._cache[request_id]
                return None

            # Mark as recently used
            self._cache.move_to_end(request_id)
            return collector

    def delete(self, request_id: str) -> bool:
        """Delete debug data"""
        with self._lock:  # ⚠️ Thread-safe critical section
            if request_id in self._cache:
                del self._cache[request_id]
                return True
            return False

    def cleanup_expired(self) -> int:
        """Clean up expired entries"""
        with self._lock:  # ⚠️ Thread-safe critical section
            now = datetime.now()
            expired_keys = [
                req_id for req_id, collector in self._cache.items()
                if now - collector.timestamp > self._ttl
            ]
            for req_id in expired_keys:
                del self._cache[req_id]
            return len(expired_keys)


# Global cache instance
# ⚠️ NOTE: For multi-process deployments (gunicorn, uwsgi), use Redis implementation instead
debug_cache = DebugDataCache(ttl_minutes=30, max_size=1000)
```

> [!NOTE]
> **StreamHandler Modification**: This design does NOT modify `stream_handler.py` to inject `request_id` or collect debug data.
> - `stream_handler.py` does NOT yield `start`/`done` events (see current code)
> - Route layer (`chat_stream.py`) is responsible for all `request_id` injection and debug collection
> - This avoids application→server reverse dependency

#### 7.1.3 Debug API Implementation

```python
# ============================================================
# File: server/api/rest/v1/debug.py
# ============================================================
#
# ⚠️ EXAMPLE CODE (REFERENCE IMPLEMENTATION)
# This module does not exist in the current codebase.
# This shows the intended structure; actual implementation may vary.
#
# ⚠️ IMPORT PATH NOTICE:
# All imports use PYTHONPATH=${REPO}/backend convention (no backend. prefix).
# ============================================================

from fastapi import APIRouter, HTTPException, Query
from infrastructure.debug.debug_cache import debug_cache

# Router with /api/v1 prefix - all routes below will be prefixed with /api/v1
router = APIRouter(prefix="/api/v1", tags=["debug"])


@router.get("/debug/{request_id}")  # Full path: GET /api/v1/debug/{request_id}
async def get_debug_data(
    request_id: str,
    user_id: str = Query(..., description="Internal-only: pass user_id explicitly"),
    session_id: str | None = Query(None, description="Optional: pass session_id for stricter checks"),
) -> dict:
    """
    Get debug data for a specific request

    Full endpoint path: GET /api/v1/debug/{request_id}

    Args:
        request_id: Request ID from streaming response
        user_id: User ID for ownership verification (internal-only)
        session_id: Optional session ID for additional verification

    Returns:
        Debug data including execution_log, progress_events, error_events

    Raises:
        404: Debug data not found or expired
        403: Access denied (different user)
    """
    collector = debug_cache.get(request_id)

    if not collector:
        raise HTTPException(
            status_code=404,
            detail=f"Debug data for request_id '{request_id}' not found or expired"
        )

    # Ownership check (internal-only; no auth in scope)
    if collector.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: debug data belongs to a different user"
        )
    if session_id and getattr(collector, "session_id", None) != session_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: debug data belongs to a different session"
        )

    return collector.to_dict()


@router.delete("/debug/{request_id}")  # Full path: DELETE /api/v1/debug/{request_id}
async def clear_debug_data(
    request_id: str,
    user_id: str = Query(..., description="Internal-only: pass user_id explicitly"),
) -> dict:
    """Manually clear debug data for a specific request"""
    collector = debug_cache.get(request_id)

    # Ownership check (internal-only; no auth in scope)
    if collector and collector.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: debug data belongs to a different user"
        )

    deleted = debug_cache.delete(request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found")

    return {"status": "cleared", "request_id": request_id}


@router.post("/debug/cleanup")  # Full path: POST /api/v1/debug/cleanup
async def cleanup_expired_debug_data():
    """Clean up all expired debug data (internal maintenance endpoint)."""
    count = debug_cache.cleanup_expired()
    return {"status": "cleaned", "expired_count": count}
```

#### 7.1.4 Register Debug Router

> [!IMPORTANT]
> **CRITICAL: Router must be registered in api_router.py**
>
> After implementing the debug endpoints above, you MUST register the router in `backend/server/api_router.py`:
>
> ```python
> # backend/server/api_router.py
> #
> # ⚠️ ADD THIS IMPORT AND INCLUDE STATEMENT
>
> import server.api.rest.v1.debug as debug_v1  # ⚠️ NEW
>
> api_router = APIRouter()
> # ... existing includes ...
> api_router.include_router(debug_v1.router)  # ⚠️ NEW - CRITICAL!
> ```
>
> **Without this step**, the debug endpoints will return 404 even if implemented correctly.

---

---

## 8. Frontend Adaptation

**Frontend Stack**: React + Vite + TypeScript (frontend-react/)

**Legacy Note**: Streamlit frontend (frontend/) is deprecated and no longer maintained. All examples below use the React stack.

> [!WARNING]
> **CRITICAL BLOCKER: Frontend mutex prevents unified streaming**
>
> **Current State**: `frontend-react/src/pages/ChatPage.tsx:228` enforces mutual exclusion:
> ```typescript
> const canStream = useMemo(() => useStream && !debugMode, [useStream, debugMode]);
> ```
>
> **Implication**: When `debugMode=true`, streaming is DISABLED. This contradicts the "unified streaming" approach in this design.
>
> **To implement this design**, you MUST:
> 1. Remove this mutex: allow `debugMode + useStream` simultaneously
> 2. Update UI flow:
>    - Enable streaming when debug mode is on
>    - Extract `request_id` from `start` event
>    - After receiving `done` event, call `GET /api/v1/debug/{request_id}`
>    - Display debug data in Debug Panel
>
> **Until the mutex is removed**, this design cannot be fully implemented.

> [!CAUTION]
> **ADDITIONAL FRONTEND CHANGES REQUIRED**
>
> Beyond removing the mutex, the frontend currently consumes `execution_log` events from SSE (`frontend-react/src/pages/ChatPage.tsx:531`):
>
> ```typescript
> // CURRENT CODE (will break after implementation):
> if (ev.status === "execution_log") {
>   setExecutionLogs((prev) => [...prev, ev.content]);
>   return;
> }
> ```
>
> **Required changes**:
> 1. **Remove SSE execution_log consumption** - execution_log events will no longer be forwarded (cache-only)
> 2. **Add debug API call** after receiving `done`:
>    ```typescript
>    if (ev.status === "done" && ev.request_id && debugMode) {
>      const debugData = await fetchDebugData(ev.request_id);
>      setExecutionLogs(debugData.execution_log);
>      setDebugData(debugData); // Store all debug data
>    }
>    ```
> 3. **Update TypeScript types** to match new DebugData interface (see section 8.1)
>
> This is a **breaking change** from the current debug mode behavior.

### 8.1 React/Vite Integration

```typescript
// frontend-react/src/services/debugApi.ts

interface ExecutionLogEntry {
  node: string;  // e.g., "rag_plan", "rag_retrieval_done"
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  timestamp: string;
}

interface ProgressEvent {
  stage: string;
  completed: number;
  total: number;
  error: string | null;
  agent_type: string;
  retrieval_count: number | null;
}

interface RAGRun {
  agent_type: string;
  retrieval_count: number;
  error: string | null;
  context_length: number;
}

interface DebugData {
  request_id: string;  // Route-layer generated UUID (ephemeral)
  timestamp: string;
  user_id: string;
  session_id: string;
  execution_log: ExecutionLogEntry[];
  progress_events: ProgressEvent[];
  error_events: Array<{ message: string; timestamp: string }>;
  // ✅ NEW: From route_decision event (RouteDecision dataclass fields)
  route_decision: {
    requested_kb_prefix: string;
    routed_kb_prefix: string;
    kb_prefix: string;
    confidence: number;
    method: string;
    reason: string;
    worker_name: string;
  } | null;
  // ✅ NEW: From rag_runs event
  rag_runs: RAGRun[];
  // ⚠️ Phase 2: Trace events (not currently emitted by backend)
  trace: Array<{ timestamp: string; event_type: string; data: Record<string, unknown> }>;
  kg_data: Record<string, unknown> | null;
}

export async function getDebugData(
  messageId: string, 
  userId?: string  // Internal-only: pass user_id explicitly
): Promise<DebugData | null> {
  try {
    // Build URL with optional user_id query param (dev mode)
    const url = new URL(`/api/v1/debug/${messageId}`, window.location.origin);
    if (userId) {
      url.searchParams.set('user_id', userId);  // Dev mode: pass user_id explicitly
    }

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (response.status === 404) {
      return null;  // Debug data expired or wrong process (multi-worker issue)
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Failed to fetch debug data:', error);
    return null;
  }
}
```

### 8.2 Streaming Handler Update

```typescript
// frontend-react/src/hooks/useChatStream.ts

interface StreamOptions {
  onToken: (token: string) => void;
  onProgress?: (progress: Record<string, unknown>) => void;
  onStreamEnd?: (messageId: string) => void;
  onError?: (error: Error) => void;
}

export async function streamChatWithDebug(
  message: string,
  options: StreamOptions
): Promise<string | null> {
  const { onToken, onProgress, onStreamEnd, onError } = options;

  try {
    const response = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        user_id: localStorage.getItem('userId'),
        session_id: localStorage.getItem('sessionId'),
        debug: true,  // Enable debug mode
        agent_type: 'graph_agent',
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let messageId: string | null = null;

    if (!reader) {
      throw new Error('Response body is null');
    }

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;

        const data = line.slice(6);
        if (!data) continue;

        try {
          const event = JSON.parse(data);

          // Extract request_id
          if (event.status === 'start' && event.request_id) {
            requestId = event.request_id;
          }

          // Handle token
          if (event.status === 'token') {
            onToken(event.content || '');
          }

          // Handle progress
          if (event.status === 'progress' && onProgress) {
            onProgress(event.content);
          }

          // Handle done
          if (event.status === 'done' && onStreamEnd && requestId) {
            onStreamEnd(requestId);
          }
        } catch (parseError) {
          console.error('Failed to parse SSE event:', parseError);
        }
      }
    }

    return messageId;
  } catch (error) {
    onError?.(error as Error);
    return null;
  }
}
```

### 8.3 Debug Panel Component

```typescript
// frontend-react/src/components/DebugPanel.tsx

import React, { useState, useEffect } from 'react';
import { getDebugData } from '../services/debugApi';

interface DebugPanelProps {
  messageId: string;
}

export const DebugPanel: React.FC<DebugPanelProps> = ({ messageId }) => {
  const [debugData, setDebugData] = useState<DebugData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDebugData() {
      setLoading(true);
      setError(null);

      const data = await getDebugData(messageId);

      if (!data) {
        setError('Debug data not found or expired');
      } else {
        setDebugData(data);
      }

      setLoading(false);
    }

    loadDebugData();
  }, [messageId]);

  if (loading) {
    return <div className="p-4">Loading debug data...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-500">{error}</div>;
  }

  if (!debugData) {
    return <div className="p-4">No debug data available</div>;
  }

  return (
    <div className="debug-panel border rounded p-4">
      <h3 className="text-lg font-bold mb-4">Debug Information</h3>

      <Tabs>
        <Tab label="Route Decision">
          {debugData.route_decision ? (
            <div className="space-y-2">
              <div><strong>Route:</strong> {debugData.route_decision.route}</div>
              <div><strong>KB Prefix:</strong> {debugData.route_decision.kb_prefix}</div>
              <div><strong>Agents:</strong> {debugData.route_decision.agents.join(", ")}</div>
            </div>
          ) : (
            <div className="text-sm text-gray-500">No route decision data</div>
          )}
        </Tab>

        <Tab label="Execution Logs">
          {debugData.execution_log.map((log, idx) => (
            <div key={idx} className="mb-2">
              <div className="flex justify-between">
                <span className="font-semibold">{log.node}</span>
                <span className="text-sm text-gray-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
              </div>
              <pre className="text-xs bg-gray-100 p-2 rounded">
                Input: {JSON.stringify(log.input, null, 2)}
                Output: {JSON.stringify(log.output, null, 2)}
              </pre>
            </div>
          ))}
        </Tab>

        <Tab label="RAG Runs">
          {debugData.rag_runs.length === 0 ? (
            <div className="text-sm text-gray-500">No RAG runs data</div>
          ) : (
            <div className="space-y-2">
              {debugData.rag_runs.map((run, idx) => (
                <div key={idx} className="border p-2 rounded">
                  <div className="font-semibold">{run.agent_type}</div>
                  <div className="text-sm">Retrieved: {run.retrieval_count}</div>
                  <div className="text-sm">Context: {run.context_length} chars</div>
                  {run.error && <div className="text-sm text-red-600">Error: {run.error}</div>}
                </div>
              ))}
            </div>
          )}
        </Tab>

        <Tab label="Progress">
          {debugData.progress_events.map((event, idx) => (
            <div key={idx} className="mb-2">
              <div className="flex justify-between text-sm">
                <span>{event.stage}</span>
                <span>{event.completed}/{event.total}</span>
              </div>
              {event.agent_type && <span className="text-xs text-gray-500">Agent: {event.agent_type}</span>}
              {event.retrieval_count !== null && <span className="text-xs text-gray-500">Retrieved: {event.retrieval_count}</span>}
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full"
                  style={{ width: `${(event.completed / event.total) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </Tab>

        <Tab label="Errors">
          {debugData.error_events.length === 0 ? (
            <div className="text-sm text-gray-500">No errors</div>
          ) : (
            debugData.error_events.map((event, idx) => (
              <div key={idx} className="mb-2 text-sm text-red-600">
                {event.message}
                <div className="text-xs text-gray-400">{new Date(event.timestamp).toLocaleTimeString()}</div>
              </div>
            ))
          )}
        </Tab>

        <Tab label="Trace">
          {debugData.trace.length === 0 ? (
            <div className="text-sm text-gray-500">No trace events (Phase 2 feature)</div>
          ) : (
            <pre className="text-xs bg-gray-100 p-2 rounded overflow-auto max-h-96">
              {JSON.stringify(debugData.trace, null, 2)}
            </pre>
          )}
        </Tab>
      </Tabs>
    </div>
  );
};
```

---

## 9. Security & Access Control

### 9.1 Access Control (Internal-only)

This design intentionally excludes auth. The debug API must be treated as **internal-only**:
- Bind to localhost / protect via VPN / firewall.
- Require callers to provide `user_id` (and optionally `session_id`) and verify ownership before returning any data.

**Threat Model**:
- **UUIDv4 request_id provides 128-bit entropy**, but should NOT be relied upon as the sole security mechanism
- Attackers who obtain a valid request_id (via logs, network sniffing, or internal sharing) could access debug data
- Debug data contains sensitive information: user queries, tool traces, LLM prompts, API keys
- **Unauthorized access can lead to**: PII exposure, prompt injection attacks, credential theft

**Security Requirements**:
1. **User ownership verification**: `request_id` must belong to the requesting `user_id`
2. **Session validation** (optional): verify `session_id` matches to reduce accidental leakage
3. **Rate limiting** (optional): helpful to prevent brute-force / scraping even internally

**Implementation (Internal-only)**:
```python
# server/api/rest/v1/debug.py

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends, status
from infrastructure.debug.debug_cache import debug_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["debug"])

@router.get("/debug/{request_id}")
async def get_debug_data(
    request_id: str,
    user_id: Optional[str] = Query(None),  # Pass user_id explicitly (internal-only)
    session_id: Optional[str] = Query(None),  # Optional extra check
) -> dict:
    """
    Get debug data for a specific request

    ⚠️ SECURITY: This endpoint MUST:
    1. Verify user ownership (user_id match)
    2. (Optional) Verify session ownership (session_id match)
    3. Sanitize sensitive data
    """
    collector = debug_cache.get(request_id)

    if not collector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debug data for request_id '{request_id}' not found or expired"
        )

    requesting_user_id = user_id

    # ⚠️ CRITICAL: Verify user ownership before returning ANY data
    if not requesting_user_id or collector.user_id != requesting_user_id:
        logger.warning(
            f"Unauthorized debug access attempt: user_id={requesting_user_id} "
            f"attempted to access request_id={request_id} owned by {collector.user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: debug data belongs to a different user"
        )

    # Optional: Verify session ownership (additional security layer)
    if session_id and collector.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: debug data belongs to a different session"
        )

    # ⚠️ CRITICAL: Sanitize sensitive data before returning
    collector = sanitize_debug_data(collector)

    return collector.to_dict()
```

### 9.2 Data Sanitization

**⚠️ CRITICAL PRIVACY REQUIREMENT**: Debug data MUST be sanitized before returning to non-admin users.

**Fields That MUST NEVER Be Returned to Non-Admin Users**:

| Field Type | Examples | Risk Level | Action |
|------------|----------|------------|--------|
| **API Keys / Tokens** | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | 🔴 CRITICAL | Replace with `***REDACTED***` |
| **User PII** | Email, phone, address, SSN in queries | 🔴 CRITICAL | Replace with `[REDACTED]` |
| **Full LLM Prompts** | System prompts, few-shot examples | 🟠 HIGH | Replace with `[PROMPT REDACTED - ${len(prompt)} chars]` |
| **Raw Tool Inputs** | Search queries, database queries | 🟠 HIGH | Keep only `type` and `result_count` |
| **Internal Paths** | File paths, internal URLs | 🟡 MEDIUM | Replace with `[INTERNAL PATH]` |
| **Session/Auth Tokens** | Bearer tokens, session cookies | 🔴 CRITICAL | Replace with `***TOKEN REDACTED***` |

**Field Whitelist (Safe to Return)**:
- `request_id`, `timestamp`, `user_id`
- Tool names (`vector_search`, `graph_query`)
- Execution metrics (`duration_ms`, `step`, `stage`)
- Success/failure status
- Result counts (without PII)

**Implementation**:
```python
# server/api/rest/v1/debug_sanitizer.py
#
# ⚠️ EXAMPLE CODE (REFERENCE IMPLEMENTATION)
# This module does not exist in the current codebase.
# This shows the intended structure; actual implementation may vary.

import re
from typing import Dict, Any, List

# Patterns to detect sensitive data
SENSITIVE_PATTERNS = {
    "api_key": re.compile(r'(api[_-]?key|apikey|token)\s*[:=]\s*[\'"]?[\w-]+', re.IGNORECASE),
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "ssn": re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
}

def sanitize_string(text: str) -> str:
    """Sanitize a single string value"""
    if not text:
        return text

    # Check for known patterns
    for pattern_name, pattern in SENSITIVE_PATTERNS.items():
        if pattern.search(text):
            return f"[{pattern_name.upper()} REDACTED]"

    return text

def sanitize_debug_data(collector: "DebugDataCollector") -> "DebugDataCollector":
    """
    Remove sensitive information from debug data

    ⚠️ CRITICAL: This function MUST be called before returning debug data to non-admin users

    Note: This matches the actual execution_log format: {"node": "...", "input": {...}, "output": {...}}
    """
    # Sanitize execution_log (using actual infrastructure layer format)
    for log_entry in collector.execution_log:
        input_data = log_entry.get("input", {})
        output_data = log_entry.get("output", {})

        # Redact user queries (may contain PII)
        if "message" in input_data:
            query = input_data["message"]
            if len(query) > 100:  # Long queries more likely to contain PII
                input_data["message"] = f"[QUERY REDACTED - {len(query)} chars]"
            else:
                input_data["message"] = sanitize_string(query)

        # Redact full prompts (if present in input/output)
        for field in ["prompt", "system_prompt"]:
            if field in input_data:
                prompt = input_data[field]
                input_data[field] = f"[PROMPT REDACTED - {len(prompt)} chars]"

        # Redact file paths
        for field in ["file_path", "input_path", "output_path"]:
            if field in input_data:
                input_data[field] = "[INTERNAL PATH]"

    # Sanitize trace events (Phase 2 - not currently emitted)
    for event in collector.trace:
        event_data = event.get("data", {})

        # Redact API keys
        if "api_key" in event_data:
            event_data["api_key"] = "***REDACTED***"

        # Sanitize tool inputs
        if "tool_input" in event_data:
            tool_input = event_data["tool_input"]
            # Keep only structural information
            event_data["tool_input"] = {
                "type": tool_input.get("type"),
                "result_count": tool_input.get("result_count", "N/A"),
                "duration_ms": tool_input.get("duration_ms", "N/A"),
            }

        # Redact bearer tokens
        if "authorization" in event_data:
            event_data["authorization"] = "***TOKEN REDACTED***"

    return collector
```

**Example Output (Non-Admin User)**:
```json
{
  "request_id": "msg_uuid_123",
  "user_id": "user456",
  "execution_log": [
    {
      "node": "rag_plan",
      "input": {
        "message": "[QUERY REDACTED - 45 chars]",
        "kb_prefix": "movie"
      },
      "output": {
        "plan": ["graph_agent", "vector_search"]
      },
      "timestamp": "2025-01-22T12:34:56Z"
    },
    {
      "node": "rag_retrieval_done",
      "input": {"agent_type": "graph_agent"},
      "output": {
        "error": null,
        "retrieval_count": 10
      },
      "timestamp": "2025-01-22T12:34:57Z"
    }
  ],
  "trace": [],
  "progress_events": [],
  "error_events": []
}
```

> [!NOTE]
> **Sanitization Note**: This example shows the sanitized output format.
> - `execution_log` entries use the actual infrastructure layer format
> - `trace` is empty (Phase 2 feature - not currently emitted)
> - User queries are redacted if they exceed 100 characters or match sensitive patterns

### 9.3 Rate Limiting

```python
# backend/server/api/rest/v1/debug.py

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/debug/{request_id}")
@limiter.limit("10/minute")  # Max 10 requests per minute per IP
async def get_debug_data(...):
    # ... implementation ...
```

> [!IMPORTANT]
> **Rate limiting is OPTIONAL and requires additional dependencies**.
>
> To use the rate limiting example above:
> 1. Install `slowapi`: `pip install slowapi`
> 2. Add to requirements: `slowapi>=0.1.9`
> 3. Initialize limiter in your FastAPI app setup
>
> If you don't want rate limiting, simply omit the `@limiter.limit()` decorator.

---

---

## 10. Debug Cache (In-Memory for Development)

> [!CAUTION]
> **In-memory cache is designed for single-process development environments**. For production deployment with multiple workers, consider Redis as an enhancement.

### 10.1 Multi-Process Limitation (KNOWN CONSTRAINT)

**Problem**: In-memory cache is **per-process** and doesn't work across workers.

**Impact scenarios**:

| Scenario | What Happens | User Experience | Acceptable? |
|----------|--------------|-----------------|-------------|
| **uvicorn --reload** (dev) | Code reload → new process → empty cache | 404 on debug GET for recent requests | ✅ Yes (development) |
| **gunicorn --workers N** (prod) | Request handled by worker A, debug fetch by worker B | 404 (random failures) | ❌ No (production issue) |
| **Single worker, no reload** | Single process serves all requests | Works correctly | ✅ Yes (manual testing) |

**Current development setup** (`scripts/dev.sh:53`):
```bash
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
# ↑ --reload causes process restart on code changes
# ↑ All debug cache data is lost on every reload
# ↑ This is ACCEPTABLE for development
```

**Recommendation**:
- ✅ **Development**: Use in-memory cache, accept 404s after code reloads
- ✅ **Production (single worker)**: In-memory cache works fine
- ❌ **Production (multi-worker)**: Redis cache **REQUIRED** (see section 10.4 for implementation)

### 10.2 Client Disconnect Handling (DESIGN DECISION: Discard Data)

**Problem**: When client disconnects, route layer breaks the loop (`backend/server/api/rest/v1/chat_stream.py:40`). Should we save partial debug data?

**Chosen approach**: **Discard debug data on disconnect**.

**Rationale**:
- ✅ **Simple**: No need for complex partial data handling
- ✅ **Clean**: No incomplete/broken debug data in cache
- ❌ **Lost data**: Users can't debug requests that disconnected mid-stream

**Implementation**:
```python
# server/api/rest/v1/chat_stream.py

# Event type constants (same as main implementation)
CACHE_ONLY_EVENT_TYPES = {"execution_log", "route_decision", "rag_runs"}
CACHE_AND_FORWARD_TYPES = {"progress", "error"}
DEBUG_EVENT_TYPES = CACHE_ONLY_EVENT_TYPES | CACHE_AND_FORWARD_TYPES

async def event_generator():
    collector = None
    if request.debug:
        collector = DebugDataCollector(request_id, ...)

    client_disconnected = False
    try:
        # ... stream processing loop ...
        while True:
            # Check for client disconnection (async function - requires await)
            if await raw_request.is_disconnected():
                client_disconnected = True
                break

            # ... get next event ...
            payload = normalize_stream_event(event)

            # Inject request_id into done events
            if isinstance(payload, dict) and payload.get("status") == "done":
                if "request_id" not in payload:
                    payload["request_id"] = request_id

                # ⚠️ Set cache BEFORE forwarding done (prevents race condition)
                if collector and request.debug and not client_disconnected:
                    debug_cache.set(request_id, collector)
                    collector = None  # Avoid double-set in finally

            # Collect debug events (with error special handling)
            if collector and request.debug:
                status = payload.get("status")
                if status in DEBUG_EVENT_TYPES:
                    # Special handling for error events (use "message" field)
                    if status == "error":
                        collector.add_event(status, {"message": payload.get("message", "")})
                    else:
                        collector.add_event(status, payload.get("content", {}))

            # Forward events based on type (cache-only events NOT forwarded)
            status = payload.get("status")
            if status not in CACHE_ONLY_EVENT_TYPES:
                yield format_sse(payload)
    finally:
        # ⚠️ Only save cache if not already saved in done handler
        if collector and request.debug and not client_disconnected:
            debug_cache.set(request_id, collector)
```

**Future enhancement**: If partial debug data is valuable, move `debug_cache.set()` outside the `is_disconnected()` check.

### 10.3 Memory Management

**Problem**: In-memory cache grows unbounded if not managed.

**Current proposal**:
- LRU eviction with max size (default: 1000 entries)
- TTL-based expiration (default: 30 minutes)

**Memory estimate**:
- Typical debug entry: ~100KB-1MB (depends on log length)
- 1000 entries × 500KB avg = ~500MB RAM per worker
- 4 workers × 500MB = ~2GB RAM (if using multi-worker)

**Mitigation**:
- Smaller max size for development (100-200 entries)
- Shorter TTL for development (5-10 minutes)
- Monitor memory usage during development

### 10.4 Production Deployment: Redis Cache (REQUIRED for Multi-Worker)

> [!IMPORTANT]
> **Redis is REQUIRED for multi-worker/multi-instance production deployments**.
>
> - **Single-worker development**: In-memory cache works fine
> - **Multi-worker production**: Redis is REQUIRED to avoid 404s from process isolation
> - **Reason**: Each worker process has its own in-memory cache; debug data written by process A cannot be read by process B

**When to use Redis**:
- ✅ Production deployment with multiple workers (`--workers N` in gunicorn/uvicorn)
- ✅ Production deployment with multiple instances/pods (Kubernetes, docker-compose scale)
- ✅ Need debug data to survive pod restarts
- ✅ Want consistent debug data access across all workers

**When in-memory cache is sufficient**:
- ✅ Single-worker development (`python -m uvicorn server.main:app --reload`)
- ✅ Single-worker testing (`--workers 1`)
- ❌ NOT suitable for multi-worker production

**Implementation**: See section "12.2 Redis Cache Implementation (REQUIRED for Multi-Worker Production)" for reference implementation.

**Production readiness checklist** (before enabling Redis):
- [ ] Redis deployment and connection testing
- [ ] Fail-open vs fail-closed behavior when Redis is down
- [ ] Monitoring for Redis hit/miss rates
- [ ] Memory limits and eviction policies

---

## 11. Deployment & Configuration

### 11.1 Runtime Behavior

> [!CAUTION]
> **uvicorn --reload and Multi-Worker Cache Issue**
>
> The project uses `uvicorn --reload` in dev mode (`scripts/dev.sh:53`). With `--reload` or multiple workers (`--workers N`), **each process has its own in-memory cache**. This means:
> - Debug data written by process A may be read by process B → **404 Not Found**
> - Code changes trigger reload → **all cached debug data is lost**
>
> **Solutions** (when debug cache is implemented):
> - **Dev (single worker, no reload)**: In-memory cache works fine
> - **Dev (with reload)**: Accept 404s during development
> - **Prod (single worker)**: In-memory cache works fine
> - **Prod (multiple workers)**: Redis cache **REQUIRED** (see section 10.4)

**Debug Data Lifecycle** (when implemented):

1. **Creation**:
   - Triggered by: `POST /api/v1/chat/stream` with `debug=true`
   - Storage: In-memory cache (default)
   - TTL: Starts when created, auto-expire after TTL (default: 30 minutes)

2. **Access**:
   - User fetches via: `GET /api/v1/debug/{request_id}`
   - Authorization (dev): `user_id` from query param or request body
   - Rate limit: 10 requests/minute per IP (to be implemented)

3. **Cleanup**:
   - Automatic: Background task runs every `DEBUG_CLEANUP_INTERVAL` minutes (to be implemented)
   - Manual: `DELETE /api/v1/debug/{request_id}` (user-initiated)
   - Trigger: LRU eviction when cache reaches `DEBUG_CACHE_MAX_SIZE` (to be implemented)

4. **Failure Handling**:
   - Client disconnect: Debug data **DISCARDED** (by design - see section 10.2)
     - **Consequence**: Debug endpoint returns 404 for disconnected requests
     - **Rationale**: Avoids partial/broken debug data in cache
   - Cache miss: Return 404 (data expired, never existed, or **wrong process**)
   - Cache full: Evict oldest entry (LRU)

**Resource Limits** (proposed for implementation):

| Resource | Default | Max | Environment Variable | Status |
|----------|---------|-----|---------------------|--------|
| Cache entries | 1000 | 10000 | `DEBUG_CACHE_MAX_SIZE` | ⚠️ TO BE IMPLEMENTED |
| TTL per entry | 30 min | 24 hours | `DEBUG_CACHE_TTL` | ⚠️ TO BE IMPLEMENTED |

> [!NOTE]
> **Resource Limits**: The above limits are **proposed values** for the debug system.
> These environment variables do not exist in the current codebase and should be added to `config/settings.py` during implementation.

---

### 10.2 Environment Variables

> [!CAUTION]
> **Configuration Note**: The environment variables below are **proposed** for the debug system.
> These do not exist in the current codebase. Implementation should add these to `config/settings.py`.

| Variable | Description | Default | Required | Status |
|----------|-------------|---------|----------|--------|
| `DEBUG_CACHE_TTL` | Debug data TTL in minutes | `30` | No | ⚠️ TO BE IMPLEMENTED |
| `DEBUG_CACHE_MAX_SIZE` | Maximum cache entries | `1000` | No | ⚠️ TO BE IMPLEMENTED |
| `DEBUG_CLEANUP_INTERVAL` | Cleanup interval in minutes | `10` | No | ⚠️ TO BE IMPLEMENTED |

**Example `.env` configuration** (for future implementation):
```bash
# Debug Cache Settings (TO BE IMPLEMENTED)
DEBUG_CACHE_TTL=30
DEBUG_CACHE_MAX_SIZE=1000
DEBUG_CLEANUP_INTERVAL=10
```

---

### 10.3 Configuration File

> [!CAUTION]
> **Configuration Note**: This is a **proposed** addition to `config/settings.py`.
> These settings do not exist in the current codebase.

```python
# config/settings.py
#
# ⚠️ PROPOSED CONFIGURATION (TO BE IMPLEMENTED)
# These settings should be added to the existing settings module.

from os import getenv

# Debug cache configuration (TO BE IMPLEMENTED)
DEBUG_CACHE_TTL: int = int(getenv("DEBUG_CACHE_TTL", "30"))  # minutes
DEBUG_CACHE_MAX_SIZE: int = int(getenv("DEBUG_CACHE_MAX_SIZE", "1000"))
DEBUG_CLEANUP_INTERVAL: int = int(getenv("DEBUG_CLEANUP_INTERVAL", "10"))  # minutes
```

**Configuration source** (when implemented):
1. Environment variables (`.env` file) - highest priority
2. Configuration files (`config/settings.py`) - defaults
3. Code constants - fallback values

---

### 10.4 Deployment Checklist

- [ ] Backend code updates (stream_handler.py, debug.py)
- [ ] Frontend code updates (debugApi.ts, DebugPanel.tsx)
- [ ] Environment variable configuration
- [ ] Route registration (main.py)
- [ ] Test streaming + debug mode
- [ ] Performance testing (high concurrency)
- [ ] Monitor cache memory usage
- [ ] Security audit (authentication/authorization)

**Verification commands** (when implemented):
```bash
# Verify debug cache configuration (TO BE IMPLEMENTED)
python -c "
from config.settings import DEBUG_CACHE_TTL, DEBUG_CACHE_MAX_SIZE
print(f'TTL: {DEBUG_CACHE_TTL} min, Max Size: {DEBUG_CACHE_MAX_SIZE}')
"

# Test Redis connection (if enabled) (TO BE IMPLEMENTED)
redis-cli -u $REDIS_URL PING
```

---

## 11. Testing Plan

### 11.1 Unit Tests

```python
# tests/test_debug_cache.py
#
# ⚠️ EXAMPLE CODE (REFERENCE IMPLEMENTATION)
# These tests do not exist in the current codebase.
# This shows the intended structure; actual implementation may vary.

import pytest
from datetime import datetime, timedelta
from infrastructure.debug.debug_cache import DebugDataCache
from infrastructure.debug.debug_collector import DebugDataCollector


def test_debug_cache_set_and_get():
    """Test cache set and get"""
    cache = DebugDataCache(ttl_minutes=30, max_size=10)
    collector = DebugDataCollector("msg_123", "user1", "session1")

    cache.set("msg_123", collector)
    retrieved = cache.get("msg_123")

    assert retrieved is not None
    assert retrieved.request_id == "msg_123"


def test_debug_cache_expiration():
    """Test cache expiration"""
    cache = DebugDataCache(ttl_minutes=0, max_size=10)  # Immediate expiration
    collector = DebugDataCollector("msg_123", "user1", "session1")

    cache.set("msg_123", collector)
    retrieved = cache.get("msg_123")

    assert retrieved is None  # Expired


def test_debug_cache_lru_eviction():
    """Test LRU eviction when max_size reached"""
    cache = DebugDataCache(ttl_minutes=30, max_size=2)

    # Add 3 items (should evict first)
    for i in range(3):
        collector = DebugDataCollector(f"msg_{i}", "user1", "session1")
        cache.set(f"msg_{i}", collector)

    # First item should be evicted
    assert cache.get("msg_0") is None
    assert cache.get("msg_1") is not None
    assert cache.get("msg_2") is not None
```

### 11.2 Integration Tests

```python
# tests/test_debug_api.py
#
# ⚠️ EXAMPLE CODE (REFERENCE IMPLEMENTATION)
# These tests do not exist in the current codebase.
# This shows the intended structure; actual implementation may vary.

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from server.main import app
from infrastructure.debug.debug_cache import debug_cache
from infrastructure.debug.debug_collector import DebugDataCollector


client = TestClient(app)


def debug_url(request_id: str, user_id: str, session_id: str | None = None) -> str:
    """Internal-only: pass user_id (and optional session_id) via query params."""
    url = f"/api/v1/debug/{request_id}?user_id={user_id}"
    if session_id:
        url += f"&session_id={session_id}"
    return url


def test_get_debug_data_not_found():
    """Test getting non-existent debug data"""
    response = client.get(debug_url("nonexistent_id", "user1", "session1"))
    assert response.status_code == 404
    assert "not found or expired" in response.json()["detail"]


def test_get_debug_data_unauthorized():
    """Test accessing another user's debug data returns 403"""
    # Setup: Create debug data for user1
    collector = DebugDataCollector("msg_test_auth", "user1", "session1")
    collector.add_execution_log("test_step", 100)
    debug_cache.set("msg_test_auth", collector)

    try:
        # Act: Try to access as user2
        response = client.get(debug_url("msg_test_auth", "user2", "session2"))

        # Assert: Should return 403 Forbidden
        assert response.status_code == 403
        assert "belongs to a different user" in response.json()["detail"]
    finally:
        # Cleanup
        debug_cache.delete("msg_test_auth")


def test_get_debug_data_success():
    """Test owner can access their own debug data"""
    # Setup: Create debug data for user1
    collector = DebugDataCollector("msg_test_success", "user1", "session1")
    collector.add_execution_log("entity_extraction", 150, entities=["Nolan"])
    collector.add_trace_event("tool_call", {"tool": "local_search"})
    debug_cache.set("msg_test_success", collector)

    try:
        # Act: Access as user1 (owner)
        response = client.get(debug_url("msg_test_success", "user1", "session1"))

        # Assert: Should return 200 with debug data
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "msg_test_success"
        assert len(data["execution_log"]) == 1
        assert data["execution_log"][0]["step"] == "entity_extraction"
    finally:
        # Cleanup
        debug_cache.delete("msg_test_success")


@pytest.mark.asyncio
async def test_debug_data_flow():
    """Test complete debug data flow: stream → collect → retrieve"""
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        # 1. Initiate streaming request (debug mode)
        response = await ac.post(
            "/api/v1/chat/stream",
            json={
                "message": "Test query",
                "user_id": "flow_user",
                "session_id": "flow_session",
                "debug": True
            },
        )

        # 2. Parse SSE events and extract request_id
        request_id = None
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                import json
                event = json.loads(line[6:])
                if event.get("status") == "start":
                    request_id = event.get("request_id")
                    break

        assert request_id is not None, "request_id should be in start event"

        # 3. Get debug data via API
        debug_response = await ac.get(debug_url(request_id, "flow_user", "flow_session"))

        # 4. Verify data integrity
        assert debug_response.status_code == 200
        debug_data = debug_response.json()
        assert debug_data["request_id"] == request_id
        assert debug_data["user_id"] == "flow_user"
```

### 11.3 E2E Tests

```typescript
// frontend-react/tests/e2e/debugMode.spec.ts

import { test, expect } from '@playwright/test';

test('debug mode with streaming', async ({ page }) => {
  await page.goto('/chat');

  // Enable debug mode
  await page.check('[data-testid="debug-mode-toggle"]');

  // Enable streaming
  await page.check('[data-testid="streaming-toggle"]');

  // Send message
  await page.fill('[data-testid="chat-input"]', 'What movies did Nolan direct?');
  await page.click('[data-testid="send-button"]');

  // Wait for streaming to complete
  await page.waitForSelector('[data-testid="message-done"]');

  // Check for debug panel
  await page.click('[data-testid="debug-panel-toggle"]');
  await expect(page.locator('[data-testid="debug-panel"]')).toBeVisible();

  // Verify debug data
  await expect(page.locator('[data-testid="execution-logs"]')).toContainText('entity_extraction');
  await expect(page.locator('[data-testid="trace-events"]')).toBeVisible();
});
```

---

## 12. Performance Optimization

### 12.1 Memory Optimization

**Strategies**:
1. Limit cache size with LRU eviction
2. Data sampling (keep only last N trace events)
3. Compress large debug data structures

**Implementation**:
```python
class DebugDataCollector:
    def __init__(self, request_id: str, user_id: str, session_id: str):
        # ... existing code ...
        self.max_trace_events = 100

    def add_trace_event(self, event_type: str, data: Dict[str, Any]):
        """Keep only last N trace events"""
        if len(self.trace) >= self.max_trace_events:
            self.trace.pop(0)  # Remove oldest
        self.trace.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        })
```

### 12.2 Redis Cache Implementation (REQUIRED for Multi-Worker Production)

> [!IMPORTANT]
> **Redis cache implementation is REQUIRED for multi-worker production deployments**.
>
> This section provides a reference implementation for replacing the in-memory cache with Redis.
>
> **Use case**: Production deployments with `--workers N` or multiple pod instances.

**For production deployments with multiple workers** (future):

```python
# infrastructure/debug/debug_cache_redis.py
#
# ⚠️ PROPOSED CODE (FUTURE ENHANCEMENT)
# Redis-based cache for multi-process deployments (gunicorn, uwsgi, etc.)
# This returns Dict[str, Any], NOT DebugDataCollector (see NOTE below)

import redis
import json
from typing import Dict, Any, Optional
from datetime import timedelta


class RedisDebugDataCache:
    """
    Redis-based debug data cache (REQUIRED for multi-worker production).

    Thread-safety: Thread-safe (redis-py handles connection pooling).
    Persistence: Optional (Redis RDB/AOF).
    Scalability: Supports multi-process deployments.

    Use case: Production deployments with --workers N or multiple pod instances.
    """

    def __init__(self, redis_url: str, ttl_seconds: int = 1800):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            ttl_seconds: Time-to-live for debug data (default: 30 minutes)
        """
        self.client = redis.from_url(
            redis_url,
            decode_responses=True,  # ⚠️ REQUIRED: Return strings, not bytes
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self.ttl = ttl_seconds

    def set(self, request_id: str, collector: "DebugDataCollector"):
        """Store debug data in Redis"""
        key = f"debug:{request_id}"
        data = json.dumps(collector.to_dict())  # ⚠️ Serialize to dict first
        self.client.setex(key, self.ttl, data)

    def get(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get debug data from Redis.

        ⚠️ NOTE: Returns Dict[str, Any], NOT DebugDataCollector.

        Why not reconstruct the collector?
        - Collector is only needed for data collection (write path)
        - Retrieval is read-only and doesn't need collector methods
        - Simpler: No need to maintain from_dict() method
        - Flexibility: Can modify schema without breaking collector class
        """
        key = f"debug:{request_id}"
        data = self.client.get(key)

        if data:
            return json.loads(data)  # Return dict, not reconstructed collector

        return None

    def delete(self, request_id: str) -> bool:
        """Delete debug data from Redis"""
        key = f"debug:{request_id}"
        return bool(self.client.delete(key))
```

**Design Decision: Why return Dict instead of reconstructing Collector?**

| Approach | Pros | Cons |
|----------|------|------|
| **Return Dict** (this design) | ✅ Simpler, no from_dict() needed<br>✅ Schema flexibility<br>✅ Less coupling | ❌ No collector methods available |
| Reconstruct Collector | ✅ Access to collector methods | ❌ Requires from_dict()<br>❌ Schema rigidity<br>❌ More maintenance |

**Recommendation**: Use `Dict` for retrieval. The collector is only needed during data collection.

### 12.3 Compression

```python
import gzip
import json

def compress_debug_data(data: Dict) -> bytes:
    """Compress debug data"""
    json_str = json.dumps(data)
    return gzip.compress(json_str.encode())

def decompress_debug_data(compressed: bytes) -> Dict:
    """Decompress debug data"""
    json_str = gzip.decompress(compressed).decode()
    return json.loads(json_str)
```

---

## 13. Risks & Limitations

### 13.1 Known Risks

| Risk | Impact | Severity | Mitigation |
|------|--------|----------|------------|
| **🔴 Data leakage / Unauthorized access** | User A accesses User B's debug data via leaked/guessed `request_id`. Exposes PII, prompts, API keys, tool traces. | CRITICAL | 1. Internal-only deployment (localhost/VPN/firewall)<br>2. User ownership verification (user_id match)<br>3. Optional session validation (session_id match)<br>4. Data sanitization (redact PII, API keys, tokens)<br>5. Rate limiting (10 req/min)<br>6. Audit logging for failed access attempts |
| **🔴 PII leakage in debug data** | User queries contain PII (email, phone, SSN) returned in trace/logs | CRITICAL | 1. Data sanitization before return<br>2. Regex patterns for PII detection<br>3. Admin-only access to unsanitized data |
| **🟠 Memory leak** | Cache not cleaned, high memory usage | HIGH | Auto-expiration (TTL), max size limit, periodic cleanup |
| **🟠 Debug data loss** | Client disconnect before fetching | MEDIUM | Reasonable TTL (30 min), Redis for multi-worker persistence |
| **🟡 Concurrent access** | Race conditions in cache | MEDIUM | Thread-safe data structures (single-worker), Redis REQUIRED for multi-worker |
| **🟡 Large debug data** | Single entry consumes too much memory | MEDIUM | Limit trace/log counts (100/50), compress data |
| **🟡 Cache exhaustion DoS** | Attacker floods debug API to exhaust memory | MEDIUM | Max size limit (1000 entries), LRU eviction, rate limiting |

### 13.2 Limitations

1. **TTL constraint**: Debug data retained for 30 minutes by default (when implemented)
2. **Cache size**: Default max 1000 entries (configurable, when implemented)
3. **Trace events**: Not currently emitted by infrastructure layer (Phase 2 feature)
4. **Backward compatibility**: Non-debug mode behavior unchanged
5. **Multi-process deployments**: In-memory cache doesn't work across processes; requires Redis or single-process deployment

### 13.3 Future Improvements

- [ ] Debug data export (JSON/CSV)
- [ ] Real-time debug data subscription (WebSocket)
- [ ] Cross-session debug data comparison
- [ ] Debug data visualization (charts/timelines)
- [ ] Automated anomaly detection in traces
- [ ] Integration with observability platforms (Datadog, New Relic)

---

## Appendix

### A. Import Path Quick Reference

**⚠️ CRITICAL: This project uses `PYTHONPATH=${REPO}/backend` (see `scripts/dev.sh:50`)**

| Scenario | PYTHONPATH Setting | Import Format | Example |
|----------|-------------------|---------------|---------|
| **Project default (dev.sh)** | `${REPO}/backend` | `from <path>` (no backend.) | `from server.api.rest.v1.debug import ...` |
| **Repo-relative** | `${REPO}` | `from backend.<path>` | `from backend.server.api.rest.v1.debug import ...` |
| **Using `python -m`** | Depends on cwd | `python -m uvicorn server.main:app` | See commands below |

**Quick Checklist**:
- ✅ All imports in this document **do NOT** use `backend.` prefix
- ✅ This matches `scripts/dev.sh` which sets `PYTHONPATH=${ROOT}/backend`
- ⚠️ If you run code outside of dev.sh, adjust PYTHONPATH accordingly
- ⚠️ See section "Code Organization" for detailed structure diagram

**Running the Server**:
```bash
# ✅ CORRECT: Use the project's dev script (sets PYTHONPATH automatically)
bash scripts/dev.sh backend

# ✅ CORRECT: Run with uvicorn explicitly (requires PYTHONPATH=$PWD/backend)
export PYTHONPATH=${PYTHONPATH}:$(pwd)/backend
python -m uvicorn server.main:app --reload

# ❌ WRONG: -m doesn't accept :app syntax
python -m server.main:app  # This will fail!
```

**Common Mistakes**:
```python
# ✅ CORRECT: Matches dev.sh PYTHONPATH (no backend. prefix)
from server.api.rest.v1.debug import router
from infrastructure.debug.debug_cache import DebugDataCache

# ❌ WRONG: Includes backend. prefix (won't work with dev.sh)
from backend.server.api.rest.v1.debug import router
from backend.infrastructure.debug.debug_cache import DebugDataCache

# ❌ WRONG: Reverse dependency (application importing from server)
# In stream_handler.py or any application/ layer code:
from server.api.rest.v1.debug import debug_cache  # BAD! Creates reverse dependency
# ✅ CORRECT: Use infrastructure layer instead
from infrastructure.debug.debug_cache import debug_cache
```

---

### B. Code Quality Checklist

**⚠️ Common Pitfalls to Avoid When Implementing This Design**

This section summarizes critical code quality issues that MUST be avoided.

#### B.1 Python Mutable Default Arguments

**❌ WRONG - Shared mutable default**:
```python
class BadCollector:
    def __init__(self, items=[]):  # BUG: Same list reused!
        self.items = items

# Pydantic models:
class BadModel(BaseModel):
    items: List[str] = []  # BUG: Shared across instances!
```

**✅ CORRECT**:
```python
class GoodCollector:
    def __init__(self, items=None):
        self.items = items if items is not None else []

# Pydantic models:
class GoodModel(BaseModel):
    items: List[str] = Field(default_factory=list)  # Calls list() each time
```

**Why it matters**: Python evaluates default arguments once at function definition time. All instances share the same object, leading to data corruption.

#### B.2 LRU Cache Implementation

**❌ WRONG - Arbitrary key selection**:
```python
class BadLRU:
    def evict_if_full(self):
        if len(self._cache) >= self._max_size:
            # BUG: min() returns arbitrary key, not oldest!
            oldest = min(self._cache.keys())
            del self._cache[oldest]
```

**✅ CORRECT - OrderedDict-based LRU**:
```python
from collections import OrderedDict

class GoodLRU:
    def __init__(self):
        self._cache = OrderedDict()

    def evict_if_full(self):
        if len(self._cache) >= self._max_size:
            # CORRECT: Remove first item (oldest in OrderedDict)
            self._cache.popitem(last=False)

    def access(self, key):
        if key in self._cache:
            # Mark as recently used
            self._cache.move_to_end(key)
```

**Why it matters**: Python dicts (before 3.7) and `min()` don't preserve insertion order. OrderedDict with `move_to_end()` + `popitem(last=False)` is the correct LRU pattern.

#### B.3 Thread Safety

**❌ WRONG - Race conditions**:
```python
class BadCache:
    def get_and_delete(self, key):
        if key in self._cache:  # Thread A checks
            # ← Context switch: Thread B also checks
            return self._cache.pop(key)  # Thread A pops
            # Thread B now gets KeyError!
```

**✅ CORRECT - Thread-safe with locks**:
```python
import threading

class GoodCache:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def get_and_delete(self, key):
        with self._lock:  # Atomic operation
            if key in self._cache:
                return self._cache.pop(key)
        return None
```

**Why it matters**: In multi-threaded environments (gunicorn, uwsgi), race conditions can cause data corruption, KeyErrors, or inconsistent state.

#### B.4 Redis Bytes vs Strings

**❌ WRONG - Bytes returned**:
```python
client = redis.from_url("redis://localhost:6379")
data = client.get("key")
print(data)  # b'{"value": "123"}' - Bytes!
json.loads(data)  # ERROR: expects str, not bytes
```

**✅ CORRECT - Decode responses**:
```python
client = redis.from_url(
    "redis://localhost:6379",
    decode_responses=True  # ← REQUIRED: Auto-decode bytes to str
)
data = client.get("key")
print(data)  # '{"value": "123"}' - String!
json.loads(data)  # Works correctly
```

**Why it matters**: Redis stores bytes. Without `decode_responses=True`, you get bytes objects that break JSON parsing and string operations.

#### B.5 Debug API Exposure (Internal-only)

**Rule**: The debug API must be treated as **internal-only** in this design (no auth in scope).

**Minimum expectation**:
- Do not bind publicly; keep behind localhost/VPN/firewall.
- Always enforce `user_id` ownership checks before returning debug payloads.
- Sanitize secrets/PII in all returned debug fields.

---

### C. Related Documentation

**External References**:
- [SSE Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [React Streaming with fetch](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API)
- [Pydantic Field Validation](https://docs.pydantic.dev/latest/concepts/fields/)

**Internal Documentation**:
- Frontend Integration: See `frontend-react/README.md`
- Testing Guide: See `test/README.md`
- API Testing: See `test/e2e/README.md`

### D. Migration Guide

**For existing deployments**:

1. Update backend code to new version
2. Deploy new debug API endpoints
3. Update frontend to use new streaming handler
4. Enable debug mode + streaming in UI
5. Monitor cache memory usage
6. Gradual rollout (canary deployment)

**Rollback plan**:
- Feature flag to disable new debug API
- Fallback to non-streaming debug mode
- Cache cleanup script

### E. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2025-01-22 | Initial design document |

### F. Review Notes

- [ ] Security review (authentication/authorization)
- [ ] Performance review (cache sizing, TTL)
- [ ] Frontend review (UI/UX for debug panel)
- [ ] Backend review (API design, error handling)
- [ ] Testing review (coverage, E2E scenarios)

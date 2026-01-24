# Langfuse 优化方案

> **版本**: 1.1.3  
> **更新时间**: 2025-01-23  
> **状态**: 待实施  
> **目标**: 提升 Langfuse 可观测性覆盖度和数据质量（确保“单次请求单条 Trace”，并覆盖路由/检索/生成/错误）

## 目录

- [1. 概述](#1-概述)
- [2. SDK/接口对齐（重要）](#2-sdk接口对齐重要)
- [3. 上下文传递/并发模型（关键难点）](#3-上下文传递并发模型关键难点)
- [4. 当前问题分析（结合代码）](#4-当前问题分析结合代码)
- [5. 优化方案（落地步骤）](#5-优化方案落地步骤)
- [6. 埋点地图（真实文件/函数映射）](#6-埋点地图真实文件函数映射)
- [7. 数据规范/脱敏与体量预算](#7-数据规范脱敏与体量预算)
- [8. 验收标准 + 测试方法](#8-验收标准--测试方法)
- [9. 开关/采样/失败降级](#9-开关采样失败降级)
- [10. 实施优先级](#10-实施优先级)
- [11. 预期收益](#11-预期收益)

---

## 1. 概述

### 1.1 背景

当前系统已初步集成 Langfuse，主要实现了：
- ✅ HTTP 入口创建 Trace：`backend/server/api/rest/v1/chat_stream.py:46`
- ✅ 生成侧函数装饰器：`backend/infrastructure/llm/completion.py:49`
- ✅ LangChain CallbackHandler：`backend/infrastructure/observability/langfuse_handler.py:56`

但目前关键步骤并没有形成“同一条 trace 下的完整树状链路”，Langfuse 的核心价值（可追踪、可分析、可定位瓶颈）没有发挥出来。

### 1.2 优化目标（对齐可落地的验收）

1) 单次 `/api/v1/chat/stream` 只产生 1 条 Langfuse Trace（根 trace id = request_id）  
2) 该 trace 下至少包含：`route_decision` → `rag_retrieval`（含每个 spec 子 span）→ `generation`  
3) 错误/超时可在 Langfuse UI 中筛选（使用 tags / observation level / status_message，而非 “trace.status”）  
4) 对性能优化有帮助：每步耗时、检索结果规模、TTFT（可选）可见

---

## 2. SDK/接口对齐（重要）⚠️

> 本节用于修正“实现时容易写错”的 API 用法，避免落地阶段反复返工。以下以当前仓库依赖的 Langfuse Python SDK 为准。

### 2.1 `Trace.update()` 不支持 `status=...`

错误示例（不要这样写）：

```python
langfuse_trace.update(output=final_output, status="success")  # ❌ Trace.update 没有 status 参数
```

正确做法：
- Trace 层用 `tags`/`metadata` 标记结果（便于 UI 过滤）
- Span/Generation 层用 `level="ERROR"` 和 `status_message="..."` 标记失败节点

```python
# ✅ Trace：用 tags/metadata 标记（便于 UI 过滤）
trace.update(tags=["error"], metadata={"error_type": "timeout", "ok": False})

# ✅ Span：用 level/status_message 标记（更语义化）
span.end(level="ERROR", status_message="timeout after 8s", output={"error": "timeout"})
```

### 2.2 `langfuse.get_current_observation()` 不存在

文档/代码里不要依赖 `langfuse.get_current_observation()` 这类 API。若使用装饰器上下文，应使用：

```python
from langfuse.decorators import langfuse_context

trace_id = langfuse_context.get_current_trace_id()
observation_id = langfuse_context.get_current_observation_id()
langfuse_context.update_current_observation(metadata={"k": "v"})
langfuse_context.update_current_trace(tags=["x"], metadata={"k": "v"})
```

注意：`langfuse_context.*` 仅在 `@observe` 管理的调用栈内才有意义；跨线程/跨库回调时不要强依赖它。

### 2.3 Span/Generation 需要显式 `end()`

`StatefulSpanClient` / `StatefulGenerationClient` 需要 `end()` 才算闭合；并且 **不支持** `with ... as ...` 的 context manager 语法。

```python
span = trace.span(name="retrieval")
try:
    span.update(metadata={"count": 10})
finally:
    span.end()
```

### 2.4 LangChain 回调要绑定到现有 trace/span

Langfuse 的 `CallbackHandler` 支持把 LangChain 的 LLM events 绑定到指定父对象：

```python
from langfuse.callback import CallbackHandler

cb = CallbackHandler(
    public_key=...,
    secret_key=...,
    host=...,
    stateful_client=trace_or_span,  # ✅ 关键
    update_stateful_client=False,
    user_id=user_id,
    session_id=session_id,
)
chain.invoke(payload, config={"callbacks": [cb]})
```

---

## 3. 上下文传递/并发模型（关键难点）⚠️

### 3.1 本项目的真实并发/跨线程点（结合代码）

- 检索在后台线程执行：`backend/infrastructure/rag/rag_manager.py`（`asyncio.to_thread(_invoke)`）
- 检索并发 fanout：`backend/infrastructure/streaming/chat_stream_executor.py`（`create_task` + `as_completed`）

结论：不要把“trace 不分裂”寄托在隐式上下文上；要用“显式 parent 绑定”。

### 3.2 本项目 trace 分裂的主要原因

当前根 trace 在 HTTP 层手动创建：`backend/server/api/rest/v1/chat_stream.py:46`；但：
- 生成侧使用 `@langfuse_observe`：`backend/infrastructure/llm/completion.py:49`（未绑定到 HTTP 层 trace）
- LangChain CallbackHandler 未设置 `stateful_client`：`backend/infrastructure/observability/langfuse_handler.py:56`

因此会出现 “HTTP 有一条 trace，LLM 生成又有另一条 trace” 的情况。

### 3.3 推荐落地模式（适配本项目）

原则：不要依赖“隐式上下文”；用“显式父子关系”。

- 根 trace：在 HTTP 层创建（现状已做）
- 路由/检索/聚合：用 `trace.span(...)` 显式创建 span
- LLM：用 `CallbackHandler(stateful_client=trace_or_span)` 把 LangChain generation 挂回这条 trace
- 后台线程：如需细分 span，可用 `langfuse.span(trace_id=..., parent_observation_id=...)` 在线程内创建

---

## 4. 当前问题分析（结合代码）

### 4.1 Trace 不连贯（根 trace 与 LLM trace 分裂）

- 根 trace 创建在：`backend/server/api/rest/v1/chat_stream.py:46`
- 生成侧 `@langfuse_observe` 独立运行：`backend/infrastructure/llm/completion.py:49`
- CallbackHandler 未绑定到现有 trace：`backend/infrastructure/observability/langfuse_handler.py:56`

### 4.2 路由/检索只有 debug cache，没有 Langfuse span

当前“路由/计划/检索摘要/性能统计”主要在 debug cache（execution_log / route_decision / rag_runs）：
- 路由与编排：`backend/application/chat/handlers/stream_handler.py:1`
- 并发检索与检索摘要：`backend/infrastructure/streaming/chat_stream_executor.py:1`

Langfuse 里缺少：
- 路由为什么这么选（置信度、fallback）
- 检索每步耗时、结果规模、错误点

### 4.3 在线检索 embedding / Neo4j vector query 未被追踪

实际在线向量检索路径：
- embedding：`backend/graphrag_agent/search/tool/base.py:151`（`self.embeddings.embed_query(query)`）
- 向量检索（Neo4j index）：`backend/graphrag_agent/search/tool/base.py:155`（`db.index.vector.queryNodes`）

### 4.4 错误/超时没有统一“可过滤”标记

目前 trace 主要只 `update(output=...)`：`backend/server/api/rest/v1/chat_stream.py:160`  
错误/超时大多只进 debug execution_log；Langfuse UI 很难筛选 error/timeout 类请求。

### 4.5 悬空导出（技术债）

`backend/infrastructure/observability/langfuse_handler.py:152` 的 `__all__` 含 `get_langfuse_async_openai`，但当前文件并无实现（需移除或实现）。

---

## 5. 优化方案（落地步骤）

### 5.1 Phase 1（必须）：把 LLM generation 挂回根 trace

目标：解决“trace 分裂”，让 Langfuse UI 至少能看到 “chat_stream → LLM generation”。

落地要点：
- 在 `get_langfuse_callback()` 支持传入 `stateful_client`（trace 或 span）
- 在生成侧创建 callback 时传入 `stateful_client=<http_root_trace>`
- 或者把生成逻辑放在根 trace/span 的生命周期内创建 generation

### 5.2 Phase 2（必须）：为路由/检索/聚合创建 spans（只打关键字段）

目标：Langfuse 中能看到每步耗时和规模，定位瓶颈。

建议 span 粒度：
- `route_decision`：kb_prefix、worker_name、routing_ms
- `rag_plan`：plan spec 列表、total_runs
- `rag_retrieval`：每个 spec 一个子 span（agent_type、timeout_s、retrieval_count、error）
- `retrieval_aggregation`：聚合后 retrieval_count、是否 fallback、是否 error

### 5.3 Phase 3（增强）：embedding / Neo4j query / TTFT

- embedding：维度、耗时、输入长度（截断）
- Neo4j vector query：index_name、limit、返回数量、耗时
- TTFT：`completion_start_time`（仅当你们确实需要 TTFT 分析）

### 5.4 Phase 4（产品能力）：Scores / Datasets / Prompt 版本 / Release

- Scores：前端加“好/坏/评分/反馈”按钮，后端用 trace_id 上报 `score`
- Datasets/Evals：评测脚本把 offline run 写入 dataset
- Prompt 版本：把关键 prompt 作为 Langfuse prompt 管理（可选）
- Release：后端从 env 注入 `release` 便于对比部署版本

---

## 6. 埋点地图（真实文件/函数映射）

| 目标操作 | Span/Observation 名称 | 主要落点 | 推荐字段（metadata/input/output） |
|---------|------------------------|---------|-----------------------------------|
| HTTP 请求根 | `chat_stream`（trace） | `backend/server/api/rest/v1/chat_stream.py` | user_id/session_id/kb_prefix/agent_type |
| 路由决策 | `route_decision`（span） | `backend/application/chat/handlers/stream_handler.py` | routing_ms、worker_name、confidence、kb_prefix |
| RAG 计划 | `rag_plan`（span） | `backend/infrastructure/streaming/chat_stream_executor.py` | plan、total_runs |
| 单个检索 spec | `rag_retrieval_spec`（span） | `backend/infrastructure/rag/rag_manager.py` | agent_type、timeout_s、retrieval_count、error |
| 生成 | `generation`（LangChain callback 或 generation） | `backend/infrastructure/llm/completion.py` | model、ttft_ms（可选）、tokens/cost（自动/半自动） |
| Neo4j 向量检索 | `vector_search`（span） | `backend/graphrag_agent/search/tool/base.py` | index_name、limit、returned_count、latency_ms |

---

## 7. 数据规范/脱敏与体量预算

建议默认规则（可写成代码约束）：
- 不上传全量 `retrieval_results` 原文；只上传统计 + 少量 preview（长度截断）
- 不在 metadata 存放用户隐私/密钥/token；对 prompt/response 做长度限制
- 对错误栈：只存 `type/message`，不要全量 traceback（避免泄漏路径/敏感信息）
- 成本控制：debug 模式可更详细；非 debug 保持轻量 spans

---

## 8. 验收标准 + 测试方法

### 8.1 验收标准（DoD）

- 发起一次 `/api/v1/chat/stream`，Langfuse UI 中只有 1 条 trace（trace.id = request_id）
- trace 下至少包含 `route_decision` + `rag_retrieval` + LLM generation（或等价层级）
- 人为制造超时/错误时，该 trace 带 `tags=["error"]` 或对应 span `level=ERROR`

### 8.2 手工验证

1) 启动 Langfuse（docker）并确认 `/api/public/health` OK  
2) 从前端发一次聊天请求（确保 `LANGFUSE_ENABLED=true`）  
3) 在 Langfuse UI → Traces 中按 request_id 搜索并检查树状结构

### 8.3 脚本验证（辅助）

- `backend/langfuse_diag.py`：创建 trace 并验证可查询（验证基础链路）

---

## 9. 开关/采样/失败降级

建议：
- `LANGFUSE_ENABLED=false` 时完全不影响主链路（fail-open）
- 提供采样率（例如 `LANGFUSE_SAMPLE_RATE=0.1`）以降低生产开销
- flush 策略：请求结束 flush（或后台批量 flush），避免每 token flush
- Langfuse 不可用时：记录一次 warning 日志即可，不要让 SSE 失败

---

## 10. 实施优先级

| Phase | 目标 | 必做项 |
|------|------|-------|
| Phase 1 | 解决 trace 分裂 | CallbackHandler 绑定 stateful_client；单请求单 trace |
| Phase 2 | 关键 spans | route/retrieval/generation span 与错误标记 |
| Phase 3 | 深入性能 | embedding/neo4j spans + TTFT（可选） |
| Phase 4 | 产品能力 | scores/datasets/prompt/release（按需） |

---

## 11. 预期收益

- 线上问题定位：从“只能看 debug cache / 日志”升级为 Langfuse UI 一次请求全链路
- 性能优化：明确瓶颈在路由/检索/生成哪一步，能做数据驱动优化
- 成本监控：逐步补齐 tokens/cost（尤其对多模型对比有用）

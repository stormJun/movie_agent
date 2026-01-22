# Agent 系统（v3 strict）

本项目的 Agent 在 v3 strict 阶段被收敛为 **retrieve-only**：Agent 只负责检索并返回结构化证据；最终答案生成、流式输出、会话状态与长期记忆都由服务侧负责。

## 1. 位置与边界

- core：`backend/graphrag_agent/agents/`
- 服务侧编排与流式生成：`backend/application/`、`backend/infrastructure/rag/`、`backend/infrastructure/streaming/`

约束：
- Agent 不管理会话状态（不保存对话历史）
- Agent 不负责生成最终答案（只产出 evidence/trace）

## 2. 统一接口

所有 v3 strict Agent 统一暴露：

```python
def retrieve_with_trace(self, query: str, thread_id: str = "default") -> dict:
    """Return structured evidence for service-side aggregation/generation."""
```

其中：
- `thread_id` 由服务侧传入（通常等于 `session_id`），用于 trace 关联与日志追踪

## 3. Agent 类型（示例）

典型实现位于 `backend/graphrag_agent/agents/`：
- `naive_rag_agent.py`：向量检索为主
- `graph_agent.py`：图谱结构化检索
- `hybrid_agent.py`：多策略融合检索
- `deep_research_agent.py`：多步检索/反思式检索
- `fusion_agent.py`：多智能体编排（Plan-Execute-Report），内部复用 multi_agent 模块

## 4. 生命周期与实例管理（服务侧）

Agent 的常驻实例池化由服务侧承担（而不是 core 自己管理），参考：
- `backend/infrastructure/agents/rag_factory/`

推荐的实例 key 约定：
- `{kb_prefix}:{agent_type}:{agent_mode}`（strict 下 `agent_mode` 固定为 `retrieve_only`）

## 5. 与 Router-Worker 的关系

- Router 决策输出 `worker_name`
- RAG 执行器按 `worker_name` 分发到对应的检索 Agent
- 生成器（流式/非流式）消费聚合后的 evidence，负责产出最终回答与事件流


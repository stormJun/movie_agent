# AgentManager 类功能分析

> 注意：本文基于旧版接口与 legacy 服务（`backend/application/services/chat_service.py` 等），当前已下线；仅供历史参考。

**文件位置**: `backend/application/services/agent_service.py`

---

## 🎯 核心职责

`AgentManager` 是一个 **Agent 实例池管理器**，负责：

1. ✅ **Agent 类型注册** - 管理所有可用的 Agent 类型
2. ✅ **实例池管理** - 为每个会话创建和维护独立的 Agent 实例
3. ✅ **线程安全** - 使用锁保证并发访问安全
4. ✅ **会话隔离** - 每个 session_id 拥有独立的 Agent 实例
5. ✅ **历史清理** - 清除特定会话的聊天历史
6. ✅ **资源管理** - 关闭所有 Agent 资源

---

## 📊 类结构图

```
AgentManager
├── __init__()              # 初始化：注册 Agent 类、创建实例池、初始化锁
├── get_agent()            # 获取/创建 Agent 实例（核心方法）
├── clear_history()        # 清除会话历史
└── close_all()            # 关闭所有 Agent 资源
```

---

## 🔍 核心方法详解

### 1. `__init__()` - 初始化

```python
def __init__(self):
    # 1. 导入所有 Agent 类
    from backend.graphrag_agent.agents.graph_agent import GraphAgent
    from backend.graphrag_agent.agents.hybrid_agent import HybridAgent
    from backend.graphrag_agent.agents.naive_rag_agent import NaiveRagAgent
    from backend.graphrag_agent.agents.deep_research_agent import DeepResearchAgent
    from backend.graphrag_agent.agents.fusion_agent import FusionGraphRAGAgent

    # 2. 注册 Agent 类型映射
    self.agent_classes = {
        "graph_agent": GraphAgent,
        "hybrid_agent": HybridAgent,
        "naive_rag_agent": NaiveRagAgent,
        "deep_research_agent": DeepResearchAgent,
        "fusion_agent": FusionGraphRAGAgent,
    }

    # 3. 创建实例池（空字典）
    self.agent_instances = {}

    # 4. 创建线程锁（RLock 支持重入）
    self.agent_lock = threading.RLock()
```

**作用**:
- 📝 注册 5 种 Agent 类型
- 🗄️ 初始化空的实例池
- 🔒 创建线程锁保证并发安全

---

### 2. `get_agent()` - 获取 Agent 实例 ⭐

```python
def get_agent(self, agent_type: str, session_id: str = "default"):
    """
    获取指定类型的Agent，对每个会话使用独立实例

    Args:
        agent_type: Agent类型 (graph_agent/hybrid_agent/...)
        session_id: 会话ID

    Returns:
        Agent实例
    """
    # 1. 校验 Agent 类型
    if agent_type not in self.agent_classes:
        raise ValueError(f"未知的agent类型: {agent_type}")

    # 2. 生成实例唯一 key: "agent_type:session_id"
    instance_key = f"{agent_type}:{session_id}"

    # 3. 线程安全地获取/创建实例
    with self.agent_lock:
        if instance_key not in self.agent_instances:
            # 创建新的 Agent 实例
            self.agent_instances[instance_key] = self.agent_classes[agent_type]()

        return self.agent_instances[instance_key]
```

**核心设计**: **会话隔离 + 实例复用**

#### 实例池结构示例

```python
agent_instances = {
    "hybrid_agent:session-001": <HybridAgent 实例>,
    "hybrid_agent:session-002": <HybridAgent 实例>,
    "deep_research_agent:session-001": <DeepResearchAgent 实例>,
    "graph_agent:session-003": <GraphAgent 实例>,
}
```

#### 工作流程

```
用户请求 (agent_type="hybrid_agent", session_id="abc123")
    │
    ▼
生成 instance_key = "hybrid_agent:abc123"
    │
    ▼
检查实例池
    │
    ├─ 存在 ─────────────▶ 直接返回现有实例
    │
    └─ 不存在 ──▶ 创建新实例 ──▶ 加入实例池 ──▶ 返回实例
```

**优点**:
1. ✅ **会话隔离**: 每个用户会话有独立的 Agent 实例，避免上下文混乱
2. ✅ **资源复用**: 同一会话重复请求时复用实例，避免重复初始化
3. ✅ **线程安全**: 使用锁保护并发访问

---

### 3. `clear_history()` - 清除会话历史

```python
def clear_history(self, session_id: str) -> Dict:
    """
    清除特定会话的聊天历史

    工作流程:
    1. 遍历该会话的所有 Agent 实例
    2. 获取每个 Agent 的 memory
    3. 删除消息历史（保留前 2 条）
    """
    with self.agent_lock:
        for agent_type in self.agent_classes.keys():
            instance_key = f"{agent_type}:{session_id}"
            if instance_key in self.agent_instances:
                agent = self.agent_instances[instance_key]
                config = {"configurable": {"thread_id": session_id}}

                # 获取消息历史
                memory_content = agent.memory.get(config)
                if memory_content is None:
                    continue

                messages = memory_content["channel_values"]["messages"]

                # 删除消息（保留前 2 条）
                for message in reversed(messages):
                    if len(messages) <= 2:
                        break
                    agent.graph.update_state(
                        config,
                        {"messages": RemoveMessage(id=message.id)}
                    )

    return {"status": "success", "remaining_messages": "已清除会话历史"}
```

**关键点**:
- 🗑️ 只删除该会话的历史，不影响其他会话
- 📝 保留前 2 条消息（可能是系统提示词）
- 🔄 使用 LangGraph 的 `RemoveMessage` 机制

---

### 4. `close_all()` - 关闭所有资源

```python
def close_all(self):
    """关闭所有Agent资源"""
    with self.agent_lock:
        for instance_key, agent in self.agent_instances.items():
            try:
                agent.close()
                print(f"已关闭 {instance_key} 资源")
            except Exception as e:
                print(f"关闭 {instance_key} 资源时出错: {e}")

        # 清空实例池
        self.agent_instances.clear()
```

**用途**: 服务器关闭时释放所有 Agent 资源

---

## 🔄 调用链路

### 示例 1: 用户发送聊天请求

```
1. 用户请求到达
   ↓
2. ChatService.process_chat(agent_type="hybrid_agent", session_id="abc123")
   ↓
3. agent_manager.get_agent("hybrid_agent", "abc123")
   ↓
4. 检查实例池
   ├─ 首次请求 → 创建新实例 → agent_instances["hybrid_agent:abc123"] = HybridAgent()
   └─ 后续请求 → 直接返回 agent_instances["hybrid_agent:abc123"]
   ↓
5. 使用返回的 Agent 实例处理请求
   selected_agent.ask(message, thread_id=session_id)
```

### 示例 2: 多用户并发场景

```
用户 A (session_id="001") + 用户 B (session_id="002")
同时请求 hybrid_agent
    ┌─────────────────┐         ┌─────────────────┐
    │  Session: 001   │         │  Session: 002   │
    └────────┬────────┘         └────────┬────────┘
             │                           │
             ▼                           ▼
    get_agent("hybrid", "001")  get_agent("hybrid", "002")
             │                           │
             ▼                           ▼
    instance_key =              instance_key =
    "hybrid_agent:001"          "hybrid_agent:002"
             │                           │
             └────────┬──────────────────┘
                      ▼
            【线程锁保护并发创建】
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
   创建实例 A                  创建实例 B
   HybridAgent()              HybridAgent()
         │                         │
         └────────────┬────────────┘
                      ▼
            【实例池状态】
    {
      "hybrid_agent:001": <HybridAgent A>,
      "hybrid_agent:002": <HybridAgent B>
    }
```

**关键**: 两个用户拥有完全独立的 Agent 实例，互不干扰！

---

## 🎯 设计优势

### 1. 会话隔离

```python
# 用户 A 的请求
agent_a = agent_manager.get_agent("hybrid_agent", session_id="user_a")
agent_a.ask("什么是 GraphRAG?")  # 上下文保存在 user_a 的 memory

# 用户 B 的请求
agent_b = agent_manager.get_agent("hybrid_agent", session_id="user_b")
agent_b.ask("推荐电影")  # 上下文保存在 user_b 的 memory

# agent_a != agent_b，完全独立
```

### 2. 实例复用

```python
# 第 1 次请求: 创建新实例
agent1 = agent_manager.get_agent("hybrid_agent", session_id="abc")
# 实例池: {"hybrid_agent:abc": <HybridAgent 实例>}

# 第 2 次请求: 复用实例
agent2 = agent_manager.get_agent("hybrid_agent", session_id="abc")
# agent1 is agent2  → True (同一个对象)

# 好处:
# ✅ 保留会话上下文（Memory）
# ✅ 避免重复初始化（节省资源）
# ✅ 保持缓存状态
```

### 3. 线程安全

```python
# 并发场景
Thread-1: agent_manager.get_agent("hybrid", "session1")
Thread-2: agent_manager.get_agent("hybrid", "session2")
Thread-3: agent_manager.get_agent("graph", "session1")

# 使用 threading.RLock() 保护
with self.agent_lock:
    # 临界区代码
    if instance_key not in self.agent_instances:
        self.agent_instances[instance_key] = ...
```

---

## 📈 实例池增长示例

```python
# 初始状态
agent_instances = {}

# 请求 1: user_a 使用 hybrid_agent
get_agent("hybrid_agent", "user_a")
agent_instances = {
    "hybrid_agent:user_a": <HybridAgent>
}

# 请求 2: user_a 使用 deep_research_agent
get_agent("deep_research_agent", "user_a")
agent_instances = {
    "hybrid_agent:user_a": <HybridAgent>,
    "deep_research_agent:user_a": <DeepResearchAgent>
}

# 请求 3: user_b 使用 hybrid_agent
get_agent("hybrid_agent", "user_b")
agent_instances = {
    "hybrid_agent:user_a": <HybridAgent>,
    "deep_research_agent:user_a": <DeepResearchAgent>,
    "hybrid_agent:user_b": <HybridAgent>
}

# 请求 4: user_a 再次使用 hybrid_agent (复用)
get_agent("hybrid_agent", "user_a")
# 实例池不变，直接返回已有实例
```

---

## ⚠️ 潜在问题

### 1. 内存泄漏风险

**问题**: 实例池会持续增长，不会自动清理

```python
# 用户访问 1000 个不同的 session
for i in range(1000):
    agent_manager.get_agent("hybrid_agent", f"session_{i}")

# 实例池会有 1000 个实例，占用大量内存
```

**解决方案**:
- 定期清理长时间未使用的实例
- 设置最大实例数限制
- 使用 LRU 缓存策略

### 2. 会话过期机制缺失

**当前**: 会话永不过期，除非手动调用 `clear_history()`

**改进建议**:
```python
# 添加过期时间戳
self.agent_instances = {
    "hybrid_agent:abc": {
        "instance": <HybridAgent>,
        "last_access": 1735454400,  # Unix 时间戳
    }
}

# 定期清理
def cleanup_expired_agents(self, max_idle_seconds=3600):
    """清理超过 1 小时未使用的 Agent"""
    current_time = time.time()
    with self.agent_lock:
        expired_keys = [
            key for key, data in self.agent_instances.items()
            if current_time - data["last_access"] > max_idle_seconds
        ]
        for key in expired_keys:
            self.agent_instances[key]["instance"].close()
            del self.agent_instances[key]
```

---

## 🔗 与其他组件的关系

```
ChatService (backend/application/services/chat_service.py)
    │
    ├─ 调用 agent_manager.get_agent(agent_type, session_id)
    │       ↓
    │   AgentManager 返回 Agent 实例
    │       ↓
    └─ 调用 agent.ask(message, thread_id=session_id)
            ↓
        BaseAgent (backend/graphrag_agent/agents/base.py)
            ├─ LangGraph workflow
            ├─ Memory (MemorySaver)
            └─ Tools (Search, Graph, etc.)
```

---

## 📝 总结

### AgentManager 的核心价值

1. **🎯 单一职责**: 专注于 Agent 实例的生命周期管理
2. **🔒 线程安全**: 使用锁保证并发场景下的正确性
3. **🚀 性能优化**: 实例复用避免重复初始化
4. **🔐 会话隔离**: 每个用户会话拥有独立的 Agent 实例
5. **🧹 资源管理**: 提供统一的资源清理接口

### 关键设计

```python
instance_key = f"{agent_type}:{session_id}"
```

这个简单的 key 设计实现了：
- ✅ Agent 类型区分
- ✅ 会话隔离
- ✅ 快速查找

---

**文件**: `backend/application/services/agent_service.py`
**行数**: 211 行
**核心方法**: `get_agent()` (34-56 行)
**作者**: GraphRAG Team

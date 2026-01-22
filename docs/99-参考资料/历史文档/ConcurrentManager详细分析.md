# ConcurrentManager 类详细分析

> 注意：本文基于旧版接口与 legacy 服务（`backend/application/services/chat_service.py` 等），当前已下线；仅供历史参考。

**文件位置**: `backend/infrastructure/utils/concurrent.py`

---

## 🎯 核心职责

`ConcurrentManager` 是一个 **分布式锁管理器**，用于：

1. ✅ **并发控制** - 防止同一会话的重复请求
2. ✅ **锁超时清理** - 自动释放长时间未释放的锁
3. ✅ **非阻塞获取** - 快速失败，避免请求堆积
4. ✅ **时间戳追踪** - 记录锁的创建和更新时间

---

## 📊 类结构

```python
ConcurrentManager
├── __init__()                  # 初始化锁池和配置
├── get_lock()                  # 获取/创建锁对象
├── try_acquire_lock()          # 尝试获取锁（核心方法）
├── release_lock()              # 释放锁
├── update_timestamp()          # 更新时间戳
└── cleanup_expired_locks()     # 清理过期锁
```

---

## 🔍 详细实现分析

### 1. 初始化

```python
def __init__(self, timeout_seconds=300, lock_wait_timeout=10):
    # 1. 锁池：存储所有锁对象
    self.locks: Dict[str, threading.Lock] = {}

    # 2. 时间戳池：记录每个锁的最后活跃时间
    self.timestamps: Dict[str, float] = {}

    # 3. 锁超时时间（默认 5 分钟）
    self.timeout_seconds = timeout_seconds

    # 4. 获取锁时的最大等待时间（默认 10 秒）
    self.lock_wait_timeout = lock_wait_timeout
```

**数据结构示例**:

```python
locks = {
    "session_001_chat": <threading.Lock object>,
    "session_002_chat": <threading.Lock object>,
    "session_001_feedback": <threading.Lock object>,
}

timestamps = {
    "session_001_chat": 1735454400.123,  # Unix 时间戳
    "session_002_chat": 1735454450.456,
    "session_001_feedback": 1735454500.789,
}
```

---

### 2. 获取锁对象 `get_lock()`

```python
def get_lock(self, key: str) -> threading.Lock:
    """
    获取或创建锁对象

    Args:
        key: 锁键名（如 "session_001_chat"）

    Returns:
        threading.Lock: 线程锁对象
    """
    if key not in self.locks:
        # 首次访问：创建新锁
        self.locks[key] = threading.Lock()
        self.timestamps[key] = time.time()

    return self.locks[key]
```

**特点**:
- ✅ 懒加载：只在需要时创建锁
- ✅ 自动记录创建时间

---

### 3. 尝试获取锁 `try_acquire_lock()` ⭐ **核心方法**

```python
def try_acquire_lock(self, key: str, wait: bool = False) -> bool:
    """
    尝试获取锁

    Args:
        key: 锁键名
        wait: 是否等待锁释放

    Returns:
        bool: 是否成功获取锁
    """
    lock = self.get_lock(key)

    if wait:
        # 等待模式：最多等待 lock_wait_timeout 秒
        return lock.acquire(blocking=True, timeout=self.lock_wait_timeout)
    else:
        # 非等待模式：立即返回（默认模式）
        return lock.acquire(blocking=False)
```

#### 两种模式对比

| 模式 | blocking | timeout | 行为 |
|------|----------|---------|------|
| **非等待模式** | `False` | 无 | 立即返回 True/False |
| **等待模式** | `True` | 10 秒 | 等待最多 10 秒，超时返回 False |

#### threading.Lock.acquire() 参数详解

```python
lock.acquire(blocking=True, timeout=-1)
```

**参数说明**:

- **blocking**:
  - `True`: 阻塞模式，如果锁已被占用，会等待
  - `False`: 非阻塞模式，立即返回

- **timeout** (仅在 blocking=True 时有效):
  - `-1`: 无限等待
  - `> 0`: 等待指定秒数
  - 超时后返回 `False`

**返回值**:
- `True`: 成功获取锁
- `False`: 未能获取锁

---

### 4. 释放锁 `release_lock()`

```python
def release_lock(self, key: str) -> None:
    """
    释放锁

    Args:
        key: 锁键名
    """
    if key in self.locks and self.locks[key].locked():
        self.locks[key].release()
```

**安全检查**:
1. 检查锁是否存在
2. 检查锁是否处于锁定状态
3. 只释放已锁定的锁

---

### 5. 更新时间戳 `update_timestamp()`

```python
def update_timestamp(self, key: str) -> None:
    """更新时间戳，表示锁仍在使用中"""
    self.timestamps[key] = time.time()
```

**用途**: 防止正在使用的锁被误判为过期

---

### 6. 清理过期锁 `cleanup_expired_locks()`

```python
def cleanup_expired_locks(self) -> None:
    """清理超过 timeout_seconds 的锁"""
    current_time = time.time()
    expired_keys = []

    # 1. 找出过期的锁
    for key, timestamp in self.timestamps.items():
        if current_time - timestamp > self.timeout_seconds:
            expired_keys.append(key)

    # 2. 清理过期锁
    for key in expired_keys:
        if key in self.locks:
            try:
                if self.locks[key].locked():
                    # 强制释放长时间持有的锁
                    self.locks[key].release()
                del self.locks[key]
            except:
                pass  # 忽略删除时的错误

        if key in self.timestamps:
            del self.timestamps[key]
```

**清理流程**:

```
检查所有锁
    │
    ├─ 锁 A: 活跃时间 100 秒 → 保留
    ├─ 锁 B: 活跃时间 400 秒 → 过期，清理
    └─ 锁 C: 活跃时间 50 秒  → 保留
```

---

## 🔄 实际使用场景

### 场景 1: Chat 请求并发控制

**位置**: `backend/application/services/chat_service.py:34-44`

```python
# 1. 生成锁键
lock_key = f"{session_id}_chat"

# 2. 尝试获取锁（非阻塞）
lock_acquired = chat_manager.try_acquire_lock(lock_key)

if not lock_acquired:
    # 锁已被占用，返回 429 错误
    raise HTTPException(
        status_code=429,
        detail="当前有其他请求正在处理，请稍后再试"
    )

try:
    # 3. 更新时间戳
    chat_manager.update_timestamp(lock_key)

    # 4. 处理请求
    # ... 业务逻辑 ...

finally:
    # 5. 释放锁
    chat_manager.release_lock(lock_key)

    # 6. 清理过期锁
    chat_manager.cleanup_expired_locks()
```

### 工作流程图

```
用户 A 发送请求 (session_id="001")
    │
    ▼
生成 lock_key = "001_chat"
    │
    ▼
尝试获取锁
    │
    ├─ 成功 ────────────▶ 处理请求
    │                        │
    │                        ▼
    │                   更新时间戳
    │                        │
    │                        ▼
    │                   业务逻辑
    │                        │
    │                        ▼
    │                   释放锁
    │
    └─ 失败 ────────────▶ 返回 429 错误
         (锁被占用)        "请稍后再试"
```

### 场景 2: 防止重复提交

```
时间轴: ─────────────────────────────────────▶

t=0s    用户 A 点击"发送"
        ├─ 获取锁 "001_chat" ✅
        └─ 开始处理...

t=2s    用户 A 再次点击"发送"（误操作）
        ├─ 尝试获取锁 "001_chat" ❌
        └─ 返回 429 错误

t=10s   第一个请求完成
        ├─ 释放锁 "001_chat"
        └─ 此时可以再次发送
```

---

## 🆚 与 AgentManager 锁的对比

### AgentManager 的锁

**位置**: `backend/application/services/agent_service.py:32`

```python
class AgentManager:
    def __init__(self):
        # 使用 RLock（可重入锁）
        self.agent_lock = threading.RLock()

    def get_agent(self, agent_type: str, session_id: str):
        with self.agent_lock:
            # 保护实例池的并发访问
            if instance_key not in self.agent_instances:
                self.agent_instances[instance_key] = ...
```

### ConcurrentManager 的锁

```python
class ConcurrentManager:
    def __init__(self):
        # 多个独立的 Lock（普通锁）
        self.locks: Dict[str, threading.Lock] = {}

    def try_acquire_lock(self, key: str, wait: bool = False):
        lock = self.get_lock(key)
        return lock.acquire(blocking=False)  # 非阻塞
```

### 对比表

| 特性 | AgentManager 锁 | ConcurrentManager 锁 |
|------|----------------|---------------------|
| **锁类型** | `threading.RLock` | `threading.Lock` |
| **数量** | 1 个全局锁 | 多个独立锁（每个 key 一个） |
| **可重入** | ✅ 是 | ❌ 否 |
| **粒度** | 粗粒度（保护整个实例池） | 细粒度（每个会话独立） |
| **阻塞方式** | 阻塞（`with` 语句） | 非阻塞（默认） |
| **用途** | 保护共享数据结构 | 防止重复请求 |
| **超时清理** | ❌ 无 | ✅ 有 |

---

## 🔐 线程锁详解

### Python threading.Lock 基础

```python
import threading

# 1. 创建锁
lock = threading.Lock()

# 2. 获取锁
lock.acquire()       # 阻塞直到获取锁
lock.acquire(blocking=False)  # 非阻塞，立即返回 True/False
lock.acquire(timeout=5)       # 最多等待 5 秒

# 3. 释放锁
lock.release()

# 4. 检查锁状态
lock.locked()  # True: 已锁定, False: 未锁定
```

### 上下文管理器（推荐）

```python
# 方式 1: 手动管理（不推荐）
lock.acquire()
try:
    # 临界区代码
    pass
finally:
    lock.release()

# 方式 2: with 语句（推荐）
with lock:
    # 临界区代码
    pass
# 自动释放锁
```

### Lock vs RLock

```python
# threading.Lock（普通锁）
lock = threading.Lock()
lock.acquire()
lock.acquire()  # ❌ 死锁！同一线程不能重复获取

# threading.RLock（可重入锁）
rlock = threading.RLock()
rlock.acquire()
rlock.acquire()  # ✅ OK，同一线程可以重复获取
rlock.release()
rlock.release()  # 需要释放相同次数
```

---

## 🎬 完整执行流程示例

### 正常流程

```python
# 时间: t=0
用户 A 请求到达 (session_id="abc123")

# t=0.001
lock_key = "abc123_chat"
chat_manager.try_acquire_lock(lock_key)  # 成功 ✅

# t=0.002
chat_manager.update_timestamp(lock_key)
# timestamps["abc123_chat"] = 1735454400.002

# t=0.003 - t=10.000
处理请求（耗时 10 秒）...

# t=5.000
chat_manager.update_timestamp(lock_key)
# timestamps["abc123_chat"] = 1735454405.000  # 更新时间

# t=10.000
chat_manager.release_lock(lock_key)
# 锁被释放

# t=10.001
chat_manager.cleanup_expired_locks()
# 清理超过 5 分钟的锁
```

### 并发冲突流程

```python
# 时间: t=0
用户 A 请求 1 到达
lock_key = "abc123_chat"
chat_manager.try_acquire_lock(lock_key)  # 成功 ✅
locks["abc123_chat"].locked() = True

# t=2
用户 A 请求 2 到达（重复点击）
lock_key = "abc123_chat"
chat_manager.try_acquire_lock(lock_key)  # 失败 ❌
返回 HTTPException(status_code=429)

# 前端显示: "当前有其他请求正在处理，请稍后再试"

# t=10
请求 1 完成
chat_manager.release_lock(lock_key)
locks["abc123_chat"].locked() = False

# t=12
用户 A 请求 3 到达
chat_manager.try_acquire_lock(lock_key)  # 成功 ✅
```

---

## ⚙️ 配置参数说明

### 默认配置

```python
chat_manager = ConcurrentManager(
    timeout_seconds=300,      # 5 分钟
    lock_wait_timeout=10,     # 10 秒
)
```

### 参数说明

| 参数 | 默认值 | 说明 | 影响 |
|------|--------|------|------|
| `timeout_seconds` | 300 | 锁超时时间（秒） | 超过此时间未更新的锁会被清理 |
| `lock_wait_timeout` | 10 | 等待模式下的最大等待时间 | 仅在 `wait=True` 时生效 |

### 调整建议

```python
# 场景 1: 深度研究 Agent（处理时间长）
deep_research_manager = ConcurrentManager(
    timeout_seconds=600,   # 10 分钟
    lock_wait_timeout=30,  # 30 秒
)

# 场景 2: 快速响应（处理时间短）
quick_manager = ConcurrentManager(
    timeout_seconds=60,    # 1 分钟
    lock_wait_timeout=5,   # 5 秒
)
```

---

## 🐛 潜在问题

### 1. 锁泄漏

**问题**: 如果异常导致 `release_lock()` 未执行

```python
lock_acquired = chat_manager.try_acquire_lock(lock_key)
# ... 处理请求 ...
# ❌ 如果这里发生异常，锁不会被释放
chat_manager.release_lock(lock_key)
```

**解决方案**: 使用 try-finally

```python
lock_acquired = chat_manager.try_acquire_lock(lock_key)
try:
    # ... 处理请求 ...
finally:
    chat_manager.release_lock(lock_key)  # ✅ 保证释放
```

### 2. 过期清理时机

**问题**: 只在请求结束时调用 `cleanup_expired_locks()`，长时间无请求时不会清理

**改进建议**: 添加定时清理任务

```python
import threading

def periodic_cleanup():
    while True:
        time.sleep(60)  # 每分钟清理一次
        chat_manager.cleanup_expired_locks()
        feedback_manager.cleanup_expired_locks()

cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()
```

---

## 📊 全局实例

```python
# backend/infrastructure/utils/concurrent.py:98-99

# Chat 请求锁管理
chat_manager = ConcurrentManager()

# 反馈请求锁管理
feedback_manager = ConcurrentManager()
```

**分离原因**: Chat 和 Feedback 使用独立的锁管理器，避免互相影响

---

## 🎯 总结

### ConcurrentManager 的核心价值

1. **🔒 并发控制**: 防止同一会话的重复请求
2. **⚡ 快速失败**: 非阻塞模式，避免请求堆积
3. **🧹 自动清理**: 防止锁泄漏导致的资源占用
4. **🔑 细粒度锁**: 每个会话独立锁，提高并发性能

### 与 AgentManager 锁的配合

```
请求到达
  │
  ▼
ConcurrentManager.try_acquire_lock()  ← 会话级并发控制
  │ (防止同一用户重复提交)
  ▼
AgentManager.get_agent()
  │
  with self.agent_lock:  ← 实例池级并发控制
  │   (保护共享数据结构)
  ▼
返回 Agent 实例
```

**两层防护**:
1. **外层** (ConcurrentManager): 防止用户重复提交
2. **内层** (AgentManager): 保护实例池数据一致性

---

**文件**: `backend/infrastructure/utils/concurrent.py`
**行数**: 99 行
**核心方法**: `try_acquire_lock()` (46-63 行)
**作者**: GraphRAG Team

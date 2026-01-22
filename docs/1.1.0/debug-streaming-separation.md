# 调试模式与流式响应分离设计文档

**版本**: 1.1.0
**创建日期**: 2025-01-22
**状态**: 设计中
**作者**: Claude & Community

---

## 目录

- [1. 背景与问题](#1-背景与问题)
- [2. 设计目标](#2-设计目标)
- [3. 方案对比](#3-方案对比)
- [4. 技术架构](#4-技术架构)
- [5. API 设计](#5-api-设计)
- [6. 数据结构](#6-数据结构)
- [7. 实现细节](#7-实现细节)
- [8. 前端适配](#8-前端适配)
- [9. 部署与配置](#9-部署与配置)
- [10. 测试计划](#10-测试计划)
- [11. 性能优化](#11-性能优化)
- [12. 风险与限制](#12-风险与限制)

---

## 1. 背景与问题

### 1.1 当前问题

**现状**：
- 调试模式下必须关闭流式响应
- 用户无法同时体验"实时反馈"和"调试信息"
- 调试数据（执行日志、知识图谱、Trace）在流式模式下无法完整传递

**根本原因**：
```python
# 当前实现（伪代码）
if debug_mode:
    # 非流式：一次性返回所有数据
    return {
        "answer": "完整答案",
        "execution_log": [...],
        "kg_data": {...},
        "trace": {...}
    }
else:
    # 流式：逐个 token 发送，调试数据丢失
    async for token in stream():
        yield {"status": "token", "content": token}
```

### 1.2 影响范围

| 用户群体 | 影响 |
|---------|------|
| **开发者** | 无法在调试模式下实时看到生成过程 |
| **产品测试** | 难以调试 Agent 行为和检索性能 |
| **最终用户** | 调试模式下体验差（等待时间长） |

---

## 2. 设计目标

### 2.1 核心目标

1. ✅ **调试模式支持流式响应**
   - 用户可以同时看到实时生成和调试信息

2. ✅ **职责分离**
   - 流式 API 只负责内容生成
   - 调试 API 专门提供调试数据

3. ✅ **按需加载**
   - 前端可以决定是否加载调试数据
   - 减少不必要的数据传输

4. ✅ **向后兼容**
   - 不影响现有非流式 API
   - 平滑迁移

### 2.2 非目标

- ❌ 不改变现有的非流式 API 行为
- ❌ 不强制用户在调试模式下使用流式响应
- ❌ 不增加后端存储依赖（可选 Redis）

---

## 3. 方案对比

### 3.1 方案矩阵

| 方案 | 优点 | 缺点 | 复杂度 | 推荐度 |
|------|------|------|--------|--------|
| **A. 流式结束时发送调试包** | 实现简单 | 数据量大时延迟高 | ⭐⭐ | ⭐⭐⭐ |
| **B. 前端重建调试数据** | 无后端改动 | 数据完整性难保证 | ⭐⭐⭐⭐ | ⭐ |
| **C. 分离 API（本文档）** | 职责清晰、可扩展 | 需新增 API | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

### 3.2 方案 C 详细对比

| 维度 | 当前实现 | 方案 C |
|------|---------|--------|
| **调试模式** | ❌ 必须关闭流式 | ✅ 支持流式 |
| **数据传输** | 一次性全部传输 | 分次按需传输 |
| **缓存策略** | 无 | 可缓存调试数据 |
| **API 数量** | 1 个（/chat） | 2 个（/chat/stream + /debug/{id}） |
| **前端改动** | 无需改动 | 新增调试数据查询 |
| **后端改动** | 无需改动 | 新增调试数据收集+API |

---

## 4. 技术架构

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                     前端 (Streamlit/React)               │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────┐    ┌─────────────────────┐   │
│  │  流式响应 UI          │    │  调试面板 UI        │   │
│  │  - Token 实时显示     │    │  - 执行日志         │   │
│  │  - 进度条             │    │  - Trace 信息       │   │
│  │  - message_id        │    │  - 知识图谱         │   │
│  └──────────────────────┘    └─────────────────────┘   │
│           │                            │                 │
│           │ SSE                         │ HTTP GET       │
│           ▼                            ▼                 │
└───────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌────────────────────┐    ┌────────────────────────┐  │
│  │  /api/v1/chat/     │    │  /api/v1/debug/{id}    │  │
│  │  stream (SSE)      │    │  (HTTP GET)            │  │
│  └────────────────────┘    └────────────────────────┘  │
│           │                            │                 │
│           ▼                            ▼                 │
│  ┌────────────────────┐    ┌────────────────────────┐  │
│  │  StreamHandler     │    │  DebugDataCache        │  │
│  │  - 发送 Token      │    │  - 内存缓存            │  │
│  │  - 收集调试数据    │◄───┤  - Redis (可选)        │  │
│  └────────────────────┘    └────────────────────────┘  │
│                                                           │
└───────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   核心层 (Agents)                        │
├─────────────────────────────────────────────────────────┤
│  - GraphAgent                                           │
│  - HybridAgent                                          │
│  - DeepResearchAgent                                    │
└───────────────────────────────────────────────────────────┘
```

### 4.2 数据流图

```
用户发起查询
    │
    ▼
┌───────────────────┐
│  1. POST /chat/stream  │
│     {debug: true}  │
└───────────────────┘
    │
    ├─► 生成 message_id
    │
    ├─► 返回 {"status": "start", "message_id": "xxx"}
    │
    ├─► 发送 Token 事件
    │   {"status": "token", "content": "..."}
    │
    ├─► 同时收集调试数据到缓存
    │   - execution_log
    │   - trace
    │   - progress_events
    │
    ├─► 发送 Done 事件
    │   {"status": "done", "message_id": "xxx"}
    │
    ▼
前端收到 Done
    │
    ▼
┌───────────────────┐
│  2. GET /debug/xxx   │
└───────────────────┘
    │
    ├─► 从缓存读取调试数据
    │
    └─► 返回完整调试信息
        {
          "message_id": "xxx",
          "execution_log": [...],
          "trace": [...],
          "progress_events": [...]
        }
```

---

## 5. API 设计

### 5.1 流式 API（无改动）

**端点**: `POST /api/v1/chat/stream`

**请求**:
```json
{
  "message": "诺兰导演的电影有哪些？",
  "user_id": "user123",
  "session_id": "session456",
  "debug": true,
  "agent_type": "graph_agent"
}
```

**响应（SSE 事件流）**:
```
data: {"status": "start", "message_id": "msg_uuid_123"}

data: {"status": "token", "content": "根据"}
data: {"status": "token", "content": "知识"}
data: {"status": "token", "content": "图谱"}

data: {"status": "progress", "content": {"stage": "retrieval", "completed": 5, "total": 10}}

data: {"status": "token", "content": "..."}
data: {"status": "token", "content": "《盗梦空间》"}

data: {"status": "done", "message_id": "msg_uuid_123"}
```

**关键点**：
- ✅ 在 `start` 和 `done` 事件中携带 `message_id`
- ✅ 其他事件保持不变（向后兼容）

### 5.2 调试数据 API（新增）

**端点**: `GET /api/v1/debug/{message_id}`

**请求参数**:
```
GET /api/v1/debug/msg_uuid_123
```

**成功响应（200 OK）**:
```json
{
  "message_id": "msg_uuid_123",
  "timestamp": "2025-01-22T12:34:56Z",
  "execution_log": [
    {
      "step": "entity_extraction",
      "duration_ms": 1234,
      "entities": ["诺兰", "盗梦空间"]
    },
    {
      "step": "graph_retrieval",
      "duration_ms": 567,
      "nodes": 15,
      "relationships": 23
    }
  ],
  "trace": [
    {
      "timestamp": "2025-01-22T12:34:57Z",
      "event": "tool_call",
      "tool": "local_search",
      "input": {"query": "诺兰电影"}
    }
  ],
  "progress_events": [
    {"stage": "retrieval", "completed": 10, "total": 10},
    {"stage": "generation", "completed": 100, "total": 100}
  ]
}
```

**错误响应（404 Not Found）**:
```json
{
  "detail": "Debug data for message_id 'msg_uuid_123' not found or expired"
}
```

### 5.3 调试数据清理 API（可选）

**端点**: `DELETE /api/v1/debug/{message_id}`

**响应**:
```json
{
  "status": "cleared",
  "message_id": "msg_uuid_123"
}
```

---

## 6. 数据结构

### 6.1 调试数据结构

```python
# backend/server/models/debug_data.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


class ExecutionLogEntry(BaseModel):
    """单条执行日志"""
    step: str
    duration_ms: int
    timestamp: datetime
    details: Dict[str, Any] = {}


class TraceEvent(BaseModel):
    """追踪事件"""
    timestamp: datetime
    event_type: str  # "tool_call", "retrieval", "generation", etc.
    data: Dict[str, Any]


class ProgressEvent(BaseModel):
    """进度事件"""
    stage: str
    completed: int
    total: int
    error: Optional[str] = None


class DebugData(BaseModel):
    """完整调试数据"""
    message_id: str
    timestamp: datetime
    execution_log: List[ExecutionLogEntry] = []
    trace: List[TraceEvent] = []
    progress_events: List[ProgressEvent] = []
    kg_data: Optional[Dict[str, Any]] = None  # 知识图谱数据（可选）
```

### 6.2 缓存键设计

```python
# 缓存键格式
DEBUG_CACHE_KEY = f"debug:{message_id}"

# 示例
# "debug:msg_uuid_123"
```

---

## 7. 实现细节

### 7.1 后端实现

#### 7.1.1 调试数据收集器

```python
# backend/server/api/rest/v1/debug_collector.py

from typing import Dict, List, Any
from datetime import datetime
import uuid


class DebugDataCollector:
    """调试数据收集器"""

    def __init__(self, message_id: str):
        self.message_id = message_id
        self.timestamp = datetime.now()
        self.execution_log: List[Dict] = []
        self.trace: List[Dict] = []
        self.progress_events: List[Dict] = []
        self.kg_data: Dict = {}

    def add_execution_log(self, step: str, duration_ms: int, **details):
        """添加执行日志"""
        self.execution_log.append({
            "step": step,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
            **details
        })

    def add_trace_event(self, event_type: str, data: Dict):
        """添加追踪事件"""
        self.trace.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        })

    def add_progress_event(self, stage: str, completed: int, total: int, error: str = None):
        """添加进度事件"""
        self.progress_events.append({
            "stage": stage,
            "completed": completed,
            "total": total,
            "error": error
        })

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat(),
            "execution_log": self.execution_log,
            "trace": self.trace,
            "progress_events": self.progress_events,
            "kg_data": self.kg_data
        }
```

#### 7.1.2 调试数据缓存管理

```python
# backend/server/api/rest/v1/debug_cache.py

from typing import Dict, Optional
from datetime import datetime, timedelta
from backend.server.api.rest.v1.debug_collector import DebugDataCollector


class DebugDataCache:
    """调试数据缓存（内存实现）"""

    def __init__(self, ttl_minutes: int = 30):
        self._cache: Dict[str, DebugDataCollector] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def set(self, message_id: str, collector: DebugDataCollector):
        """存储调试数据"""
        self._cache[message_id] = collector

    def get(self, message_id: str) -> Optional[DebugDataCollector]:
        """获取调试数据"""
        collector = self._cache.get(message_id)
        if collector is None:
            return None

        # 检查是否过期
        if datetime.now() - collector.timestamp > self._ttl:
            del self._cache[message_id]
            return None

        return collector

    def delete(self, message_id: str) -> bool:
        """删除调试数据"""
        if message_id in self._cache:
            del self._cache[message_id]
            return True
        return False

    def cleanup_expired(self):
        """清理过期数据"""
        now = datetime.now()
        expired = [
            msg_id for msg_id, collector in self._cache.items()
            if now - collector.timestamp > self._ttl
        ]
        for msg_id in expired:
            del self._cache[msg_id]
        return len(expired)


# 全局缓存实例
debug_cache = DebugDataCache(ttl_minutes=30)
```

#### 7.1.3 流式 API 改造

```python
# backend/server/api/rest/v1/chat_stream.py（修改部分）

import uuid
from backend.server.api.rest.v1.debug_cache import debug_cache
from backend.server.api.rest.v1.debug_collector import DebugDataCollector


@router.post("/chat/stream")
async def chat_stream(
    raw_request: Request,
    request: ChatRequest,
    handler: StreamHandler = Depends(get_stream_handler),
) -> StreamingResponse:
    # 生成唯一 message_id
    message_id = str(uuid.uuid4())

    # 创建调试数据收集器（仅调试模式）
    collector = None
    if request.debug:
        collector = DebugDataCollector(message_id)
        debug_cache.set(message_id, collector)

    async def event_generator():
        yield format_sse({"status": "start", "message_id": message_id})

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
                if await raw_request.is_disconnected():
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

                # 收集调试数据
                if request.debug and collector:
                    if event.get("status") == "execution_log":
                        collector.add_execution_log(**event.get("content", {}))
                    elif event.get("status") == "progress":
                        collector.add_progress_event(**event.get("content", {}))
                    elif "trace" in event:
                        collector.add_trace_event(**event["trace"])

                # 发送到前端
                payload = normalize_stream_event(event)
                if payload.get("status") == "done":
                    payload["message_id"] = message_id
                yield format_sse(payload)

        finally:
            aclose = getattr(iterator, "aclose", None)
            if callable(aclose):
                await aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

#### 7.1.4 调试 API 实现

```python
# backend/server/api/rest/v1/debug.py（新建文件）

from fastapi import APIRouter, HTTPException
from backend.server.api.rest.v1.debug_cache import debug_cache

router = APIRouter(prefix="/api/v1", tags=["debug"])


@router.get("/debug/{message_id}")
async def get_debug_data(message_id: str) -> dict:
    """
    获取指定消息的调试数据

    Args:
        message_id: 流式响应返回的 message_id

    Returns:
        调试数据，包含 execution_log, trace, progress_events 等
    """
    collector = debug_cache.get(message_id)

    if not collector:
        raise HTTPException(
            status_code=404,
            detail=f"Debug data for message_id '{message_id}' not found or expired"
        )

    return collector.to_dict()


@router.delete("/debug/{message_id}")
async def clear_debug_data(message_id: str) -> dict:
    """手动清理指定消息的调试数据"""
    deleted = debug_cache.delete(message_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Message '{message_id}' not found")
    return {"status": "cleared", "message_id": message_id}


@router.post("/debug/cleanup")
async def cleanup_expired_debug_data() -> dict:
    """清理所有过期的调试数据（管理接口）"""
    count = debug_cache.cleanup_expired()
    return {"status": "cleaned", "expired_count": count}
```

### 7.2 注册路由

```python
# backend/server/main.py

from server.api.rest.v1 import debug

# 注册路由
app.include_router(debug.router)  # 添加调试数据路由
app.include_router(chat.router)
app.include_router(chat_stream.router)
```

---

## 8. 前端适配

### 8.1 API 客户端更新

```python
# frontend/utils/api.py

async def send_message_stream_with_debug(
    message: str,
    on_token: Callable[[str, bool], None],
    on_progress: Optional[Callable[[Dict], None]] = None,
    on_stream_end: Optional[Callable[[str], None] = None,
) -> Optional[str]:
    """
    流式发送消息，返回 message_id 用于查询调试数据

    Args:
        message: 用户消息
        on_token: Token 回调（token, is_thinking）
        on_progress: 进度回调
        on_stream_end: 流式结束回调，参数为 message_id

    Returns:
        message_id (如果成功)
    """
    try:
        message_id = None

        params = {
            "message": message,
            "user_id": st.session_state.user_id,
            "session_id": st.session_state.session_id,
            "debug": st.session_state.debug_mode,
            "agent_type": st.session_state.agent_type
        }

        response = requests.post(
            f"{API_URL}/api/v1/chat/stream",
            json=params,
            stream=True,
            headers={"Accept": "text/event-stream"}
        )

        client = sseclient.SSEClient(response)

        for event in client.events():
            try:
                data = json.loads(event.data)

                # 提取 message_id
                if data.get("status") == "start":
                    message_id = data.get("message_id")

                # 处理 token
                elif data.get("status") == "token":
                    on_token(data.get("content", ""))

                # 处理进度
                elif data.get("status") == "progress":
                    if on_progress:
                        on_progress(data.get("content", {}))

                # 流式结束
                elif data.get("status") == "done":
                    if on_stream_end and message_id:
                        on_stream_end(message_id)
                    break

            except Exception as e:
                print(f"处理事件错误: {e}")

        return message_id

    except Exception as e:
        on_token(f"\n\n连接错误: {e}")
        return None


def get_debug_data(message_id: str) -> Optional[dict]:
    """
    根据 message_id 获取调试数据

    Args:
        message_id: 消息 ID

    Returns:
        调试数据字典，如果失败返回 None
    """
    try:
        response = requests.get(
            f"{API_URL}/api/v1/debug/{message_id}",
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except Exception as e:
        print(f"获取调试数据失败: {e}")
        return None
```

### 8.2 UI 集成

```python
# frontend/components/chat.py

def display_chat_interface():
    """显示主聊天界面"""

    # ... 现有代码 ...

    # 修改流式响应选项
    if not st.session_state.debug_mode:
        use_stream = st.checkbox("使用流式响应", value=True)
        st.session_state.use_stream = use_stream
    else:
        # 调试模式现在也支持流式！
        use_stream = st.checkbox("使用流式响应（调试模式）", value=True)
        st.session_state.use_stream = use_stream


async def send_message_with_debug():
    """发送消息并自动加载调试数据"""

    # 缓存调试数据
    if "debug_cache" not in st.session_state:
        st.session_state.debug_cache = {}

    current_message_id = None

    async def on_stream_end(message_id: str):
        """流式结束后自动获取调试数据"""
        nonlocal current_message_id
        current_message_id = message_id

        if st.session_state.debug_mode and message_id:
            with st.spinner("加载调试数据..."):
                debug_data = get_debug_data(message_id)
                if debug_data:
                    st.session_state.debug_cache[message_id] = debug_data

    # 发送流式消息
    await send_message_stream_with_debug(
        message=user_input,
        on_token=lambda token, is_thinking=False: update_message(token),
        on_progress=handle_progress,
        on_stream_end=on_stream_end
    )

    # 存储 message_id 到消息中
    if current_message_id:
        st.session_state.messages[-1]["message_id"] = current_message_id


def display_debug_panel():
    """在调试模式下显示调试数据"""
    if not st.session_state.debug_mode:
        return

    # 获取当前消息的 message_id
    current_msg = st.session_state.messages[-1]
    message_id = current_msg.get("message_id")

    if not message_id:
        return

    # 从缓存获取调试数据
    debug_data = st.session_state.debug_cache.get(message_id)

    if not debug_data:
        st.info("调试数据正在加载...")
        return

    with st.expander("🐛 调试信息", expanded=False):
        # Tab 1: 执行日志
        tab1, tab2, tab3 = st.tabs(["执行日志", "追踪", "进度事件"])

        with tab1:
            if debug_data.get("execution_log"):
                for log in debug_data["execution_log"]:
                    st.caption(f"📌 {log['step']} ({log['duration_ms']}ms)")
                    st.json(log.get("details", {}))
                    st.markdown("---")
            else:
                st.info("无执行日志")

        with tab2:
            if debug_data.get("trace"):
                st.json(debug_data["trace"])
            else:
                st.info("无追踪信息")

        with tab3:
            if debug_data.get("progress_events"):
                for event in debug_data["progress_events"]:
                    progress = event["completed"] / event["total"] * 100
                    st.progress(progress / 100)
                    st.caption(f"{event['stage']}: {event['completed']}/{event['total']}")
            else:
                st.info("无进度事件")
```

---

## 9. 部署与配置

### 9.1 环境变量

```bash
# .env 新增配置

# 调试数据缓存 TTL（分钟）
DEBUG_CACHE_TTL=30

# 调试数据清理间隔（分钟）
DEBUG_CLEANUP_INTERVAL=10

# 是否启用 Redis 缓存（可选）
DEBUG_CACHE_USE_REDIS=false
REDIS_URL=redis://localhost:6379/0
```

### 9.2 配置文件

```python
# backend/config/settings.py（新增）

from os import getenv

DEBUG_CACHE_TTL = int(getenv("DEBUG_CACHE_TTL", "30"))
DEBUG_CLEANUP_INTERVAL = int(getenv("DEBUG_CLEANUP_INTERVAL", "10"))
DEBUG_CACHE_USE_REDIS = getenv("DEBUG_CACHE_USE_REDIS", "false").lower() == "true"
REDIS_URL = getenv("REDIS_URL", "redis://localhost:6379/0")
```

### 9.3 部署检查清单

- [ ] 后端代码更新（chat_stream.py, debug.py）
- [ ] 前端代码更新（api.py, chat.py）
- [ ] 环境变量配置
- [ ] 路由注册（main.py）
- [ ] 测试流式 + 调试模式
- [ ] 性能测试（高并发场景）
- [ ] 监控缓存内存占用

---

## 10. 测试计划

### 10.1 单元测试

```python
# tests/test_debug_cache.py

import pytest
from datetime import datetime, timedelta
from server.api.rest.v1.debug_cache import DebugDataCache
from server.api.rest.v1.debug_collector import DebugDataCollector


def test_debug_cache_set_and_get():
    """测试缓存设置和获取"""
    cache = DebugDataCache(ttl_minutes=30)
    collector = DebugDataCollector("msg_123")

    cache.set("msg_123", collector)
    retrieved = cache.get("msg_123")

    assert retrieved is not None
    assert retrieved.message_id == "msg_123"


def test_debug_cache_expiration():
    """测试缓存过期"""
    cache = DebugDataCache(ttl_minutes=0)  # 立即过期
    collector = DebugDataCollector("msg_123")

    cache.set("msg_123", collector)
    retrieved = cache.get("msg_123")

    assert retrieved is None  # 已过期


def test_debug_cache_cleanup():
    """测试清理过期数据"""
    cache = DebugDataCache(ttl_minutes=30)

    # 添加多个条目
    for i in range(5):
        collector = DebugDataCollector(f"msg_{i}")
        cache.set(f"msg_{i}", collector)

    # 清理
    count = cache.cleanup_expired()
    assert count == 0  # 都未过期
```

### 10.2 集成测试

```python
# tests/test_debug_api.py

import pytest
from fastapi.testclient import TestClient
from server.main import app


client = TestClient(app)


def test_get_debug_data_not_found():
    """测试获取不存在的调试数据"""
    response = client.get("/api/v1/debug/nonexistent_id")
    assert response.status_code == 404


def test_debug_data_flow():
    """测试完整的调试数据流程"""
    # 1. 发起流式请求（调试模式）
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "message": "测试消息",
            "debug": True,
            "user_id": "test_user",
            "session_id": "test_session"
        }
    )

    # 2. 提取 message_id
    assert response.status_code == 200
    events = list(response.stream())
    start_event = events[0]
    message_id = start_event.get("message_id")
    assert message_id is not None

    # 3. 获取调试数据
    debug_response = client.get(f"/api/v1/debug/{message_id}")
    assert debug_response.status_code == 200
    debug_data = debug_response.json()
    assert debug_data["message_id"] == message_id
```

### 10.3 端到端测试

```python
# tests/test_e2e_debug_streaming.py

import pytest
from frontend.utils.api import send_message_stream_with_debug, get_debug_data


@pytest.mark.asyncio
async def test_debug_mode_with_streaming():
    """测试调试模式下的流式响应"""

    message_id = None

    async def on_stream_end(msg_id):
        nonlocal message_id
        message_id = msg_id

    # 发送消息
    await send_message_stream_with_debug(
        message="测试查询",
        on_token=lambda token: print(f"Token: {token}"),
        on_stream_end=on_stream_end
    )

    # 等待流式结束
    assert message_id is not None

    # 获取调试数据
    debug_data = get_debug_data(message_id)
    assert debug_data is not None
    assert "execution_log" in debug_data
```

---

## 11. 性能优化

### 11.1 内存优化

**问题**：调试数据可能占用大量内存

**解决方案**：

1. **限制缓存大小**
   ```python
   class DebugDataCache:
       def __init__(self, ttl_minutes: int = 30, max_size: int = 1000):
           self._cache: Dict[str, DebugDataCollector] = {}
           self._ttl = timedelta(minutes=ttl_minutes)
           self._max_size = max_size

       def set(self, message_id: str, collector: DebugDataCollector):
           # LRU 淘汰策略
           if len(self._cache) >= self._max_size:
               # 删除最旧的条目
               oldest_key = min(self._cache.keys())
               del self._cache[oldest_key]

           self._cache[message_id] = collector
   ```

2. **数据采样**
   ```python
   class DebugDataCollector:
       def add_trace_event(self, event_type: str, data: Dict):
           # 只保留最近 100 条追踪事件
           if len(self.trace) >= 100:
               self.trace.pop(0)
           self.trace.append(...)
   ```

### 11.2 Redis 缓存（可选）

**生产环境推荐使用 Redis**：

```python
# backend/server/api/rest/v1/debug_cache_redis.py

import redis
import json
from datetime import timedelta


class RedisDebugDataCache:
    """基于 Redis 的调试数据缓存"""

    def __init__(self, redis_url: str, ttl_seconds: int = 1800):
        self.client = redis.from_url(redis_url)
        self.ttl = ttl_seconds

    def set(self, message_id: str, collector: DebugDataCollector):
        """存储调试数据"""
        key = f"debug:{message_id}"
        data = json.dumps(collector.to_dict())
        self.client.setex(key, self.ttl, data)

    def get(self, message_id: str) -> Optional[DebugDataCollector]:
        """获取调试数据"""
        key = f"debug:{message_id}"
        data = self.client.get(key)
        if data:
            return DebugDataCollector.from_dict(json.loads(data))
        return None

    def delete(self, message_id: str) -> bool:
        """删除调试数据"""
        key = f"debug:{message_id}"
        return bool(self.client.delete(key))
```

---

## 12. 风险与限制

### 12.1 已知风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **内存泄漏** | 缓存未清理导致内存占用过高 | 自动清理过期数据、限制缓存大小 |
| **调试数据丢失** | 客户端断开连接后无法获取 | 提供合理的 TTL（30分钟） |
| **并发竞争** | 多个请求同时访问缓存 | 使用线程安全的数据结构或 Redis |
| **调试数据过大** | 单条数据占用内存过多 | 限制 trace 和 log 的数量 |

### 12.2 限制

1. **TTL 限制**：调试数据默认保留 30 分钟
2. **缓存大小**：默认最多缓存 1000 条调试数据
3. **Trace 数量**：默认最多保留 100 条追踪事件
4. **向后兼容**：非调试模式下行为不变

### 12.3 未来改进

- [ ] 支持调试数据导出（JSON/CSV）
- [ ] 支持调试数据实时订阅（WebSocket）
- [ ] 支持跨会话的调试数据对比
- [ ] 支持调试数据可视化（图表）

---

## 附录

### A. 相关文档

- [SSE 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [前端调试面板设计](./debug-panel-design.md)

### B. 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.1.0 | 2025-01-22 | 初始设计文档 |

### C. 审批记录

| 角色 | 姓名 | 日期 | 状态 |
|------|------|------|------|
| 设计者 | Claude | 2025-01-22 | ✅ |
| 审核者 | - | - | ⏳ |
| 批准者 | - | - | ⏳ |

# 管理员 API 文档

## 概述

管理员 API 提供系统监控和管理功能，包括健康检查、查询性能统计等。

**基础路径**: `/admin`

---

## 接口列表

### 1. 系统健康检查

**端点**: `GET /admin/health`

**描述**: 获取 Neo4j 数据库连接健康状态

**返回示例**:
```json
{
  "neo4j": {
    "healthy": true,
    "version": "5.12.0",
    "response_time_ms": 12.34,
    "error": null,
    "check_time": "2025-01-05T10:30:45.123456"
  }
}
```

**字段说明**:
- `healthy`: 连接是否健康
- `version`: Neo4j 版本
- `response_time_ms`: 响应时间（毫秒）
- `error`: 错误信息（如果有）
- `check_time`: 检查时间

**使用示例**:
```bash
curl http://localhost:8000/admin/health
```

---

### 2. 查询性能统计

**端点**: `GET /admin/query-stats`

**描述**: 获取查询性能统计摘要和慢查询列表

**返回示例**:
```json
{
  "summary": {
    "total_queries": 1523,
    "unique_queries": 89,
    "slow_queries_count": 12,
    "slow_query_threshold": 1.0,
    "avg_times_top10": {
      "MATCH (n)-[r]->(m) RETURN r": 1.234,
      "MATCH (n:__Entity__) WHERE n.id IN $ids RETURN n": 0.856,
      ...
    }
  },
  "slow_queries": [
    {
      "signature": "MATCH (n)-[r]->(m) RETURN r...",
      "elapsed": 2.34,
      "cypher_preview": "MATCH (n)-[r]->(m) RETURN r LIMIT 100",
      "timestamp": "2025-01-05T10:25:30.123456"
    },
    ...
  ]
}
```

**字段说明**:
- `total_queries`: 总查询次数
- `unique_queries`: 唯一查询数量
- `slow_queries_count`: 慢查询数量
- `slow_query_threshold`: 慢查询阈值（秒）
- `avg_times_top10`: Top 10 平均执行时间最长的查询
- `slow_queries`: 慢查询详情列表

**使用示例**:
```bash
curl http://localhost:8000/admin/query-stats
```

---

### 3. 重置查询统计

**端点**: `POST /admin/query-stats/reset`

**描述**: 重置查询性能统计数据

**返回示例**:
```json
{
  "status": "success",
  "message": "查询统计已重置"
}
```

**使用示例**:
```bash
curl -X POST http://localhost:8000/admin/query-stats/reset
```

---

### 4. 设置慢查询阈值

**端点**: `POST /admin/query-stats/threshold?seconds=0.5`

**描述**: 修改慢查询检测阈值

**参数**:
- `seconds` (query): 新的阈值（秒），例如 0.5

**返回示例**:
```json
{
  "status": "success",
  "message": "慢查询阈值已设置为 0.5 秒",
  "threshold": 0.5
}
```

**使用示例**:
```bash
# 设置慢查询阈值为 0.5 秒
curl -X POST "http://localhost:8000/admin/query-stats/threshold?seconds=0.5"

# 设置慢查询阈值为 2.0 秒
curl -X POST "http://localhost:8000/admin/query-stats/threshold?seconds=2.0"
```

---

## 使用场景

### 1. 应用启动时自动检查

在 `backend/server/main.py` 中已集成启动时健康检查：

```python
@app.on_event("startup")
async def startup_event():
    """应用启动时检查连接"""
    from infrastructure.utils.neo4j_utils import check_neo4j_connection

    health = check_neo4j_connection(driver)
    if not health['healthy']:
        raise Exception(f"Neo4j 连接失败: {health.get('error')}")
```

### 2. 定期监控脚本

```python
import requests
import time

while True:
    # 检查健康状态
    health = requests.get("http://localhost:8000/admin/health").json()
    if not health['neo4j']['healthy']:
        print(f"⚠️ Neo4j 连接异常: {health['neo4j']['error']}")

    # 检查慢查询
    stats = requests.get("http://localhost:8000/admin/query-stats").json()
    if stats['summary']['slow_queries_count'] > 10:
        print(f"⚠️ 检测到 {stats['summary']['slow_queries_count']} 个慢查询")

    time.sleep(60)  # 每分钟检查一次
```

### 3. 性能分析

```bash
# 获取当前性能统计
curl http://localhost:8000/admin/query-stats | jq

# 重置统计（开始新的测试）
curl -X POST http://localhost:8000/admin/query-stats/reset

# 运行测试...

# 查看测试结果
curl http://localhost:8000/admin/query-stats | jq
```

### 4. 调试慢查询

```bash
# 获取慢查询列表
curl http://localhost:8000/admin/query-stats | jq '.slow_queries[]'

# 设置更低的阈值，捕获更多慢查询
curl -X POST "http://localhost:8000/admin/query-stats/threshold?seconds=0.3"

# 重新测试...
```

---

## 安全建议

这些管理员接口应该：
1. **添加认证**: 在生产环境中添加 API 认证（如 JWT、API Key）
2. **限制访问**: 仅允许内网或管理员 IP 访问
3. **添加日志**: 记录所有管理操作
4. **速率限制**: 防止频繁调用

---

## 访问文档

启动服务器后，访问 `http://localhost:8000/docs` 查看完整的交互式 API 文档（Swagger UI）。

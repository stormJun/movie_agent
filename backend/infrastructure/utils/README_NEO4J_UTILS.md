# Neo4j 工具函数模块

## 概述

`backend/infrastructure/utils/neo4j_utils.py` 提供核心的 Neo4j 查询辅助功能，包括：

1. **参数内联** - 将查询参数内联到 Cypher 查询中
2. **结果格式化** - 格式化查询结果用于日志记录
3. **性能统计** - 自动跟踪查询性能、慢查询检测
4. **连接健康检查** - 验证 Neo4j 连接状态

---

## 核心功能

### 1. 参数内联 (`inline_cypher_params`)

将参数化查询转换为可直接在 Neo4j Browser 中执行的查询。

```python
from infrastructure.utils.neo4j_utils import inline_cypher_params

cypher = "MATCH (n:__Entity__) WHERE n.id IN $ids RETURN n"
params = {"ids": ["A", "B"]}

inlined = inline_cypher_params(cypher, params)
# 结果: "MATCH (n:__Entity__) WHERE n.id IN ['A', 'B'] RETURN n"
```

---

### 2. 查询日志 (`log_neo4j_query`, `log_neo4j_query_with_result`)

统一的查询日志记录，自动内联参数。

```python
from infrastructure.utils.neo4j_utils import log_neo4j_query, log_neo4j_query_with_result
import logging

logger = logging.getLogger(__name__)

# 记录查询（参数已内联）
log_neo4j_query(cypher, params, logger)

# 记录查询和结果（自动记录性能统计）
log_neo4j_query_with_result(
    cypher,
    params,
    result_df,
    elapsed_time=0.0234,
    logger_instance=logger
)
```

**日志级别**：
- INFO: 基本信息（行数、执行时间）
- DEBUG: 结果预览（前3行，列宽60字符）
- WARNING: 慢查询警告（超过阈值）

---

### 3. 性能统计 (`Neo4jQueryStats`)

自动跟踪查询性能，检测慢查询。

```python
from infrastructure.utils.neo4j_utils import (
    get_query_stats_summary,
    get_slow_queries,
    set_slow_query_threshold
)

# 设置慢查询阈值（秒）
set_slow_query_threshold(0.5)

# 获取统计摘要
stats = get_query_stats_summary()
print(f"总查询数: {stats['total_queries']}")
print(f"慢查询数: {stats['slow_queries_count']}")

# 获取慢查询列表
slow_queries = get_slow_queries(limit=10)
for sq in slow_queries:
    print(f"{sq['signature']}: {sq['elapsed']:.2f}s")
```

**自动统计**：每次使用 `log_query_with_result` 时自动记录。

---

### 4. 连接健康检查 (`check_neo4j_connection`)

检查 Neo4j 数据库连接状态。

```python
from infrastructure.utils.neo4j_utils import check_neo4j_connection
from infrastructure.providers.neo4jdb import get_db_manager

db_manager = get_db_manager()
driver = db_manager.get_driver()

health = check_neo4j_connection(driver)
print(f"健康: {health['healthy']}")
print(f"版本: {health['version']}")
print(f"响应时间: {health['response_time_ms']} ms")
```

---

## 使用模式

### 标准 db_query 函数

```python
from infrastructure.utils.neo4j_utils import log_neo4j_query, log_neo4j_query_with_result
import time
import pandas as pd

def db_query(cypher: str, params: Dict = None) -> pd.DataFrame:
    """标准的 Neo4j 查询函数"""
    params = params or {}
    started = time.time()

    # 记录查询（参数已内联）
    log_neo4j_query(cypher, params, logger)

    # 执行查询
    df = driver.execute_query(cypher, parameters_=params, result_transformer_=Result.to_df)

    # 记录结果和性能（自动统计）
    log_neo4j_query_with_result(cypher, params, df, time.time() - started, logger)

    return df
```

---

## API 参考

### 类

#### `Neo4jQueryHelper`
主要工具类，提供所有静态方法。

#### `Neo4jQueryStats`
查询性能统计器。
- `record_query(signature, elapsed, cypher)` - 记录查询
- `get_stats_summary()` - 获取统计摘要
- `get_slow_queries(limit)` - 获取慢查询列表
- `slow_threshold` - 慢查询阈值（秒）

### 函数

#### 基础功能
- `inline_cypher_params(cypher, params)` - 参数内联
- `format_neo4j_result(result, max_rows, max_col_width)` - 结果格式化
- `log_neo4j_query(cypher, params, logger)` - 记录查询
- `log_neo4j_query_with_result(cypher, params, result, elapsed, logger)` - 记录查询和结果

#### 连接
- `check_neo4j_connection(driver)` - 检查连接健康

#### 性能统计
- `get_query_stats_summary()` - 获取统计摘要
- `get_slow_queries(limit)` - 获取慢查询
- `set_slow_query_threshold(seconds)` - 设置阈值
- `get_query_stats()` - 获取统计器实例

---

## 配置

### 慢查询阈值

默认 1.0 秒，可通过 `set_slow_query_threshold()` 修改。

---

## 最佳实践

1. **始终使用工具类的日志函数** - 确保统一的日志格式和性能统计
2. **设置合理的慢查询阈值** - 根据应用特点调整（默认 1.0s）
3. **定期检查性能统计** - 在开发和生产环境中监控慢查询
4. **应用启动时检查连接** - 使用 `check_connection()` 验证数据库可用性

---

## 示例

### 应用启动检查

已在 `backend/server/main.py` 中集成：

```python
@app.on_event("startup")
async def startup_event():
    """应用启动时检查连接"""
    from infrastructure.utils.neo4j_utils import check_neo4j_connection

    health = check_neo4j_connection(driver)
    if not health['healthy']:
        raise Exception(f"Neo4j 连接失败: {health.get('error')}")

    logger.info(f"✅ Neo4j 连接正常 (版本: {health['version']}, 响应: {health['response_time_ms']}ms)")
```

### 查询性能监控

通过管理员 API（`/admin/query-stats`）或直接调用：

```python
stats = get_query_stats_summary()
if stats['slow_queries_count'] > 0:
    logger.warning(f"检测到 {stats['slow_queries_count']} 个慢查询")
    for sq in get_slow_queries(limit=5):
        logger.warning(f"  {sq['elapsed']:.2f}s - {sq['cypher_preview']}")
```

---

## 更新日志

### v2.0 (当前)
- ✅ 添加查询性能统计 (`Neo4jQueryStats`)
- ✅ 添加慢查询检测和警告
- ✅ 添加连接健康检查
- ✅ 所有函数提供便捷的函数式接口
- ❌ 移除未使用的结果转换、查询构建、结果导出功能

### v1.0
- ✅ 参数内联
- ✅ 结果格式化
- ✅ 查询日志记录

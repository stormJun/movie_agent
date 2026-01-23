# 1.1.2 - Langfuse 可观测性集成

## 版本信息

- **版本号**: 1.1.2
- **发布日期**: 2025-01-23
- **状态**: 可选集成（非必需）

## 文档目录

- [Langfuse 集成部署指南](./langfuse-integration.md) - 完整的集成和部署文档

## 概述

本版本提供了 Langfuse 可观测性平台的可选集成，用于：

1. **LLM 调用追踪**: 自动记录 prompt、response、tokens、cost
2. **长期存储**: 持久化存储历史数据（Redis 只有 1 小时 TTL）
3. **强大的分析**: 90 分位延迟、成本趋势、模型对比
4. **Web UI**: 开箱即用的可视化界面

## 与现有功能的关系

### 现有 Debug 模式（1.1.0）

- ✅ 前端深度集成（侧边栏展示）
- ✅ 数据本地化（Redis）
- ✅ UI 完全自定义
- ❌ 无 LLM 调用追踪
- ❌ 无长期存储

### Langfuse 集成（1.1.2）

- ✅ LLM 调用自动追踪
- ✅ 长期存储（PostgreSQL）
- ✅ 强大的分析能力
- ❌ 需要外部服务（PostgreSQL + ClickHouse + Redis）
- ❌ 固定 UI

### 推荐方案：两者结合

- **用户看到**: 前端侧边栏实时调试信息（Debug 模式）
- **开发者看到**: Langfuse Web UI 长期分析（Langfuse）

## 部署复杂度对比

| 方案 | 组件 | 内存需求 | 存储需求 | 部署复杂度 |
|------|------|---------|---------|-----------|
| **Debug 模式** | Redis（可选） | ~100MB | ~100MB | 极简 |
| **Langfuse 最小化** | PostgreSQL | ~2GB | ~10GB | 中等 |
| **Langfuse 标准** | PostgreSQL + ClickHouse + Redis | ~3-4GB | ~15GB | 中等 |

## 使用场景建议

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| **开发/调试** | Debug 模式 | 实时反馈，无需额外组件 |
| **生产环境监控** | Langfuse | 长期存储、成本分析 |
| **性能优化** | Langfuse | Token 统计、延迟分析 |
| **政府/金融/医疗** | Debug 模式 | 数据不出内网 |
| **前端深度定制** | Debug 模式 | 完全自定义 UI |

## 快速开始

### 1. 最小化部署（开发/测试）

```bash
# 使用现有 PostgreSQL
docker run -d \
  --name langfuse \
  -p 3000:3000 \
  -e DATABASE_URL="postgresql://postgres:password@host.docker.internal:5432/langfuse" \
  langfuse/langfuse:latest

# 访问 http://localhost:3000
```

### 2. 标准部署（推荐）

```bash
# 使用 docker-compose
cd /Users/songxijun/workspace/otherProject/movie_agent
docker-compose -f docker-compose.langfuse.yml up -d

# 访问 http://localhost:3000
```

详细步骤请参考 [Langfuse 集成部署指南](./langfuse-integration.md)。

## 环境变量配置

在 `.env` 文件中添加：

```bash
# 是否启用 Langfuse
LANGFUSE_ENABLED=false

# Langfuse API Keys
LANGFUSE_PUBLIC_KEY="pk-xxx"
LANGFUSE_SECRET_KEY="sk-xxx"

# Langfuse 服务地址
LANGFUSE_HOST="http://localhost:3000"
```

## 相关文档

- [1.1.0 - Debug 流式分离](../1.1.0/debug-streaming-separation.md) - 现有 Debug 模式设计
- [Langfuse 官方文档](https://langfuse.com/docs)

## 维护者

- **文档作者**: Claude Code
- **最后更新**: 2025-01-23

## 反馈与问题

如有问题，请在项目仓库提交 Issue。

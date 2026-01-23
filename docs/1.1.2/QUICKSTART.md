# Langfuse 集成快速入门

> **版本**: 1.1.2
> **更新时间**: 2025-01-23

## 前置条件

✅ 已完成以下部署：
- PostgreSQL (localhost:5433)
- Redis (localhost:6379)
- ClickHouse (localhost:8123, 9002)
- Langfuse (localhost:3000)

---

## 第一步：获取 Langfuse API Keys

### 1. 访问 Langfuse Web UI

打开浏览器：http://localhost:3000

### 2. 创建账户

如果是首次访问：
1. 点击 "Sign up"
2. 输入邮箱和密码
3. 完成注册

### 3. 获取 API Keys

1. 登录后，点击左下角 **Settings** (齿轮图标)
2. 选择 **API Keys**
3. 复制以下两个值：
   - **Public Key**: `pk-xxx...`
   - **Secret Key**: `sk-xxx...`

---

## 第二步：配置环境变量

编辑项目根目录的 `.env` 文件：

```bash
# === Langfuse 可观测性 ===
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY="pk-xxx"  # 替换为你的 Public Key
LANGFUSE_SECRET_KEY="sk-xxx"  # 替换为你的 Secret Key
LANGFUSE_HOST="http://localhost:3000"
```

---

## 第三步：安装 Python 依赖

```bash
cd /Users/songxijun/workspace/otherProject/movie_agent
pip install langfuse==2.60.2
```

---

## 第四步：重启后端服务

```bash
# 停止现有服务
pkill -f "python.*server"

# 重新启动
bash scripts/dev.sh backend
```

---

## 第五步：验证集成

### 发送测试请求

```bash
curl -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好，请介绍一下这部电影",
    "session_id": "test_session",
    "kb_prefix": "movie",
    "use_stream": true
  }'
```

### 查看 Langfuse 追踪

1. 打开 http://localhost:3000/traces
2. 你应该能看到一个新的 Trace 记录
3. 点击 Trace 可以查看详细信息：
   - **Trace ID**: 唯一标识符
   - **Span 列表**: 调用链（`generate_rag_answer_stream` → `OpenAI.chat`）
   - **LLM 详情**: Token 统计、成本、延迟

---

## 集成架构

### 自动追踪点

本项目已在以下函数添加 `@langfuse_observe()` 装饰器：

| 函数 | 文件 | 说明 |
|------|------|------|
| `generate_general_answer` | `infrastructure/llm/completion.py` | 通用回答生成 |
| `generate_general_answer_stream` | `infrastructure/llm/completion.py` | 通用流式回答 |
| `generate_rag_answer` | `infrastructure/llm/completion.py` | RAG 回答生成 |
| `generate_rag_answer_stream` | `infrastructure/llm/completion.py` | RAG 流式回答 |

### 装饰器功能

`@langfuse_observe()` 装饰器会自动：

1. ✅ **捕获输入**：记录函数参数
2. ✅ **捕获输出**：记录返回值
3. ✅ **创建 Span**：在 Langfuse 中创建调用链
4. ✅ **关联 LLM**：自动追踪底层的 OpenAI 调用

---

## Langfuse Web UI 功能

### 主要页面

| 页面 | 路径 | 功能 |
|------|------|------|
| **Traces** | `/traces` | 所有请求追踪记录 |
| **Trace 详情** | `/trace/{id}` | 单个请求的详细调用链 |
| **Scores** | `/scores` | 评分和质量分析 |
| **Datasets** | `/datasets` | 测试数据集管理 |
| **Users** | `/users` | 用户列表和活动 |
| **Query** | `/query` | SQL 查询界面 |
| **Settings** | `/settings` | 配置和 API Keys |

### 典型 Trace 详情

```
Trace: 2025-01-23 12:34:56
├── Span: generate_rag_answer_stream
│   ├── Input: {"question": "你好", "context": "..."}
│   ├── Output: "你好！我是..."
│   ├── Duration: 1.2s
│   └── Span: OpenAI.chat
│       ├── Model: gpt-4o
│       ├── Tokens: 256 (123 prompt + 133 completion)
│       ├── Cost: $0.005
│       └── Latency: 1.1s
```

---

## 与现有 Debug 模式共存

### Debug 模式（1.1.0）

- ✅ 前端侧边栏实时展示
- ✅ 数据本地化（Redis）
- ✅ UI 完全自定义
- ❌ 无 LLM 调用追踪

### Langfuse（1.1.2）

- ✅ LLM 调用自动追踪
- ✅ 长期存储（PostgreSQL + ClickHouse）
- ✅ 强大的分析能力
- ❌ 需要外部服务

### 推荐配置

```bash
# 开发环境：同时启用
FRONTEND_DEFAULT_DEBUG=true   # 前端侧边栏显示调试信息
LANGFUSE_ENABLED=true          # 后端记录到 Langfuse

# 生产环境：仅 Langfuse
FRONTEND_DEFAULT_DEBUG=false  # 关闭前端调试
LANGFUSE_ENABLED=true          # 保留长期可观测性
```

---

## 故障排查

### 问题 1：看不到 Trace 数据

**检查配置**：
```bash
# 确认环境变量已设置
echo $LANGFUSE_ENABLED
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY

# 重启后端
bash scripts/dev.sh backend
```

### 问题 2：连接超时

**检查 Langfuse 服务**：
```bash
docker ps | grep langfuse_server
curl http://localhost:3000/api/health
```

### 问题 3：依赖安装失败

**使用虚拟环境**：
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 下一步

1. **创建评分规则**：在 Langfuse 中配置自定义评分
2. **建立测试数据集**：将典型问题添加到 Datasets
3. **设置成本告警**：监控 Token 使用和成本趋势
4. **对比分析**：比较不同模型的性能

---

## 相关文档

- [完整集成文档](./langfuse-integration.md)
- [Debug 模式设计](../1.1.0/debug-streaming-separation.md)
- [Langfuse 官方文档](https://langfuse.com/docs)

# 快速开始指南

## One-API 部署

使用 Docker 启动 One-API：

```bash
docker run --name one-api -d --restart always \
  -p 13000:3000 \
  -e TZ=Asia/Shanghai \
  -v /home/ubuntu/data/one-api:/data \
  justsong/one-api
```

在 One-API 控制台中配置第三方 API Key。本项目的所有 API 请求将通过 One-API 转发。

该项目的官方地址：https://github.com/songquanpeng/one-api

具体的填写方式可以看[这里](https://github.com/1517005260/graph-rag-agent/issues/7#issuecomment-2906770240)

**注意**：默认用管理员账号登录，用户名root，密码123456，进去之后可以改密码

### 或者

1. 直接使用第三方代理平台，如[云雾api](https://yunwu.ai/)等，使用方法同one-api，`.env`中api-key写中转站给你的key，url写中转站的url

2. 使用更先进的[new-api](https://github.com/QuantumNous/new-api)，使用方法基本同one-api

```bash
# 使用SQLite部署new-api
docker run --name new-api -d --restart always -p 3000:3000 -e TZ=Asia/Shanghai -v /home/ubuntu/data/new-api:/data calciumion/new-api:latest
```


## Neo4j 启动

```bash
cd graph-rag-agent/
docker compose up -d
```

默认账号密码：

```
用户名：neo4j
密码：12345678
```

## 环境搭建

```bash
conda create -n graphrag python==3.10
conda activate graphrag
cd graph-rag-agent/
pip install -r requirements.txt
```

注意：如需处理 `.doc` 格式（旧版 Word 文件），请根据操作系统安装相应依赖，详见 `requirements.txt` 中注释：

```txt
# Linux
sudo apt-get install python-dev-is-python3 libxml2-dev libxslt1-dev antiword unrtf poppler-utils

# Windows
pywin32>=302

textract==1.6.3  # Windows 无需安装
```

如果遇到报错：`OSError: [WinError 1114] 动态链接库(DLL)初始化例程失败。 Error loading "D:\anaconda\envs\graphrag\lib\site-packages\torch\lib\c10.dll" or one of its dependencies.` 是因为下载了torch2.9.0版本，遇到此问题请手动降级torch，比如`pip install torch==2.8.0`即可。

## 环境变量配置 (.env)

### 配置说明

项目配置已统一至 `.env` 文件，除知识图谱实体/关系模式外，所有运行参数均可通过环境变量覆盖。请在项目根目录创建 `.env` 文件进行配置。

### 配置入口索引（避免改错文件）

- `backend/config/`：服务/API 侧配置与开关（端口、路由开关、SSE 心跳等）
- `backend/infrastructure/config/`：基础设施侧配置与注入（Neo4j/LLM/缓存路径等，会注入到 core）

### 必选配置项

以下配置为必填项，项目无法运行时需首先检查这些配置：

```env
# ===== LLM 模型配置 =====
OPENAI_API_KEY = 'sk-xxx'
OPENAI_BASE_URL = 'http://localhost:13000/v1'
OPENAI_EMBEDDINGS_MODEL = 'text-embedding-3-large'
OPENAI_LLM_MODEL = 'gpt-4o'
RAG_ANSWER_TIMEOUT_S = 180

# ===== Neo4j 数据库配置 =====
NEO4J_URI = 'neo4j://localhost:7687'
NEO4J_USERNAME = 'neo4j'
NEO4J_PASSWORD = '12345678'
```

### 推荐修改配置项

以下配置根据实际使用场景建议调整：

```env
# ===== 缓存向量模型配置 =====
# 推荐使用第三方embedding模型api，省事。以下是需要下载的配置

# ===== 并发与性能配置 =====
# 根据机器性能调整，4核CPU推荐值如下
FASTAPI_WORKERS = 2
MAX_WORKERS = 4
MA_WORKER_EXECUTION_MODE = 'parallel'
MA_WORKER_MAX_CONCURRENCY = 4
BATCH_SIZE = 100

# ===== GDS 内存配置 =====
# 根据服务器内存调整，单位 GB
GDS_MEMORY_LIMIT = 6

# ===== 文本处理参数 =====
# 根据文档特性调整分块大小
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
```

### 默认即可配置项

以下配置一般无需修改，保持默认值即可：

```env
# ===== LLM 生成参数 =====
TEMPERATURE = 0
MAX_TOKENS = 2000
VERBOSE = True

# ===== RAG synthesize 兜底 =====
RAG_SYNTHESIZE_MAX_CHARS = 1500
RAG_SYNTHESIZE_MAX_EVIDENCE = 3
RAG_SYNTHESIZE_EVIDENCE_STRATEGY = 'score'  # score / confidence / first

# ===== 文本处理 =====
MAX_TEXT_LENGTH = 500000
SIMILARITY_THRESHOLD = 0.9

# ===== RAG 语义/回答格式 =====
# 语义默认值只在 `backend/config/rag_semantics.py` 定义；infra 通过 overrides 注入到 core settings。
RESPONSE_TYPE = '多个段落'

# ===== 批处理大小 =====
ENTITY_BATCH_SIZE = 50
CHUNK_BATCH_SIZE = 100
EMBEDDING_BATCH_SIZE = 64
LLM_BATCH_SIZE = 5
COMMUNITY_BATCH_SIZE = 50

# ===== GDS 运行参数 =====
GDS_CONCURRENCY = 4
GDS_NODE_COUNT_LIMIT = 50000
GDS_TIMEOUT_SECONDS = 300

# ===== 实体消歧配置 =====
DISAMBIG_STRING_THRESHOLD = 0.7
DISAMBIG_VECTOR_THRESHOLD = 0.85
DISAMBIG_NIL_THRESHOLD = 0.6
DISAMBIG_TOP_K = 5
ALIGNMENT_CONFLICT_THRESHOLD = 0.5
ALIGNMENT_MIN_GROUP_SIZE = 2

# ===== Neo4j 连接池 =====
NEO4J_MAX_POOL_SIZE = 10
NEO4J_REFRESH_SCHEMA = false

# ===== KB 路由规则 =====
KB_ROUTING_RULES_PATH = './backend/domain/config/kb_routing.yaml'
KB_ROUTING_RULES_RELOAD = false

# ===== 运行时目录（生成产物 / 第三方依赖缓存） =====
RUNTIME_ROOT = './files'
# tiktoken 等第三方依赖的缓存目录（可选；默认会使用 RUNTIME_ROOT/tiktoken）
# TIKTOKEN_CACHE_DIR = './files/tiktoken'

# ===== 相似实体检测 =====
SIMILAR_ENTITY_WORD_EDIT_DISTANCE = 3
SIMILAR_ENTITY_BATCH_SIZE = 500
SIMILAR_ENTITY_MEMORY_LIMIT = 6
SIMILAR_ENTITY_TOP_K = 10

# ===== 搜索工具参数 =====
SEARCH_VECTOR_LIMIT = 5
SEARCH_TEXT_LIMIT = 5
SEARCH_SEMANTIC_TOP_K = 5
SEARCH_RELEVANCE_TOP_K = 5

## （可选）mem0 长期记忆自托管

本项目支持通过 `MEM0_BASE_URL` 对接 mem0（长期记忆）服务；仓库内也提供一个最小的 mem0-compatible 服务端实现。

启动（复用本仓库的 Postgres，并连接你本地已运行的 Milvus）：

```bash
docker compose -f docker-compose.yaml -f docker-compose.mem0.yaml up -d --build
```

在 `.env` 打开并指向服务：

```env
MEMORY_ENABLE=true
MEMORY_WRITE_ENABLE=true
MEM0_BASE_URL="http://localhost:8830"
```

如果你使用 Qwen/DashScope（OpenAI 兼容接口）做 embeddings，建议给 mem0 服务单独配置，避免和本机其他服务的 `OPENAI_*` 冲突：

```env
MEM0_OPENAI_API_KEY=...
MEM0_OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MEM0_OPENAI_EMBEDDINGS_MODEL=text-embedding-v3
```
NAIVE_SEARCH_TOP_K = 3

LOCAL_SEARCH_TOP_CHUNKS = 3
LOCAL_SEARCH_TOP_COMMUNITIES = 3
LOCAL_SEARCH_TOP_OUTSIDE_RELS = 10
LOCAL_SEARCH_TOP_INSIDE_RELS = 10
LOCAL_SEARCH_TOP_ENTITIES = 10
LOCAL_SEARCH_INDEX_NAME = 'vector'

GLOBAL_SEARCH_LEVEL = 0
GLOBAL_SEARCH_BATCH_SIZE = 5

HYBRID_SEARCH_ENTITY_LIMIT = 15
HYBRID_SEARCH_MAX_HOP = 2
HYBRID_SEARCH_TOP_COMMUNITIES = 3
HYBRID_SEARCH_BATCH_SIZE = 10
HYBRID_SEARCH_COMMUNITY_LEVEL = 0

# ===== Server 运行参数 =====
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
SERVER_RELOAD = false
SERVER_LOG_LEVEL = 'info'
SERVER_WORKERS = 2
# SSE keepalive 心跳间隔（秒）；长检索阶段避免代理/网关断连
SSE_HEARTBEAT_S = 15

# ===== KB 自动路由（movie/edu）=====
KB_AUTO_ROUTE = true
KB_AUTO_ROUTE_OVERRIDE = true
KB_AUTO_ROUTE_MIN_CONFIDENCE = 0.75

# ===== Phase 2（handlers + backend/infrastructure/rag）=====
PHASE2_ENABLE_KB_HANDLERS = true
# 旧开关保留兼容，未设置 PHASE2_ENABLE_KB_HANDLERS 时会回落到此值
PHASE2_ENABLE_BUSINESS_AGENTS = true

# ===== 前端运行参数 =====
FRONTEND_API_URL = 'http://localhost:8000'
FRONTEND_DEFAULT_AGENT = 'naive_rag_agent'
FRONTEND_DEFAULT_DEBUG = false
FRONTEND_SHOW_THINKING = true
FRONTEND_USE_DEEPER_TOOL = true
FRONTEND_USE_STREAM = true
FRONTEND_USE_CHAIN_EXPLORATION = true

# ===== 知识图谱可视化参数 =====
KG_PHYSICS_ENABLED = true
KG_NODE_SIZE = 25
KG_EDGE_WIDTH = 2
KG_SPRING_LENGTH = 150
KG_GRAVITY = -5000

# ===== Agent 参数 =====
AGENT_RECURSION_LIMIT = 5
AGENT_CHUNK_SIZE = 4
AGENT_STREAM_FLUSH_THRESHOLD = 40
DEEP_AGENT_STREAM_FLUSH_THRESHOLD = 80
FUSION_AGENT_STREAM_FLUSH_THRESHOLD = 60
```

### 可选配置项

以下配置为可选功能，不需要可以不配置或注释掉：

```env
# ===== LangSmith 监控（可选）=====
# 不需要可以完全注释掉此部分
LANGSMITH_TRACING = true
LANGSMITH_ENDPOINT = "https://api.smith.langchain.com"
LANGSMITH_API_KEY = "xxx"
LANGSMITH_PROJECT = "xxx"
```

### 配置模板获取

完整配置模板请参考项目根目录的 `.env.example` 文件，可直接复制重命名为 `.env` 后修改。

### 同库多知识库共存（可选）

如需在同一个 Neo4j 库中同时存放多个知识库（例如 `movie` + `edu`），需要同时做到“写入命名空间前缀化 + 搜索侧前缀过滤 + 索引/社区命名空间隔离”：

- **document 模式（学生管理等）**：设置 `DOCUMENT_KB_PREFIX=edu`，使写入的 `__Entity__.id/__Chunk__.id/__Document__.fileName` 统一加 `edu:` 前缀。
- **structured 模式（电影）**：设置 `STRUCTURED_KB_PREFIX=movie`，使 Canonical 层 `__Entity__.id/__Chunk__.id/__Document__.fileName` 统一加 `movie:` 前缀。
- **搜索侧隔离**：按当前运行的知识库设置过滤前缀（例如电影：`GRAPH_ENTITY_ID_PREFIX_FILTER=movie:`、`GRAPH_CHUNK_ID_PREFIX_FILTER=movie:`、`GRAPH_COMMUNITY_ID_PREFIX=movie:`），避免共库串 KB。
- **索引名称隔离（建议）**：为不同 KB 使用不同 index name（例如电影：`ENTITY_VECTOR_INDEX_NAME=movie_vector`、`CHUNK_VECTOR_INDEX_NAME=movie_chunk_vector`；学生：`edu_vector`/`edu_chunk_vector`）。

### 补跑社区摘要（可选）

Global Search 依赖 `__Community__.summary/full_content`。结构化模式默认会跳过社区摘要（避免成本/耗时），如需补跑可使用：

```bash
GRAPH_ENTITY_ID_PREFIX_FILTER=movie: \
GRAPH_CHUNK_ID_PREFIX_FILTER=movie: \
GRAPH_COMMUNITY_ID_PREFIX=movie: \
COMMUNITY_SUMMARY_LIMIT=0 \
COMMUNITY_SUMMARY_ONLY_MISSING=true \
COMMUNITY_SUMMARY_MAX_WORKERS=4 \
GRAPH_SKIP_SIMILAR_ENTITY=true \
GRAPH_SKIP_ENTITY_MERGE=true \
GRAPH_SKIP_ENTITY_QUALITY=true \
GRAPH_SKIP_COMMUNITY_SUMMARY=false \
BUILD_RUN_ENTITY_INDEX=false \
BUILD_RUN_COMMUNITY_DETECTION=false \
bash scripts/py.sh infrastructure.integrations.build.build_index_and_community
```

### 模型兼容性说明

全流程测试通过的模型：
- DeepSeek (20241226版本)
- GPT-4o

已知问题模型：
- DeepSeek (20250324版本)：幻觉问题严重，可能导致实体抽取失败
- Qwen 系列：可以抽取实体，但与 LangChain/LangGraph 兼容性存在问题，建议使用其官方 [Qwen-Agent](https://qwen.readthedocs.io/zh-cn/latest/framework/qwen_agent.html) 框架

## 项目初始化

```bash
pip install -e .
```

## 知识图谱原始文件放置

请将原始文件放入 `files/` 文件夹，支持有目录的存放。当前支持以下格式（采用简单分块，后续会优化处理方式）：

```
- TXT（纯文本）
- PDF（PDF 文档）
- MD（Markdown）
- DOCX（新版 Word 文档）
- DOC（旧版 Word 文档）
- CSV（表格）
- JSON（结构化文本）
- YAML/YML（配置文件）
```

## 知识图谱实体与关系配置

知识图谱的**实体类型**和**关系类型**建议通过 `.env` 配置（对应 `backend/config/rag.py`），无需再改 `backend/graphrag_agent/config/settings.py`：

```bash
# 领域/知识库语义配置
KB_NAME='华东理工大学'
GRAPH_THEME='华东理工大学学生管理'
GRAPH_ENTITY_TYPES='学生类型,奖学金类型,处分类型,部门,学生职责,管理规定'
GRAPH_RELATIONSHIP_TYPES='申请,评选,违纪,资助,申诉,管理,权利义务,互斥'

# 冲突解决策略：manual_first / auto_first / merge
GRAPH_CONFLICT_STRATEGY='manual_first'
# 社区检测算法：leiden / sllpa
GRAPH_COMMUNITY_ALGORITHM='leiden'
```

如需硬编码默认值（不推荐），可直接改 `backend/config/rag.py`。

## 使用 graphrag_agent 前的 bootstrap

如果在脚本/REPL 中直接调用 `graphrag_agent`（而不是通过 `server` 或 `infrastructure` 入口），
请先注入基础设施 Provider，否则会因未配置端口而报错：

```python
from infrastructure.bootstrap import bootstrap_core_ports

bootstrap_core_ports()
```

## 构建知识图谱

```bash
cd graph-rag-agent/

# 初始全量构建
bash scripts/py.sh infrastructure.integrations.build.main

# 单次变量（增量、减量）构建：
bash scripts/py.sh infrastructure.integrations.build.incremental_update --once

# 后台守护进程，定期变量更新：
bash scripts/py.sh infrastructure.integrations.build.incremental_update --daemon
```

**注意：** `main.py`是构建的全流程，如果需要单独跑某个流程，请先完成实体索引的构建，再进行 chunk 索引构建，否则会报错（chunk 索引依赖实体索引）。

## 知识图谱搜索测试

```bash
cd graph-rag-agent/test

# 查询前可以注释掉不想测试的Agent，防止运行过慢

# 非流式查询
python search_without_stream.py

# 流式查询
python search_with_stream.py
```

## 知识图谱评估

```bash
cd test/evaluation
# 查看对应 README 获取更多信息
```

## 前端示例问题配置

通过 `.env` 配置（逗号分隔）：

```bash
FRONTEND_EXAMPLES='旷课多少学时会被退学？,国家奖学金和国家励志奖学金互斥吗？,优秀学生要怎么申请？,那上海市奖学金呢？'
```

## 配置体系说明

项目配置分为三层：

1. `.env` 文件：所有运行时参数、密钥、性能调优参数
2. `backend/config/rag.py`：领域/RAG 语义配置默认值（实体/关系类型、示例问题、工具描述等）
3. 配置入口（按职责拆分，避免“该改哪个”）
   - `backend/config/settings.py`：服务侧运行参数与功能开关（HTTP/SSE/Phase2 等）
   - `backend/infrastructure/config/settings.py`：基础设施侧配置（Neo4j/LLM/缓存/路径/路由阈值等）
   - `frontend/frontend_config/settings.py`：前端界面配置（对接后端地址、展示开关等）

大部分配置可通过 `.env` 直接控制，无需修改代码。

## 深度搜索优化（建议禁用前端超时）

如需开启深度搜索功能，建议禁用前端超时限制，修改 `frontend/utils/api.py`：

```python
response = requests.post(
    f"{API_URL}/api/v1/chat",
    json={
        "message": message,
        "session_id": st.session_state.session_id,
        "debug": st.session_state.debug_mode,
        "agent_type": st.session_state.agent_type
    },
    # timeout=120  # 建议注释掉此行
)
```

## 中文字体支持（Linux）

如需中文图表显示，可参考[字体安装教程](https://zhuanlan.zhihu.com/p/571610437)。默认使用英文绘图（`matplotlib`）。


## 启动前后端服务

```bash
# 启动后端
cd graph-rag-agent/
bash scripts/dev.sh backend

# 启动前端
cd graph-rag-agent/
streamlit run frontend/app.py
```

**注意**：由于langchain版本问题，目前的流式是伪流式实现，即先完整生成答案，再分段返回。

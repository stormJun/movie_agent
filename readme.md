# movie_agent

基于 GraphRAG 的知识图谱问答/检索系统示例项目，包含：
- FastAPI 后端（`backend/server/`）
- GraphRAG 核心运行时与 Agents（`backend/graphrag_agent/`）
- 构建/摄取管道与集成（`backend/infrastructure/`）
- React 前端（`frontend-react/`）

## 目录结构

```
backend/        # 后端全部代码（含 server、graphrag_agent、infrastructure）
frontend-react/ # React UI (Vite)
test/           # unittest 回归测试
datasets/       # 数据输入（示例/公开数据）
documents/      # 文档输入（如用于摄取的语料）
files/          # 生成物/缓存/导出（建议与源数据分离）
scripts/        # 开发/测试脚本封装
```

## 快速开始

1) 创建环境并安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) 配置环境变量

```bash
cp .env.example .env
```

3) 启动后端

```bash
bash scripts/dev.sh backend
```

4) 启动前端（可选，React）

```bash
bash scripts/dev.sh frontend
```

## Neo4j（可选但推荐）

项目默认使用 Neo4j 作为图存储，常见配置参考：
- `docker/docker-compose.yaml`
- `docs/03-部署指南/Neo4j配置.md`

## 测试

```bash
bash scripts/test.sh
```

## 数据与产物约定

- 输入数据放 `datasets/`、`documents/`
- 生成物放 `files/`（默认不提交到 git）
- 不要提交 `.env` 等敏感信息

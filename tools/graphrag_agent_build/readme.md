# 知识图谱构建模块（Build Tools）

本目录提供 GraphRAG 的“构建/增量更新”工具链（图谱构建、索引创建、社区检测、增量更新）。

实现代码位置：
- `tools/graphrag_agent_build/graphrag_agent_build/`
- Python 包：`graphrag_agent_build`
- CLI：`graphrag-agent-build`

兼容导入路径：
- `infrastructure.integrations.build.*`（通过 `backend/infrastructure/integrations/build/__init__.py` shim 映射到已安装的 `graphrag_agent_build`）

## 运行方式

方式 1：直接在 monorepo 里运行（不安装 runtime/tools 包）

```bash
bash scripts/py.sh infrastructure.integrations.build.main
```

方式 2：安装 core + runtime + build tools 后运行（推荐，不依赖 PYTHONPATH）

```bash
pip install .
pip install ./backend
pip install ./tools/graphrag_agent_build

graphrag-agent-build
```

# 添加新 Agent

> 目标：在不破坏既有能力的前提下，新增一个可用的 Agent。

## 1. 选择基类与职责

- 推荐从 `backend/graphrag_agent/agents/base.py` 派生，明确输入/输出约定。
- 先决定 Agent 的“职责边界”：只做检索与拼接，还是包含多步规划/执行。

## 2. 添加实现文件

在 `backend/graphrag_agent/agents/` 下新增模块，例如：

- 文件名：`<your_agent>.py`（放在 `backend/graphrag_agent/agents/` 目录下）

并实现一个类（建议 `PascalCase`），在构造函数里注入需要的模型/工具。

## 3. 注册到系统配置

按当前分层，建议在服务层注册/路由（并通过 `.env` 控制默认行为）：

- 将新 Agent 加入可选列表/路由逻辑（参考 `backend/infrastructure/agents/rag_factory/manager.py`、`backend/infrastructure/routing/orchestrator/`）
- 若涉及领域语义（KB 名称、实体/关系类型、示例问题、工具描述），优先改 `.env`（对应 `backend/config/rag.py`）

## 4. 暴露到后端与前端（可选）

- FastAPI：在 `backend/infrastructure/agents/rag_factory/manager.py` 与相关 router 中加入分发逻辑（按现有模式）。
- Streamlit：在 `frontend/app.py` 或侧边栏中添加可选项（按现有模式）。

## 5. 最小验证

```bash
bash scripts/test.sh
```

建议补充一个最小用例：给定输入问题，Agent 能返回结构化输出且不中断。

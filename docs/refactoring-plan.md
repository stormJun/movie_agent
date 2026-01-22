# GraphRAG Agent 架构重构计划

> 状态：本仓库后端代码已收敛到 `backend/`（根目录不再保留 `server/`、`graphrag_agent/` 等后端包目录）。
> 本文档保留为“历史迁移计划 + 约束说明”，避免后续又把后端包移回仓库根目录。

## 问题总结

1. **目录混用导致漂移** - 历史上根目录与 `backend/` 混用，容易反复迁移/引用错路径（现已统一）
2. **legacy rag_layer/ 过于单薄** - 只有配置，不符合"层"的定位（已迁至 `backend/infrastructure/rag/`）
3. **分层边界易被破坏** - 缺少“目录约束 + 回归保护”，容易在迭代中把后端包移出 `backend/`（现已补充）

## 目标架构

```
graph-rag-agent/
├── backend/graphrag_agent/          # 核心GraphRAG引擎（可复用）
├── backend/application/             # 应用编排层（业务流程）
├── backend/domain/                  # 领域层（语义/实体）
├── backend/infrastructure/          # 技术基础设施（RAG/路由/缓存/模型/DB）
├── backend/config/                  # 服务配置（settings/database/rag）
└── backend/server/                  # API接口层（HTTP）
    ├── main.py
    ├── api/
    └── models/
```

## 迁移步骤

### 已完成（归档）

- 后端目录统一：所有后端代码位于 `backend/`
- 旧的根目录后端包（如 `server/`、`graphrag_agent/`）已下线（在 git 里表现为删除）
- import 路径已切到 `backend.*`（后续 Phase2.5 会进一步“去掉 `backend.` 前缀”，但物理目录仍在 `backend/` 下重构）

## 依赖规则

1. **backend/graphrag_agent/** 不依赖其他层
2. **backend/infrastructure/** 依赖 graphrag_agent + config
3. **backend/domain/** 依赖 graphrag_agent
4. **backend/application/** 依赖 domain + infrastructure
5. **backend/server/** 只依赖 application + config（必要时引用 infrastructure 工具）

## 注意事项

- ✅ 采用渐进式迁移，每步都可运行测试
- ✅ 目录约束写入文档（`AGENTS.md` / 架构文档 / 开发指南）
- ✅ 增加回归保护：禁止根目录出现后端包目录（见 `test/test_backend_layout.py`）
- ✅ CI/CD配置同步更新

## 预期收益

1. **清晰的分层** - 每个目录职责明确
2. **易于维护** - 新功能有明确的归属位置
3. **可复用性** - core/可独立作为包发布
4. **可扩展性** - 新增领域（如医疗、金融）只需在backend/domain/下添加

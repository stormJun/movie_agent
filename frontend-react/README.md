# GraphRAG React 前端

基于 React + TypeScript + Vite + Ant Design 的现代化前端界面。

## ✨ 功能特性

- 🎨 **Chat 工作台**: 支持多种 Agent 类型（Graph, Hybrid, NaiveRAG, DeepResearch, Fusion）
- 📊 **知识图谱可视化**: 基于 @antv/g6 的交互式图谱展示
- 🔄 **流式输出**: 基于 SSE 的实时响应（支持中断）
- 🐛 **调试模式**: 执行日志、推理过程、迭代信息、性能监控
- 📝 **源文档引用**: 点击查看原始文档内容
- 👍 **反馈机制**: 正向/负向反馈提交
- 📈 **性能监控**: 请求耗时统计（avg/p95/max）
- 🗂️ **图谱管理**: 实体管理、关系管理、图谱探索

## 🚀 快速开始

### 前置要求

- Node.js >= 18
- npm >= 9

### 安装依赖

```bash
cd frontend-react
npm install
```

### 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，确保后端地址正确：

```env
VITE_BACKEND_ORIGIN=http://localhost:8324
```

### 启动开发服务器

```bash
# 方式 1: 使用脚本
./start.sh

# 方式 2: 直接运行
npm run dev
```

访问: http://localhost:5174

### 启动后端服务

```bash
# 在项目根目录
python server/main.py
```

### 生产构建

```bash
npm run build
npm run preview  # 预览构建结果
```

## 📁 项目结构

```
frontend-react/
├── src/
│   ├── app/              # 全局配置
│   │   ├── layout/       # 布局组件
│   │   ├── settings.ts   # API 配置
│   │   └── examples.ts   # 示例问题
│   ├── components/       # 可复用组件
│   │   ├── GraphView.tsx          # 图谱可视化
│   │   └── KnowledgeGraphPanel.tsx # KG 面板
│   ├── pages/           # 页面组件
│   │   ├── ChatPage.tsx           # Chat 工作台 ⭐
│   │   ├── GraphExplorePage.tsx   # 图谱探索
│   │   ├── EntitiesPage.tsx       # 实体管理
│   │   ├── RelationsPage.tsx      # 关系管理
│   │   ├── SourcesPage.tsx        # 源文档管理
│   │   └── SettingsPage.tsx       # 设置页面
│   ├── services/        # API 调用层
│   │   ├── http.ts      # Axios 实例
│   │   ├── chat.ts      # 聊天 API
│   │   ├── graph.ts     # 图谱 API
│   │   ├── feedback.ts  # 反馈 API
│   │   └── source.ts    # 源文档 API
│   ├── types/           # TypeScript 类型定义
│   └── utils/           # 工具函数
│       └── sse.ts       # SSE 处理
├── .env.example         # 环境变量模板
├── package.json
├── vite.config.ts       # Vite 配置
└── README.md
```

## 🔧 配置说明

### API 代理配置

开发模式下，Vite 会自动代理 `/api/*` 请求到后端服务器：

```typescript
// vite.config.ts
server: {
  port: 5174,
  proxy: {
    "/api": {
      target: "http://localhost:8324",  // 后端地址
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ""),
    },
  },
}
```

### 超时配置

已针对深度研究 Agent 优化超时设置：

```typescript
// src/services/http.ts
export const http = axios.create({
  timeout: 300_000,  // 5分钟超时
});
```

## 🆚 与 Streamlit 版本对比

| 功能 | Streamlit | React | 优势 |
|------|-----------|-------|------|
| Chat 界面 | ✅ | ✅ | 对等 |
| 流式输出 | ✅ | ✅ | React 性能更好 |
| 知识图谱 | ✅ | ✅ | React 交互更丰富 |
| 调试模式 | ✅ | ✅ | React 结构化展示 |
| 性能监控 | ❌ | ✅ | **React 独有** |
| 图谱管理 | ❌ | ✅ | **React 独有** |
| 设置页面 | ❌ | ✅ | **React 独有** |
| 技术栈 | Python | TypeScript | React 类型安全 |

## 🎯 使用指南

### 1. Chat 工作台

1. 选择 Agent 类型（推荐 Hybrid Agent）
2. 输入问题，点击"发送"
3. 查看流式响应和知识图谱
4. 在调试面板查看执行日志、推理过程
5. 点击源文档引用查看原始内容
6. 提交反馈（👍/👎）

### 2. 深度研究 Agent 特殊配置

- **使用增强版研究工具**: 启用更强大的多轮推理
- **显示推理过程**: 实时展示推理步骤

### 3. Debug 模式

启用后会自动：
- 禁用流式输出
- 显示执行日志
- 展示迭代信息
- 提取知识图谱

## 🐛 故障排查

### 后端连接失败

1. 确认后端服务已启动（`python server/main.py`）
2. 检查 `.env` 中的 `VITE_BACKEND_ORIGIN` 配置
3. 查看浏览器控制台网络请求

### SSE 流式输出中断

1. 检查后端是否超时（深度研究 Agent 可能需要更长时间）
2. 查看浏览器控制台是否有错误
3. 尝试禁用调试模式后重试

### 知识图谱不展示

1. 确保返回的 `kg_data` 包含 `nodes` 和 `links`
2. 检查调试面板的"知识图谱"标签页
3. 尝试点击"从回答提取图谱"按钮

## 📝 开发建议

### 添加新 Agent

1. 在 `ChatPage.tsx` 的 `agentOptions` 中添加配置
2. 如需特殊参数，参考 `deep_research_agent` 的实现

### 扩展 API

1. 在 `src/types/` 中定义 TypeScript 类型
2. 在 `src/services/` 中实现 API 调用
3. 在页面组件中使用

## 📚 相关文档

- [整体架构文档](../docs/Chat工作台完整调用流程.md)
- [后端 API 文档](../server/README.md)
- [知识图谱构建](../CLAUDE.md)

## 🔗 技术栈

- **框架**: React 18
- **构建工具**: Vite 6
- **语言**: TypeScript 5
- **UI 库**: Ant Design 5
- **图谱可视化**: @antv/g6
- **Markdown 渲染**: react-markdown
- **HTTP 客户端**: axios
- **路由**: react-router-dom

---

**版本**: v1.0
**最后更新**: 2025-12-29
**维护者**: GraphRAG Team

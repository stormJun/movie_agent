# mem0 记忆管理界面设计文档（React 版本）

> **文档版本**: v2.0
> **创建日期**: 2025-01-21
> **最后更新**: 2025-01-21
> **作者**: GraphRAG Team
> **状态**: 设计阶段
> **技术栈**: React 18 + TypeScript + Ant Design 5 + React Router 6 + Axios

---

## 目录

- [1. 概述](#1-概述)
- [2. 技术栈与架构](#2-技术栈与架构)
- [3. 功能需求](#3-功能需求)
- [4. 界面设计](#4-界面设计)
  - [4.1 导航结构](#41-导航结构)
  - [4.2 记忆列表页面](#42-记忆列表页面)
  - [4.3 记忆详情页面](#43-记忆详情页面)
  - [4.4 记忆搜索页面](#44-记忆搜索页面)
  - [4.5 统计面板页面](#45-统计面板页面)
- [5. 组件设计](#5-组件设计)
- [6. API 接口设计](#6-api-接口设计)
- [7. 类型定义](#7-类型定义)
- [8. 实施计划](#8-实施计划)

---

## 1. 概述

### 1.1 背景

GraphRAG Agent 已集成 mem0 自托管服务实现长期记忆功能，但目前缺乏可视化的记忆管理界面。基于现有的 **React + Ant Design** 前端架构，新增"记忆管理"模块，提供友好的 Web UI 界面。

### 1.2 设计目标

在现有 React 前端中新增"记忆管理"模块，提供：
- 📋 列表管理：查看、分页、过滤、排序记忆
- 🔍 智能搜索：语义搜索 + 关键词过滤
- ✏️ 编辑功能：修改记忆内容、标签、元数据
- 🗑️ 删除管理：单条删除 + 批量删除 + 回收站
- 📊 数据统计：可视化图表展示记忆分布
- 🎨 **用户体验**：符合 Ant Design 设计规范，与现有界面风格统一

### 1.3 技术亮点

- ✅ **TypeScript 强类型**：完整的类型定义，减少运行时错误
- ✅ **Ant Design 组件**：复用企业级 UI 组件库，开发效率高
- ✅ **React Hooks**：现代化的状态管理，代码简洁
- ✅ **响应式布局**：支持不同屏幕尺寸
- ✅ **性能优化**：虚拟滚动、懒加载、缓存策略

---

## 2. 技术栈与架构

### 2.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| **React** | 18.3.1 | UI 框架 |
| **TypeScript** | 5.7.2 | 类型安全 |
| **Ant Design** | 5.23.3 | UI 组件库 |
| **React Router** | 6.28.2 | 路由管理 |
| **Axios** | 1.7.9 | HTTP 客户端 |
| **Vite** | 6.0.7 | 构建工具 |

### 2.2 目录结构

```
frontend-react/src/
├── pages/
│   ├── MemoriesPage.tsx          # 记忆列表页（主入口）
│   ├── MemoryDetailPage.tsx      # 记忆详情页
│   ├── MemorySearchPage.tsx       # 记忆搜索页
│   └── MemoryStatisticsPage.tsx   # 统计面板页
├── components/
│   └── memory/
│       ├── MemoryList.tsx         # 记忆列表组件
│       ├── MemoryCard.tsx         # 记忆卡片组件
│       ├── MemorySearchBar.tsx    # 搜索栏组件
│       ├── MemoryFilterPanel.tsx  # 过滤面板组件
│       ├── MemoryEditor.tsx       # 记忆编辑器组件
│       ├── MemoryStatistics.tsx   # 统计图表组件
│       └── MemoryTagManager.tsx   # 标签管理组件
├── services/
│   └── memory.ts                  # mem0 API 调用
├── types/
│   └── memory.ts                  # 记忆相关类型定义
├── App.tsx                        # 路由配置（需更新）
└── app/layout/AdminLayout.tsx     # 主布局（需更新菜单）
```

### 2.3 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (React)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    Components                         │  │
│  │  ┌─────────────┬─────────────┬─────────────────────┐ │  │
│  │  │ MemoryList  │ MemorySearch│ MemoryStatistics    │ │  │
│  │  └─────────────┴─────────────┴─────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   Services Layer                      │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │  memory.ts (Axios HTTP Client)               │   │  │
│  │  │  - getMemories()                              │   │  │
│  │  │  - searchMemories()                           │   │  │
│  │  │  - updateMemory()                             │   │  │
│  │  │  - deleteMemory()                             │   │  │
│  │  └──────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   REST API                            │  │
│  │  GET  /api/v1/memories                               │  │
│  │  POST /api/v1/memories/search                         │  │
│  │  PUT  /api/v1/memories/:id                            │  │
│  │  DELETE /api/v1/memories/:id                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              mem0 Self-Hosted Service                 │  │
│  │  (FastAPI + PostgreSQL + Milvus)                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 功能需求

### 3.1 核心功能（MVP）

#### 3.1.1 记忆列表

**功能描述**：以表格形式展示当前用户的所有记忆记录。

**详细需求**：
- 📋 表格列：ID、内容、标签、创建时间、置信度、操作
- 🔢 分页显示：每页 10/20/50/100 条，支持跳页
- 🔍 实时搜索：根据关键词过滤列表
- 🏷️ 标签筛选：下拉选择标签过滤
- 📅 排序功能：按创建时间、置信度排序
- 🗑️ 快速删除：操作列提供删除按钮
- ✏️ 快速编辑：点击编辑按钮跳转详情页

**用户场景**：
```
用户 A 想查看系统记住了自己的哪些偏好，
打开记忆列表，看到 50 条记忆，按时间倒序排列，
发现其中有 3 条关于"喜欢科幻电影"的重复记录，
于是删除了 2 条旧的，保留了最新的。
```

#### 3.1.2 记忆搜索

**功能描述**：基于语义相似度的智能搜索。

**详细需求**：
- 🔍 **语义搜索框**：输入自然语言查询
- 📊 **结果排序**：按相似度分数排序
- 🎯 **高亮匹配**：在结果中高亮显示相关片段
- 📄 **结果数量**：返回 Top-K 结果（默认 5 条）
- 💾 **搜索历史**：记录最近 10 次搜索

**用户场景**：
```
用户 B 想知道系统是否记住了自己的饮食偏好，
在搜索框输入"我不吃什么食物？"，
系统返回 3 条高相关记忆：
1. "用户对花生过敏"（相似度 0.95）
2. "用户偏好素食"（相似度 0.87）
3. "用户喜欢吃辣"（相似度 0.72）
```

#### 3.1.3 记忆编辑

**功能描述**：编辑记忆的内容、标签、元数据。

**详细需求**：
- ✏️ **编辑内容**：修改记忆文本
- 🏷️ **管理标签**：添加/删除标签
- 📝 **编辑元数据**：修改来源、置信度等
- 💾 **保存版本**：保留编辑历史（P2）

#### 3.1.4 记忆删除

**功能描述**：删除单条或批量删除记忆。

**详细需求**：
- 🗑️ **单条删除**：删除按钮 + 确认弹窗
- 📦 **批量删除**：勾选多条记忆，批量删除
- ♻️ **软删除**：删除后 30 天内可恢复（P2）
- ⚠️ **删除提示**：提示删除后无法恢复（或可恢复时间）

#### 3.1.5 记忆统计

**功能描述**：可视化展示记忆数据的统计信息。

**详细需求**：
- 📊 **数量统计**：总记忆数、今日新增、本周新增
- 🏷️ **标签分布**：饼图展示各标签占比
- 📅 **时间趋势**：折线图展示记忆增长趋势
- 🎯 **质量分析**：平均置信度分数、低质量记忆占比

---

## 4. 界面设计

### 4.1 导航结构

#### 4.1.1 更新 AdminLayout 菜单

在 `AdminLayout.tsx` 中添加"记忆管理"菜单项：

```typescript
const menuItems = [
  { key: "/chat", icon: <CommentOutlined />, label: "Chat 工作台" },
  {
    key: "/graph",
    icon: <ApartmentOutlined />,
    label: "知识图谱",
    children: [
      { key: "/graph/explore", icon: <DeploymentUnitOutlined />, label: "探索" },
      { key: "/graph/reasoning", icon: <ClusterOutlined />, label: "推理" },
      { key: "/graph/manage/entities", icon: <ClusterOutlined />, label: "实体管理" },
      { key: "/graph/manage/relations", icon: <LinkOutlined />, label: "关系管理" },
    ],
  },
  // 新增：记忆管理菜单组
  {
    key: "/memory",
    icon: <DatabaseOutlined />, // 需要导入
    label: "记忆管理",
    children: [
      { key: "/memory/list", icon: <UnorderedListOutlined />, label: "记忆列表" },
      { key: "/memory/search", icon: <SearchOutlined />, label: "记忆搜索" },
      { key: "/memory/statistics", icon: <BarChartOutlined />, label: "统计面板" },
    ],
  },
  { key: "/sources", icon: <FileSearchOutlined />, label: "源内容" },
  { key: "/settings", icon: <SettingOutlined />, label: "设置" },
];
```

#### 4.1.2 更新路由配置

在 `App.tsx` 中添加记忆管理路由：

```typescript
import { MemoriesPage } from "./pages/MemoriesPage";
import { MemorySearchPage } from "./pages/MemorySearchPage";
import { MemoryStatisticsPage } from "./pages/MemoryStatisticsPage";

export function App() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/graph/explore" element={<GraphExplorePage />} />
        <Route path="/graph/reasoning" element={<GraphReasoningPage />} />
        <Route path="/graph/manage/entities" element={<EntitiesPage />} />
        <Route path="/graph/manage/relations" element={<RelationsPage />} />
        <Route path="/sources" element={<SourcesPage />} />

        {/* 新增：记忆管理路由 */}
        <Route path="/memory" element={<Navigate to="/memory/list" replace />} />
        <Route path="/memory/list" element={<MemoriesPage />} />
        <Route path="/memory/search" element={<MemorySearchPage />} />
        <Route path="/memory/statistics" element={<MemoryStatisticsPage />} />

        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
```

---

### 4.2 记忆列表页面

#### 4.2.1 页面布局

```tsx
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Tooltip,
  Input,
  Select,
  message,
  Modal,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  SearchOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import type { MemoryData, MemoryListFilter } from "../types/memory";
import { getMemories, deleteMemory } from "../services/memory";

export function MemoriesPage() {
  const navigate = useNavigate();
  const [memories, setMemories] = useState<MemoryData[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const [filters, setFilters] = useState<MemoryListFilter>({});
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  // 加载数据
  useEffect(() => {
    fetchMemories();
  }, [pagination.current, pagination.pageSize, filters]);

  async function fetchMemories() {
    setLoading(true);
    try {
      const resp = await getMemories({
        offset: (pagination.current - 1) * pagination.pageSize,
        limit: pagination.pageSize,
        ...filters,
      });
      setMemories(resp.memories);
      setPagination({ ...pagination, total: resp.total });
    } catch (e) {
      message.error(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  // 删除记忆
  async function handleDelete(id: string) {
    Modal.confirm({
      title: "确认删除",
      content: "删除后 30 天内可恢复，确定要删除这条记忆吗？",
      onOk: async () => {
        try {
          await deleteMemory(id);
          message.success("删除成功");
          fetchMemories();
        } catch (e) {
          message.error(e instanceof Error ? e.message : "删除失败");
        }
      },
    });
  }

  // 批量删除
  async function handleBatchDelete() {
    if (selectedRowKeys.length === 0) {
      message.warning("请先选择要删除的记忆");
      return;
    }
    Modal.confirm({
      title: "批量删除",
      content: `确定要删除选中的 ${selectedRowKeys.length} 条记忆吗？`,
      onOk: async () => {
        try {
          await Promise.all(selectedRowKeys.map((id) => deleteMemory(id as string)));
          message.success("批量删除成功");
          setSelectedRowKeys([]);
          fetchMemories();
        } catch (e) {
          message.error(e instanceof Error ? e.message : "批量删除失败");
        }
      },
    });
  }

  // 表格列定义
  const columns: ColumnsType<MemoryData> = useMemo(
    () => [
      {
        title: "ID",
        dataIndex: "id",
        key: "id",
        width: 200,
        ellipsis: true,
        render: (id) => (
          <Tooltip title={id}>
            <span>{id.substring(0, 16)}...</span>
          </Tooltip>
        ),
      },
      {
        title: "内容",
        dataIndex: "text",
        key: "text",
        ellipsis: true,
        render: (text) => (
          <Tooltip title={text}>
            <span>{text}</span>
          </Tooltip>
        ),
      },
      {
        title: "标签",
        dataIndex: "tags",
        key: "tags",
        width: 200,
        render: (tags: string[]) => (
          <>
            {tags?.map((tag) => (
              <Tag key={tag} color="blue">
                {tag}
              </Tag>
            ))}
          </>
        ),
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        width: 180,
        sorter: true,
        render: (date) => new Date(date).toLocaleString("zh-CN"),
      },
      {
        title: "置信度",
        dataIndex: "score",
        key: "score",
        width: 120,
        sorter: true,
        render: (score: number) => (
          <div>
            <span>{(score * 100).toFixed(1)}%</span>
            <progress
              value={score * 100}
              max={100}
              style={{ width: 60, marginLeft: 8 }}
            />
          </div>
        ),
      },
      {
        title: "操作",
        key: "actions",
        width: 150,
        fixed: "right",
        render: (_, record) => (
          <Space>
            <Tooltip title="查看详情">
              <Button
                type="text"
                icon={<EyeOutlined />}
                onClick={() => navigate(`/memory/detail/${record.id}`)}
              />
            </Tooltip>
            <Tooltip title="编辑">
              <Button
                type="text"
                icon={<EditOutlined />}
                onClick={() => navigate(`/memory/edit/${record.id}`)}
              />
            </Tooltip>
            <Tooltip title="删除">
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(record.id)}
              />
            </Tooltip>
          </Space>
        ),
      },
    ],
    [navigate],
  );

  return (
    <div style={{ padding: 24 }}>
      {/* 页面标题 + 操作栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Space size="middle" style={{ width: "100%", justifyContent: "space-between" }}>
          <Space>
            <h2 style={{ margin: 0 }}>💾 记忆列表</h2>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchMemories}
            >
              刷新
            </Button>
          </Space>
          <Space>
            <Button
              type="primary"
              danger
              icon={<DeleteOutlined />}
              disabled={selectedRowKeys.length === 0}
              onClick={handleBatchDelete}
            >
              批量删除 ({selectedRowKeys.length})
            </Button>
          </Space>
        </Space>
      </Card>

      {/* 搜索和过滤栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Space size="middle" wrap>
          <Input
            placeholder="🔍 搜索记忆内容..."
            allowClear
            style={{ width: 300 }}
            onPressEnter={(e) => setFilters({ ...filters, query: e.currentTarget.value })}
            suffix={<SearchOutlined />}
          />
          <Select
            placeholder="🏷️ 标签过滤"
            allowClear
            style={{ width: 150 }}
            onChange={(value) => setFilters({ ...filters, tag: value })}
            options={[
              { value: "偏好", label: "偏好" },
              { value: "事实", label: "事实" },
              { value: "事件", label: "事件" },
              { value: "指令", label: "指令" },
            ]}
          />
          <Select
            placeholder="📅 排序方式"
            defaultValue="created_at"
            style={{ width: 150 }}
            onChange={(value) => setFilters({ ...filters, sort: value })}
            options={[
              { value: "created_at", label: "创建时间" },
              { value: "-created_at", label: "创建时间（倒序）" },
              { value: "score", label: "置信度" },
              { value: "-score", label: "置信度（倒序）" },
            ]}
          />
        </Space>
      </Card>

      {/* 记忆列表表格 */}
      <Card>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={memories}
          loading={loading}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
            pageSizeOptions: [10, 20, 50, 100],
          }}
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys),
          }}
          scroll={{ x: 1200 }}
          onChange={(pagination) => {
            setPagination({
              ...pagination,
              current: pagination.current || 1,
              pageSize: pagination.pageSize || 20,
            });
          }}
        />
      </Card>
    </div>
  );
}
```

---

### 4.3 记忆详情页面

#### 4.3.1 页面布局

```tsx
import {
  Card,
  Descriptions,
  Tag,
  Button,
  Space,
  Modal,
  Form,
  Input,
  message,
  Tabs,
} from "antd";
import {
  EditOutlined,
  DeleteOutlined,
  ArrowLeftOutlined,
} from "@ant-design/icons";
import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getMemoryDetail, updateMemory, deleteMemory } from "../services/memory";
import type { MemoryData, MemoryUpdateData } from "../types/memory";

export function MemoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [memory, setMemory] = useState<MemoryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    if (id) {
      fetchMemoryDetail();
    }
  }, [id]);

  async function fetchMemoryDetail() {
    if (!id) return;
    setLoading(true);
    try {
      const data = await getMemoryDetail(id);
      setMemory(data);
      form.setFieldsValue(data);
    } catch (e) {
      message.error(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    try {
      const values = await form.validateFields();
      const updateData: MemoryUpdateData = {
        id: id!,
        ...values,
      };
      await updateMemory(updateData);
      message.success("保存成功");
      setEditMode(false);
      fetchMemoryDetail();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "保存失败");
    }
  }

  async function handleDelete() {
    Modal.confirm({
      title: "确认删除",
      content: "删除后 30 天内可恢复，确定要删除这条记忆吗？",
      onOk: async () => {
        if (!id) return;
        try {
          await deleteMemory(id);
          message.success("删除成功");
          navigate("/memory/list");
        } catch (e) {
          message.error(e instanceof Error ? e.message : "删除失败");
        }
      },
    });
  }

  if (loading || !memory) {
    return <div>加载中...</div>;
  }

  return (
    <div style={{ padding: 24 }}>
      {/* 页面标题栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate("/memory/list")}
          >
            返回列表
          </Button>
          <h2 style={{ margin: 0 }}>📄 记忆详情</h2>
        </Space>
      </Card>

      {/* 记忆详情卡片 */}
      <Card>
        {!editMode ? (
          <>
            {/* 查看模式 */}
            <Descriptions title="基本信息" bordered column={2}>
              <Descriptions.Item label="记忆 ID">{memory.id}</Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(memory.created_at).toLocaleString("zh-CN")}
              </Descriptions.Item>
              <Descriptions.Item label="置信度">
                {(memory.score * 100).toFixed(1)}%
              </Descriptions.Item>
              <Descriptions.Item label="来源">
                {memory.metadata?.source || "未知"}
              </Descriptions.Item>
              <Descriptions.Item label="标签" span={2}>
                <Space>
                  {memory.tags?.map((tag) => (
                    <Tag key={tag} color="blue">
                      {tag}
                    </Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="记忆内容" span={2}>
                <div style={{ whiteSpace: "pre-wrap" }}>
                  {memory.text}
                </div>
              </Descriptions.Item>
            </Descriptions>

            {/* 操作按钮 */}
            <Space style={{ marginTop: 16 }}>
              <Button
                type="primary"
                icon={<EditOutlined />}
                onClick={() => setEditMode(true)}
              >
                编辑
              </Button>
              <Button
                danger
                icon={<DeleteOutlined />}
                onClick={handleDelete}
              >
                删除
              </Button>
            </Space>
          </>
        ) : (
          <>
            {/* 编辑模式 */}
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSave}
            >
              <Form.Item
                label="记忆内容"
                name="text"
                rules={[{ required: true, message: "请输入记忆内容" }]}
              >
                <Input.TextArea
                  rows={6}
                  placeholder="请输入记忆内容"
                />
              </Form.Item>

              <Form.Item
                label="标签"
                name="tags"
              >
                <Select
                  mode="tags"
                  placeholder="输入标签，按回车添加"
                  options={[
                    { value: "偏好", label: "偏好" },
                    { value: "事实", label: "事实" },
                    { value: "事件", label: "事件" },
                    { value: "指令", label: "指令" },
                  ]}
                />
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit">
                    保存
                  </Button>
                  <Button onClick={() => setEditMode(false)}>
                    取消
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          )}
        </Card>
      </Card>
    </div>
  );
}
```

---

### 4.4 记忆搜索页面

#### 4.4.1 页面布局

```tsx
import {
  Card,
  Input,
  Button,
  Slider,
  Space,
  List,
  Tag,
  message,
  Divider,
} from "antd";
import {
  SearchOutlined,
  EyeOutlined,
  EditOutlined,
} from "@ant-design/icons";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { searchMemories } from "../services/memory";
import type { MemoryData } from "../types/memory";

const { TextArea } = Input;

export function MemorySearchPage() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [results, setResults] = useState<MemoryData[]>([]);
  const [loading, setLoading] = useState(false);
  const [topK, setTopK] = useState(5);
  const [minScore, setMinScore] = useState(0.6);

  async function handleSearch() {
    if (!searchQuery.trim()) {
      message.warning("请输入搜索查询");
      return;
    }

    setLoading(true);
    try {
      const data = await searchMemories({
        query: searchQuery,
        top_k: topK,
        min_score: minScore,
      });
      setResults(data);
    } catch (e) {
      message.error(e instanceof Error ? e.message : "搜索失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 24 }}>
      {/* 页面标题 */}
      <Card style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>🔍 记忆搜索</h2>
      </Card>

      {/* 搜索框 */}
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <TextArea
            rows={3}
            placeholder="输入自然语言查询，例如：我喜欢的电影类型"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onPressEnter={handleSearch}
          />

          {/* 高级选项 */}
          <Card size="small" title="🔧 高级选项">
            <Space direction="vertical" style={{ width: "100%" }}>
              <div>
                <span>📊 返回结果数: {topK}</span>
                <Slider
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(value) => setTopK(value)}
                  marks={{ 1: "1", 5: "5", 10: "10", 20: "20" }}
                />
              </div>
              <div>
                <span>🎯 最低相似度: {minScore.toFixed(2)}</span>
                <Slider
                  min={0}
                  max={1}
                  step={0.05}
                  value={minScore}
                  onChange={(value) => setMinScore(value)}
                  marks={{ 0: "0", 0.5: "0.5", 0.8: "0.8", 1: "1" }}
                />
              </div>
            </Space>
          </Card>

          <Button
            type="primary"
            icon={<SearchOutlined />}
            size="large"
            loading={loading}
            onClick={handleSearch}
            block
          >
            搜索
          </Button>
        </Space>
      </Card>

      {/* 搜索结果 */}
      {results.length > 0 && (
        <Card>
          <Divider>搜索结果（共找到 {results.length} 条相关记忆）</Divider>
          <List
            itemLayout="vertical"
            dataSource={results}
            renderItem={(item, index) => (
              <List.Item
                key={item.id}
                actions={[
                  <Button
                    type="link"
                    icon={<EyeOutlined />}
                    onClick={() => navigate(`/memory/detail/${item.id}`)}
                  >
                    详情
                  </Button>,
                  <Button
                    type="link"
                    icon={<EditOutlined />}
                    onClick={() => navigate(`/memory/edit/${item.id}`)}
                  >
                    编辑
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <span>{index + 1}. 🔍 相似度: {(item.score * 100).toFixed(1)}%</span>
                      <progress value={item.score * 100} max={100} style={{ width: 100 }} />
                    </Space>
                  }
                  description={
                    <div>
                      <p>{item.text}</p>
                      <Space>
                        {item.tags?.map((tag) => (
                          <Tag key={tag} color="blue">
                            {tag}
                          </Tag>
                        ))}
                      </Space>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  );
}
```

---

### 4.5 统计面板页面

#### 4.5.1 页面布局

```tsx
import {
  Card,
  Statistic,
  Row,
  Col,
  Progress,
  Alert,
} from "antd";
import {
  FileTextOutlined,
  PlusOutlined,
  TrophyOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { useEffect, useState } from "react";
import { getMemoryStatistics } from "../services/memory";
import type { MemoryStatistics } from "../types/memory";

export function MemoryStatisticsPage() {
  const [stats, setStats] = useState<MemoryStatistics | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStatistics();
  }, []);

  async function fetchStatistics() {
    setLoading(true);
    try {
      const data = await getMemoryStatistics();
      setStats(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  if (loading || !stats) {
    return <div>加载中...</div>;
  }

  return (
    <div style={{ padding: 24 }}>
      {/* 页面标题 */}
      <Card style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>📊 记忆统计</h2>
      </Card>

      {/* 总览统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="📝 总记忆数"
              value={stats.total_count}
              prefix={<FileTextOutlined />}
              suffix="条"
            />
            <div style={{ marginTop: 16 }}>
              今日新增: <span style={{ color: "#3f8600" }}>+{stats.today_count}</span>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="📅 今日新增"
              value={stats.today_count}
              prefix={<PlusOutlined />}
              suffix="条"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="📆 本周新增"
              value={stats.week_count}
              prefix={<PlusOutlined />}
              suffix="条"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="📊 平均质量"
              value={stats.avg_score}
              precision={2}
              prefix={<TrophyOutlined />}
              suffix="%"
            />
            <Progress
              percent={stats.avg_score * 100}
              showInfo={false}
              style={{ marginTop: 8 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 质量建议 */}
      <Card title="⚠️ 质量建议" style={{ marginBottom: 16 }}>
        {stats.suggestions.map((suggestion, index) => (
          <Alert
            key={index}
            message={suggestion.message}
            description={suggestion.description}
            type={suggestion.type === "low_quality" ? "warning" : "info"}
            showIcon
            style={{ marginBottom: 8 }}
          />
        ))}
      </Card>

      {/* 更多图表（需使用 ECharts 或 Recharts） */}
      <Row gutter={16}>
        <Col span={12}>
          <Card title="🏷️ 标签分布">
            {/* TODO: 使用饼图展示标签分布 */}
            <div style={{ textAlign: "center", padding: 40 }}>
              标签分布图表（待实现）
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="📅 时间趋势">
            {/* TODO: 使用折线图展示时间趋势 */}
            <div style={{ textAlign: "center", padding: 40 }}>
              时间趋势图表（待实现）
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
```

---

## 5. 组件设计

### 5.1 核心 React 组件

| 组件 | 文件路径 | 功能说明 |
|------|---------|---------|
| `MemoriesPage` | `pages/MemoriesPage.tsx` | 记忆列表页（主入口） |
| `MemoryDetailPage` | `pages/MemoryDetailPage.tsx` | 记忆详情页 |
| `MemorySearchPage` | `pages/MemorySearchPage.tsx` | 记忆搜索页 |
| `MemoryStatisticsPage` | `pages/MemoryStatisticsPage.tsx` | 统计面板页 |

### 5.2 可复用子组件

| 组件 | 文件路径 | 功能说明 |
|------|---------|---------|
| `MemoryCard` | `components/memory/MemoryCard.tsx` | 记忆卡片组件 |
| `MemorySearchBar` | `components/memory/MemorySearchBar.tsx` | 搜索栏组件 |
| `MemoryFilterPanel` | `components/memory/MemoryFilterPanel.tsx` | 过滤面板组件 |
| `MemoryEditor` | `components/memory/MemoryEditor.tsx` | 记忆编辑器组件 |
| `MemoryTagManager` | `components/memory/MemoryTagManager.tsx` | 标签管理组件 |

---

## 6. API 接口设计

### 6.1 mem0 服务 API（需后端实现）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/memories` | 获取记忆列表（分页） |
| GET | `/api/v1/memories/:id` | 获取单条记忆详情 |
| POST | `/api/v1/memories/search` | 语义搜索记忆 |
| PUT | `/api/v1/memories/:id` | 更新记忆 |
| DELETE | `/api/v1/memories/:id` | 删除记忆 |
| GET | `/api/v1/memories/stats` | 获取统计数据 |

### 6.2 前端 API 调用封装

在 `services/memory.ts` 中封装 mem0 API 调用：

```typescript
import { http } from "./http";
import type {
  MemoryData,
  MemoryListFilter,
  MemorySearchQuery,
  MemoryUpdateData,
  MemoryStatistics,
} from "../types/memory";

export async function getMemories(
  filter: MemoryListFilter,
): Promise<{ memories: MemoryData[]; total: number }> {
  const resp = await http.get<{ memories: MemoryData[]; total: number }>(
    "/api/v1/memories",
    { params: filter },
  );
  return resp.data;
}

export async function getMemoryDetail(id: string): Promise<MemoryData> {
  const resp = await http.get<MemoryData>(`/api/v1/memories/${id}`);
  return resp.data;
}

export async function searchMemories(
  query: MemorySearchQuery,
): Promise<MemoryData[]> {
  const resp = await http.post<{ memories: MemoryData[] }>(
    "/api/v1/memories/search",
    query,
  );
  return resp.data.memories || [];
}

export async function updateMemory(
  data: MemoryUpdateData,
): Promise<{ success: boolean; message?: string }> {
  const resp = await http.put<{ success: boolean; message?: string }>(
    `/api/v1/memories/${data.id}`,
    data,
  );
  return resp.data;
}

export async function deleteMemory(
  id: string,
): Promise<{ success: boolean; message?: string }> {
  const resp = await http.delete<{ success: boolean; message?: string }>(
    `/api/v1/memories/${id}`,
  );
  return resp.data;
}

export async function getMemoryStatistics(): Promise<MemoryStatistics> {
  const resp = await http.get<MemoryStatistics>("/api/v1/memories/stats");
  return resp.data;
}
```

---

## 7. 类型定义

在 `types/memory.ts` 中定义 TypeScript 类型：

```typescript
export interface MemoryData {
  id: string;
  text: string;
  tags: string[];
  created_at: string;
  updated_at?: string;
  score: number;
  metadata?: {
    source?: string;
    session_id?: string;
    [key: string]: any;
  };
}

export interface MemoryListFilter {
  query?: string;
  tag?: string;
  sort?: string;
  offset?: number;
  limit?: number;
}

export interface MemorySearchQuery {
  query: string;
  top_k?: number;
  min_score?: number;
}

export interface MemoryUpdateData {
  id: string;
  text?: string;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface MemoryStatistics {
  total_count: number;
  today_count: number;
  week_count: number;
  avg_score: number;
  tag_distribution: Record<string, number>;
  timeline: {
    dates: string[];
    counts: number[];
  };
  suggestions: Array<{
    type: "low_quality" | "duplicate" | "expired";
    message: string;
    description: string;
  }>;
}
```

---

## 8. 实施计划

### 8.1 阶段划分

#### 第一阶段：MVP（2-3 周）

- ✅ **Week 1**: 基础架构 + 记忆列表页
  - 创建类型定义 `types/memory.ts`
  - 创建 API 服务 `services/memory.ts`
  - 实现记忆列表页面 `pages/MemoriesPage.tsx`
  - 更新路由和导航菜单

- ✅ **Week 2**: 记忆详情 + 编辑 + 删除
  - 实现记忆详情页 `pages/MemoryDetailPage.tsx`
  - 实现记忆编辑功能
  - 实现记忆删除功能（带确认）
  - 批量删除功能

- ✅ **Week 3**: 记忆搜索 + 测试
  - 实现记忆搜索页 `pages/MemorySearchPage.tsx`
  - 优化搜索结果展示
  - 集成测试和 bug 修复

#### 第二阶段：增强功能（1-2 周）

- ✅ 统计面板 `pages/MemoryStatisticsPage.tsx`
- ✅ 可复用组件拆分
- ✅ 图表集成（使用 @ant-design/charts）

### 8.2 验收标准

- ✅ 用户可以在 3 步内查看所有记忆
- ✅ 用户可以编辑记忆内容并保存成功
- ✅ 用户可以删除记忆并看到确认提示
- ✅ 语义搜索返回相关结果（相似度 > 0.6）
- ✅ 列表加载时间 < 1s（100 条记忆内）
- ✅ 搜索响应时间 < 2s
- ✅ 所有组件通过 TypeScript 类型检查
- ✅ 无 ESLint 警告

---

## 附录

### A. 参考资源

**React 生态**：
- [React 官方文档](https://react.dev/)
- [Ant Design 组件库](https://ant.design/)
- [React Router 文档](https://reactrouter.com/)
- [TypeScript 手册](https://www.typescriptlang.org/docs/)

**现有代码参考**：
- `frontend-react/src/pages/EntitiesPage.tsx` - 实体管理页（类似结构）
- `frontend-react/src/services/management.ts` - API 调用模式
- `frontend-react/src/app/layout/AdminLayout.tsx` - 布局组件

### B. 术语表

| 术语 | 定义 |
|------|------|
| **记忆（Memory）** | 存储在 mem0 中的结构化信息 |
| **语义搜索** | 基于向量相似度的智能搜索 |
| **置信度分数** | 记忆的质量评分，范围 [0, 1] |
| **TTL** | Time To Live，记忆的有效期 |
| **用户隔离** | 确保不同用户的记忆数据完全隔离 |

---

**文档结束**

如有疑问或建议，请联系 GraphRAG Team。

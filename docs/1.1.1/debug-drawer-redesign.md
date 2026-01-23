# 调试信息抽屉重设计

## 背景

当前调试信息抽屉存在以下问题：
1. **信息架构混乱**：5个平级Tab（执行轨迹、route_decision、rag_runs、progress、errors），用户不知道先看哪个
2. **重复冗余**：
   - errors单独一个Tab，但其实应该整合进时间线
   - progress_events主要用于流式过程中的进度条，事后调试价值不高
3. **关键信息埋没**：
   - 用户最关心的"走了哪个agent、检索命中多少、是否报错"需要在多个Tab间跳转
   - rag_runs的检索详情埋在JSON里，不直观
   - 时间线（execution_log）只显示input/output的JSON，缺少关键指标的摘要

## 目标

设计一个清晰、易用的调试信息架构：
- **1个入口**：调试信息按钮（已实现）
- **4个主视图**：概览（Overview）、时间线（Timeline）、检索（Retrieval）、原始（Raw）
- **降低冗余**：合并/降级重复项

## 设计方案

### 1. 概览（Overview）- 默认Tab

**目标**：回答用户最常问的5个问题

#### 1.1 核心指标卡片
```
┌─────────────────────────────────────┐
│ 路由决策                             │
│ - Agent: hybrid_agent               │
│ - Reasoning: [展开查看]             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 检索概览                             │
│ - 检索路径: 3路（local_search、     │
│   global_search、vector）           │
│ - 总命中数: 47条                     │
│ - 错误/超时: 0                       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 性能指标                             │
│ - 总耗时: 3.2s                       │
│ - 检索: 1.8s                         │
│ - 生成: 1.4s                         │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Top Sources                         │
│ 1. [ID: abc123] "Inception情节分析" │
│ 2. [ID: def456] "诺兰导演作品"       │
│ 3. [ID: ghi789] "科幻电影推荐"       │
└─────────────────────────────────────┘
```

#### 1.2 数据来源
- **route_decision**: 做成摘要 + 可展开详情
  - 摘要：显示选择的agent和简短理由
  - 详情：完整的decision对象（折叠显示）
  
- **rag_runs**: 做成统计摘要
  - 显示：几路检索、每路命中数、是否有error
  - 示例：`3路检索 | local: 12条, global: 8条, vector: 27条 | 无错误`

- **execution_log**: 提取性能指标
  - 总耗时：最后一个node的timestamp - 第一个node的timestamp
  - 各阶段耗时：根据node类型聚合

- **Top Sources**: 从rag_runs的top_sources字段提取

#### 1.3 实现要点
- 使用Ant Design的`Statistic`组件展示指标
- 使用`Card`组件分块
- 使用`Collapse`组件可展开route_decision详情

### 2. 时间线（Timeline）

**目标**：完整的执行追踪，每个node一条卡片

#### 2.1 卡片设计
```
┌─────────────────────────────────────┐
│ ① route_decision                    │
│ ✓ 成功 | 12:34:56.123 | 耗时: 0.05s│
├─────────────────────────────────────┤
│ 摘要:                                │
│ - 选择: hybrid_agent                │
│ - 理由: 需要多维度检索              │
├─────────────────────────────────────┤
│ [展开] 输入/输出 JSON               │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ ② rag_retrieval_local_search        │
│ ✓ 成功 | 12:34:56.234 | 耗时: 0.8s │
├─────────────────────────────────────┤
│ 摘要:                                │
│ - 检索数: 12条                       │
│ - 粒度: entities                    │
│ - Top Sources: [abc123, def456]     │
│ - Sample Evidence: "Inception是..."│
├─────────────────────────────────────┤
│ [展开] 输入/输出 JSON               │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ ③ llm_generation                    │
│ ✗ 超时 | 12:34:57.456 | 耗时: 10s  │
├─────────────────────────────────────┤
│ 错误: TimeoutError                  │
│ 消息: LLM请求超时                   │
└─────────────────────────────────────┘
```

#### 2.2 状态标识
- ✓ 成功：绿色
- ✗ 错误：红色
- ⏱ 超时：橙色
- ⚠ 警告：黄色（例如检索数为0但不算错误）

#### 2.3 摘要字段映射

根据node类型，提取关键字段：

**检索类node** (rag_retrieval_*):
- `retrieval_count`: 检索数
- `granularity`: 粒度
- `top_sources`: Top源ID（可点击跳转）
- `sample_evidence`: 样例证据（截取100字）

**生成类node** (llm_generation):
- `model`: 模型名称
- `tokens`: 生成token数
- `finish_reason`: 结束原因

**路由类node** (route_decision):
- `selected_agent`: 选择的agent
- `reasoning`: 选择理由（截取）

#### 2.4 实现要点
- 使用Ant Design的`Timeline`组件
- 每个Timeline.Item包含一个`Card`
- 状态用dot属性的color表示
- 使用`Descriptions`组件展示摘要字段
- 使用`Collapse`折叠input/output JSON

### 3. 检索（Retrieval）

**目标**：可视化"到底找到了什么"

#### 3.1 检索路径表格
```
Agent Type       | 检索数 | 上下文长度 | 耗时  | 错误
----------------|--------|-----------|-------|------
local_search    | 12     | 3.2K      | 0.8s  | -
global_search   | 8      | 2.1K      | 0.6s  | -
vector_search   | 27     | 8.5K      | 1.2s  | -
```

#### 3.2 Source聚合视图
```
┌─────────────────────────────────────┐
│ Source: abc123                      │
│ 标题: "Inception情节分析"            │
│ 命中次数: 3次                        │
│ 来源路径: local(2), global(1)       │
├─────────────────────────────────────┤
│ Sample Evidence:                    │
│ "Inception是一部2010年的科幻电影..." │
├─────────────────────────────────────┤
│ [查看完整内容]  [在源内容中打开]   │
└─────────────────────────────────────┘
```

**交互**：
- 点击Source ID：打开Source Drawer（现有功能）
- 显示Sample Evidence：让用户快速判断相关性

#### 3.3 检索质量指标
```
总检索数: 47条
去重后: 35条（重复12条）
平均相关性评分: 0.82
```

#### 3.4 数据来源
- **rag_runs**: 提取agent_type, retrieval_count, context_length, error
- **execution_log中的检索node**: 提取top_sources, sample_evidence
- **聚合逻辑**: 按source_id聚合，统计命中次数和来源路径

### 4. 原始（Raw / Export）

**目标**：完整JSON，用于复制/下载/粘贴到issue

#### 4.1 功能
- 完整的DebugData JSON（格式化）
- **复制按钮**：一键复制到剪贴板
- **下载按钮**：下载为JSON文件（文件名：debug_{request_id}.json）
- **筛选器**（可选）：
  - 只看execution_log
  - 只看rag_runs
  - 只看route_decision

#### 4.2 保留字段
- execution_log
- route_decision
- rag_runs
- progress_events（降级到这里，不再作为独立Tab）
- error_events（降级到这里，错误在时间线中已经显示）

#### 4.3 实现要点
- 使用`<pre>`标签 + JSON.stringify(debugData, null, 2)
- 使用`Button`组件实现复制/下载
- 可选：使用react-json-view渲染可折叠的JSON树（更友好）

## 重复项合并/降级

### 删除/合并
| 原Tab | 处理方式 | 理由 |
|-------|---------|------|
| errors | **合并到时间线** | 每个node的error状态在时间线中已经标识，顶部可加"错误汇总"卡片 |
| progress_events | **降级到Raw** | 主要用于流式过程中的进度条，事后调试优先看时间线 |

### 提升
| 原位置 | 新位置 | 理由 |
|-------|--------|------|
| route_decision（独立Tab） | **概览（摘要）** | 作为核心决策信息，应在概览显示 |
| rag_runs（独立Tab） | **概览（统计） + 检索（详情表格）** | 分层展示：概览看总数，检索看明细 |

## Tab顺序

```
[概览] [时间线] [检索] [原始]
```

- **概览**：默认，快速了解整体情况
- **时间线**：深入排查问题
- **检索**：专注检索质量
- **原始**：导出数据

## 实现路线图

### Phase 1: 概览Tab（MVP）
- [ ] 创建Overview组件
- [ ] 实现路由决策卡片（route_decision摘要）
- [ ] 实现检索概览卡片（rag_runs统计）
- [ ] 实现Top Sources卡片
- [ ] 集成到Drawer

### Phase 2: 时间线Tab
- [ ] 创建Timeline组件
- [ ] 实现node状态标识（✓/✗/⏱）
- [ ] 实现摘要字段提取逻辑（按node类型）
- [ ] 实现折叠的input/output显示
- [ ] 添加错误汇总（顶部卡片）

### Phase 3: 检索Tab
- [ ] 创建Retrieval组件
- [ ] 实现检索路径表格（rag_runs）
- [ ] 实现Source聚合逻辑
- [ ] 实现Source卡片（sample evidence）
- [ ] 集成Source Drawer跳转

### Phase 4: 原始Tab
- [ ] 创建Raw组件
- [ ] 实现JSON显示（格式化）
- [ ] 实现复制按钮
- [ ] 实现下载按钮
- [ ] （可选）使用react-json-view

### Phase 5: 优化
- [ ] 移除旧的独立Tab（errors, progress）
- [ ] 调整默认Tab为"概览"
- [ ] 添加性能指标计算（耗时）
- [ ] 完善错误处理和空状态显示

## 数据结构参考

### DebugData 接口（现有）
```typescript
export interface DebugData {
  request_id: string;
  execution_log?: unknown[];
  route_decision?: unknown;
  rag_runs?: unknown[];
  progress_events?: unknown[];
  error_events?: unknown[];
}
```

### 期望的execution_log节点结构
```typescript
interface ExecutionLogNode {
  node: string;                    // 节点名称
  timestamp: string;               // ISO时间戳
  status?: 'ok' | 'error' | 'timeout';
  input?: unknown;
  output?: unknown;
  error?: {
    type: string;
    message: string;
  };
  // 特定节点的额外字段
  retrieval_count?: number;        // 检索节点
  granularity?: string;
  top_sources?: string[];
  sample_evidence?: string;
  model?: string;                  // 生成节点
  tokens?: number;
  finish_reason?: string;
  selected_agent?: string;         // 路由节点
  reasoning?: string;
}
```

### 期望的rag_runs结构
```typescript
interface RagRun {
  agent_type: string;
  retrieval_count: number;
  context_length: number;
  duration_ms?: number;
  error?: string;
  top_sources?: string[];
}
```

## 注意事项

1. **后端兼容性**：设计时假设后端已补充granularity、top_sources、sample_evidence字段，但前端应做容错处理（字段不存在时优雅降级）

2. **性能**：
   - Source聚合逻辑可能涉及大量数据，建议使用useMemo缓存
   - JSON渲染用react-json-view时设置collapsed层级，避免一次展开过多内容

3. **可扩展性**：
   - node类型和摘要字段的映射应该是可配置的（未来可能有新的node类型）
   - 考虑使用策略模式处理不同node类型的摘要提取

4. **用户体验**：
   - 所有Tab应有"暂无数据"的空状态提示
   - 时间线的timestamp应格式化为可读格式（HH:mm:ss.SSS）
   - 错误信息应高亮显示，方便快速定位

## 示例代码框架

### 概览Tab
```typescript
function OverviewTab({ debugData }: { debugData: DebugData | null }) {
  const routeSummary = useMemo(() => {
    if (!debugData?.route_decision) return null;
    const rd = debugData.route_decision as any;
    return {
      agent: rd.selected_agent || 'unknown',
      reasoning: rd.reasoning || '',
    };
  }, [debugData]);

  const ragSummary = useMemo(() => {
    if (!debugData?.rag_runs) return null;
    const runs = debugData.rag_runs as any[];
    return {
      total: runs.reduce((sum, r) => sum + (r.retrieval_count || 0), 0),
      paths: runs.length,
      errors: runs.filter(r => r.error).length,
    };
  }, [debugData]);

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Card title="路由决策" size="small">
        <Descriptions size="small">
          <Descriptions.Item label="Agent">{routeSummary?.agent}</Descriptions.Item>
        </Descriptions>
        <Collapse size="small">
          <Collapse.Panel header="详情" key="1">
            <pre>{JSON.stringify(debugData?.route_decision, null, 2)}</pre>
          </Collapse.Panel>
        </Collapse>
      </Card>

      <Card title="检索概览" size="small">
        <Statistic title="总命中数" value={ragSummary?.total || 0} />
        <Statistic title="检索路径" value={`${ragSummary?.paths || 0}路`} />
        <Statistic title="错误" value={ragSummary?.errors || 0} />
      </Card>
    </Space>
  );
}
```

### 时间线Tab
```typescript
function TimelineTab({ executionLog }: { executionLog: unknown[] }) {
  const nodes = executionLog.map((entry, idx) => {
    const node = entry as any;
    const status = node.error ? 'error' : 'ok';
    const color = status === 'error' ? 'red' : 'green';

    // 提取摘要字段
    const summary = extractSummary(node);

    return {
      key: idx,
      color,
      label: `${idx + 1}. ${node.node} (${node.timestamp})`,
      summary,
      node,
    };
  });

  return (
    <Timeline>
      {nodes.map(n => (
        <Timeline.Item key={n.key} color={n.color}>
          <Card size="small" title={n.label}>
            <Descriptions size="small">
              {Object.entries(n.summary).map(([k, v]) => (
                <Descriptions.Item key={k} label={k}>{v}</Descriptions.Item>
              ))}
            </Descriptions>
            <Collapse size="small">
              <Collapse.Panel header="输入/输出" key="io">
                <pre>{JSON.stringify(n.node, null, 2)}</pre>
              </Collapse.Panel>
            </Collapse>
          </Card>
        </Timeline.Item>
      ))}
    </Timeline>
  );
}

function extractSummary(node: any): Record<string, any> {
  const type = node.node;
  if (type.includes('retrieval')) {
    return {
      '检索数': node.retrieval_count || 0,
      '粒度': node.granularity || '-',
      'Top Sources': (node.top_sources || []).join(', '),
    };
  }
  // 其他类型...
  return {};
}
```

## 总结

此重设计将调试信息从5个平级、重复的Tab重构为4个有明确职责的视图：
1. **概览**：快速回答"发生了什么"
2. **时间线**：详细追踪"怎么发生的"
3. **检索**：深入分析"找到了什么"
4. **原始**：导出/分享数据

通过合并errors和降级progress_events，减少信息冗余，提升用户体验。

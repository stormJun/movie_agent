# 调试信息抽屉重设计 - 完整实现指南

> 本文档提供可直接落地的完整实现方案，包括组件代码、类型定义、工具函数、样式规范等。

## 目录
1. [架构设计](#架构设计)
2. [类型定义](#类型定义)
3. [工具函数](#工具函数)
4. [组件实现](#组件实现)
5. [样式规范](#样式规范)
6. [集成指南](#集成指南)

---

## 架构设计

### 文件结构
```
frontend-react/src/
├── components/
│   └── debug/
│       ├── DebugDrawer.tsx          # 主抽屉容器
│       ├── OverviewTab.tsx          # 概览Tab
│       ├── TimelineTab.tsx          # 时间线Tab
│       ├── RetrievalTab.tsx         # 检索Tab
│       ├── RawTab.tsx               # 原始Tab
│       ├── ErrorSummary.tsx         # 错误汇总组件
│       ├── SourceCard.tsx           # Source卡片组件
│       └── debug.types.ts           # 调试专用类型
├── utils/
│   └── debugHelpers.ts              # 调试数据处理工具函数
└── styles/
    └── debug.css                    # 调试抽屉样式
```

---

## 类型定义

### `debug.types.ts`

```typescript
import type { DebugData } from '../types/chat';

// ========== 执行日志节点类型 ==========

export interface ExecutionLogNode {
  node: string;
  timestamp: string;
  duration_ms?: number;
  status?: 'ok' | 'error' | 'timeout' | 'warning';
  input?: unknown;
  output?: unknown;
  error?: {
    type: string;
    message: string;
    stack?: string;
  };
  // 检索节点特定字段
  retrieval_count?: number;
  granularity?: string;
  top_sources?: string[];
  sample_evidence?: string;
  context_length?: number;
  // 生成节点特定字段
  model?: string;
  tokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  finish_reason?: string;
  // 路由节点特定字段
  selected_agent?: string;
  reasoning?: string;
  confidence?: number;
}

// ========== RAG运行记录类型 ==========

export interface RagRun {
  agent_type: string;
  retrieval_count: number;
  context_length: number;
  duration_ms?: number;
  error?: string | null;
  top_sources?: string[];
  granularity?: string;
}

// ========== 路由决策类型 ==========

export interface RouteDecision {
  selected_agent: string;
  reasoning?: string;
  confidence?: number;
  alternatives?: Array<{
    agent: string;
    score: number;
  }>;
}

// ========== 聚合数据类型 ==========

export interface PerformanceMetrics {
  totalDuration: number;
  retrievalDuration: number;
  generationDuration: number;
  routingDuration: number;
  nodeCount: number;
  errorCount: number;
}

export interface RetrievalSummary {
  totalPaths: number;
  totalHits: number;
  totalErrors: number;
  pathDetails: Array<{
    agentType: string;
    count: number;
    error?: string;
  }>;
}

export interface SourceAggregation {
  sourceId: string;
  title?: string;
  hitCount: number;
  paths: Array<{
    agentType: string;
    count: number;
  }>;
  sampleEvidence?: string;
}

export interface TimelineNode {
  index: number;
  node: ExecutionLogNode;
  status: 'success' | 'error' | 'timeout' | 'warning';
  color: string;
  icon: string;
  summary: Record<string, any>;
  duration: string;
  timestamp: string;
}

// ========== Tab组件Props ==========

export interface DebugTabProps {
  debugData: DebugData | null;
  onOpenSource?: (sourceId: string) => void;
}

export interface TimelineTabProps {
  executionLog: ExecutionLogNode[];
  onOpenSource?: (sourceId: string) => void;
}

export interface RetrievalTabProps {
  ragRuns: RagRun[];
  executionLog: ExecutionLogNode[];
  onOpenSource?: (sourceId: string) => void;
}
```

---

## 工具函数

### `debugHelpers.ts`

```typescript
import dayjs from 'dayjs';
import type {
  ExecutionLogNode,
  RagRun,
  RouteDecision,
  PerformanceMetrics,
  RetrievalSummary,
  SourceAggregation,
  TimelineNode,
} from '../components/debug/debug.types';
import type { DebugData } from '../types/chat';

// ========== 类型守卫 ==========

export function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

export function isExecutionLogNode(value: unknown): value is ExecutionLogNode {
  return isPlainRecord(value) && typeof value.node === 'string';
}

export function isRagRun(value: unknown): value is RagRun {
  return (
    isPlainRecord(value) &&
    typeof value.agent_type === 'string' &&
    typeof value.retrieval_count === 'number'
  );
}

// ========== 格式化工具 ==========

export function formatTimestamp(ts: string): string {
  try {
    return dayjs(ts).format('HH:mm:ss.SSS');
  } catch {
    return ts;
  }
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return String(num);
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

// ========== 数据提取 ==========

/**
 * 从DebugData中提取所有ExecutionLogNode
 */
export function extractExecutionLog(debugData: DebugData | null): ExecutionLogNode[] {
  if (!debugData?.execution_log) return [];
  return debugData.execution_log
    .filter(isExecutionLogNode)
    .map((node) => ({
      ...node,
      status: node.error ? 'error' : 'ok',
    }));
}

/**
 * 从DebugData中提取所有RagRun
 */
export function extractRagRuns(debugData: DebugData | null): RagRun[] {
  if (!debugData?.rag_runs) return [];
  return debugData.rag_runs.filter(isRagRun);
}

/**
 * 从DebugData中提取RouteDecision
 */
export function extractRouteDecision(debugData: DebugData | null): RouteDecision | null {
  if (!debugData?.route_decision || !isPlainRecord(debugData.route_decision)) return null;
  const rd = debugData.route_decision;
  return {
    selected_agent: String(rd.selected_agent || 'unknown'),
    reasoning: rd.reasoning ? String(rd.reasoning) : undefined,
    confidence: typeof rd.confidence === 'number' ? rd.confidence : undefined,
    alternatives: Array.isArray(rd.alternatives) ? rd.alternatives : undefined,
  };
}

// ========== 性能指标计算 ==========

/**
 * 计算性能指标
 */
export function calculatePerformanceMetrics(nodes: ExecutionLogNode[]): PerformanceMetrics {
  if (nodes.length === 0) {
    return {
      totalDuration: 0,
      retrievalDuration: 0,
      generationDuration: 0,
      routingDuration: 0,
      nodeCount: 0,
      errorCount: 0,
    };
  }

  let retrievalDuration = 0;
  let generationDuration = 0;
  let routingDuration = 0;
  let errorCount = 0;

  nodes.forEach((node) => {
    const duration = node.duration_ms || 0;
    const nodeName = node.node.toLowerCase();

    if (nodeName.includes('retrieval') || nodeName.includes('search')) {
      retrievalDuration += duration;
    } else if (nodeName.includes('generation') || nodeName.includes('llm')) {
      generationDuration += duration;
    } else if (nodeName.includes('route') || nodeName.includes('decision')) {
      routingDuration += duration;
    }

    if (node.error || node.status === 'error') {
      errorCount++;
    }
  });

  // 计算总耗时：最后一个节点的时间戳 - 第一个节点的时间戳
  let totalDuration = 0;
  if (nodes.length >= 2) {
    try {
      const start = dayjs(nodes[0].timestamp);
      const end = dayjs(nodes[nodes.length - 1].timestamp);
      totalDuration = end.diff(start);
    } catch {
      // 如果时间戳解析失败，用duration_ms总和作为fallback
      totalDuration = nodes.reduce((sum, n) => sum + (n.duration_ms || 0), 0);
    }
  }

  return {
    totalDuration,
    retrievalDuration,
    generationDuration,
    routingDuration,
    nodeCount: nodes.length,
    errorCount,
  };
}

// ========== 检索数据聚合 ==========

/**
 * 聚合检索概览数据
 */
export function aggregateRetrievalSummary(ragRuns: RagRun[]): RetrievalSummary {
  const totalPaths = ragRuns.length;
  const totalHits = ragRuns.reduce((sum, run) => sum + run.retrieval_count, 0);
  const totalErrors = ragRuns.filter((run) => run.error).length;

  const pathDetails = ragRuns.map((run) => ({
    agentType: run.agent_type,
    count: run.retrieval_count,
    error: run.error || undefined,
  }));

  return {
    totalPaths,
    totalHits,
    totalErrors,
    pathDetails,
  };
}

/**
 * 聚合Source数据
 */
export function aggregateSources(
  ragRuns: RagRun[],
  executionLog: ExecutionLogNode[]
): SourceAggregation[] {
  const sourceMap = new Map<string, SourceAggregation>();

  // 从rag_runs中提取top_sources
  ragRuns.forEach((run) => {
    if (!run.top_sources) return;
    run.top_sources.forEach((sourceId) => {
      if (!sourceMap.has(sourceId)) {
        sourceMap.set(sourceId, {
          sourceId,
          hitCount: 0,
          paths: [],
        });
      }
      const existing = sourceMap.get(sourceId)!;
      existing.hitCount++;
      const pathIndex = existing.paths.findIndex((p) => p.agentType === run.agent_type);
      if (pathIndex >= 0) {
        existing.paths[pathIndex].count++;
      } else {
        existing.paths.push({ agentType: run.agent_type, count: 1 });
      }
    });
  });

  // 从execution_log中提取sample_evidence
  executionLog.forEach((node) => {
    if (!node.top_sources || !Array.isArray(node.top_sources)) return;
    node.top_sources.forEach((sourceId) => {
      const agg = sourceMap.get(sourceId);
      if (agg && node.sample_evidence && !agg.sampleEvidence) {
        agg.sampleEvidence = truncateText(node.sample_evidence, 200);
      }
    });
  });

  return Array.from(sourceMap.values()).sort((a, b) => b.hitCount - a.hitCount);
}

// ========== 时间线节点处理 ==========

/**
 * 提取节点摘要字段
 */
export function extractNodeSummary(node: ExecutionLogNode): Record<string, any> {
  const nodeName = node.node.toLowerCase();
  const summary: Record<string, any> = {};

  // 检索类节点
  if (nodeName.includes('retrieval') || nodeName.includes('search')) {
    if (node.retrieval_count !== undefined) {
      summary['检索数'] = node.retrieval_count;
    }
    if (node.granularity) {
      summary['粒度'] = node.granularity;
    }
    if (node.context_length) {
      summary['上下文长度'] = formatNumber(node.context_length);
    }
    if (node.top_sources && node.top_sources.length > 0) {
      summary['Top Sources'] = node.top_sources.slice(0, 3).join(', ');
    }
    if (node.sample_evidence) {
      summary['样例证据'] = truncateText(node.sample_evidence, 100);
    }
  }
  // 生成类节点
  else if (nodeName.includes('generation') || nodeName.includes('llm')) {
    if (node.model) {
      summary['模型'] = node.model;
    }
    if (node.tokens) {
      summary['生成Token数'] = node.tokens;
    }
    if (node.prompt_tokens && node.completion_tokens) {
      summary['Token分布'] = `${node.prompt_tokens} + ${node.completion_tokens}`;
    }
    if (node.finish_reason) {
      summary['结束原因'] = node.finish_reason;
    }
  }
  // 路由类节点
  else if (nodeName.includes('route') || nodeName.includes('decision')) {
    if (node.selected_agent) {
      summary['选择Agent'] = node.selected_agent;
    }
    if (node.reasoning) {
      summary['理由'] = truncateText(node.reasoning, 150);
    }
    if (node.confidence !== undefined) {
      summary['置信度'] = `${(node.confidence * 100).toFixed(1)}%`;
    }
  }

  return summary;
}

/**
 * 确定节点状态和颜色
 */
export function getNodeStatusAndColor(node: ExecutionLogNode): {
  status: 'success' | 'error' | 'timeout' | 'warning';
  color: string;
  icon: string;
} {
  if (node.error) {
    const errorType = node.error.type?.toLowerCase() || '';
    if (errorType.includes('timeout')) {
      return { status: 'timeout', color: 'orange', icon: '⏱' };
    }
    return { status: 'error', color: 'red', icon: '✗' };
  }

  // 警告：检索数为0但不是错误
  if (
    (node.node.includes('retrieval') || node.node.includes('search')) &&
    node.retrieval_count === 0
  ) {
    return { status: 'warning', color: 'gold', icon: '⚠' };
  }

  return { status: 'success', color: 'green', icon: '✓' };
}

/**
 * 将ExecutionLogNode转换为TimelineNode
 */
export function convertToTimelineNodes(nodes: ExecutionLogNode[]): TimelineNode[] {
  return nodes.map((node, index) => {
    const { status, color, icon } = getNodeStatusAndColor(node);
    const summary = extractNodeSummary(node);
    const duration = node.duration_ms ? formatDuration(node.duration_ms) : '-';
    const timestamp = formatTimestamp(node.timestamp);

    return {
      index: index + 1,
      node,
      status,
      color,
      icon,
      summary,
      duration,
      timestamp,
    };
  });
}

// ========== Top Sources提取 ==========

/**
 * 从rag_runs中提取Top N个sources
 */
export function extractTopSources(ragRuns: RagRun[], limit: number = 5): string[] {
  const sourceCountMap = new Map<string, number>();

  ragRuns.forEach((run) => {
    if (!run.top_sources) return;
    run.top_sources.forEach((sourceId) => {
      sourceCountMap.set(sourceId, (sourceCountMap.get(sourceId) || 0) + 1);
    });
  });

  return Array.from(sourceCountMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([sourceId]) => sourceId);
}

// ========== 错误汇总 ==========

export interface ErrorSummaryItem {
  node: string;
  errorType: string;
  errorMessage: string;
  timestamp: string;
}

/**
 * 汇总所有错误
 */
export function summarizeErrors(nodes: ExecutionLogNode[]): ErrorSummaryItem[] {
  return nodes
    .filter((node) => node.error)
    .map((node) => ({
      node: node.node,
      errorType: node.error!.type || 'UnknownError',
      errorMessage: node.error!.message || 'No message',
      timestamp: formatTimestamp(node.timestamp),
    }));
}
```

---

## 组件实现

### 1. `DebugDrawer.tsx` - 主容器

```typescript
import React from 'react';
import { Drawer, Tabs, Alert } from 'antd';
import type { DebugData } from '../../types/chat';
import OverviewTab from './OverviewTab';
import TimelineTab from './TimelineTab';
import RetrievalTab from './RetrievalTab';
import RawTab from './RawTab';
import { extractExecutionLog, extractRagRuns } from '../../utils/debugHelpers';

interface DebugDrawerProps {
  open: boolean;
  onClose: () => void;
  debugData: DebugData | null;
  debugMode: boolean;
  onOpenSource?: (sourceId: string) => void;
}

const DebugDrawer: React.FC<DebugDrawerProps> = ({
  open,
  onClose,
  debugData,
  debugMode,
  onOpenSource,
}) => {
  const executionLog = extractExecutionLog(debugData);
  const ragRuns = extractRagRuns(debugData);

  return (
    <Drawer
      title="调试信息"
      open={open}
      width={800}
      onClose={onClose}
      className="debug-drawer"
    >
      {debugMode && !debugData ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="调试模式已开启：回答结束后会自动拉取 debug 数据并展示在这里。"
        />
      ) : null}

      <Tabs
        defaultActiveKey="overview"
        items={[
          {
            key: 'overview',
            label: '概览',
            children: <OverviewTab debugData={debugData} onOpenSource={onOpenSource} />,
          },
          {
            key: 'timeline',
            label: `时间线 (${executionLog.length})`,
            children: (
              <TimelineTab executionLog={executionLog} onOpenSource={onOpenSource} />
            ),
          },
          {
            key: 'retrieval',
            label: `检索 (${ragRuns.length}路)`,
            children: (
              <RetrievalTab
                ragRuns={ragRuns}
                executionLog={executionLog}
                onOpenSource={onOpenSource}
              />
            ),
          },
          {
            key: 'raw',
            label: '原始数据',
            children: <RawTab debugData={debugData} />,
          },
        ]}
      />
    </Drawer>
  );
};

export default DebugDrawer;
```

### 2. `OverviewTab.tsx` - 概览Tab

```typescript
import React, { useMemo } from 'react';
import { Space, Card, Descriptions, Statistic, Row, Col, Collapse, Tag, Empty } from 'antd';
import {
  ClockCircleOutlined,
  SearchOutlined,
  BranchesOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import type { DebugTabProps } from './debug.types';
import {
  extractExecutionLog,
  extractRagRuns,
  extractRouteDecision,
  calculatePerformanceMetrics,
  aggregateRetrievalSummary,
  extractTopSources,
  formatDuration,
  prettyJson,
  summarizeErrors,
} from '../../utils/debugHelpers';
import ErrorSummary from './ErrorSummary';

const OverviewTab: React.FC<DebugTabProps> = ({ debugData, onOpenSource }) => {
  const executionLog = useMemo(() => extractExecutionLog(debugData), [debugData]);
  const ragRuns = useMemo(() => extractRagRuns(debugData), [debugData]);
  const routeDecision = useMemo(() => extractRouteDecision(debugData), [debugData]);

  const performance = useMemo(() => calculatePerformanceMetrics(executionLog), [executionLog]);
  const retrievalSummary = useMemo(() => aggregateRetrievalSummary(ragRuns), [ragRuns]);
  const topSources = useMemo(() => extractTopSources(ragRuns, 5), [ragRuns]);
  const errors = useMemo(() => summarizeErrors(executionLog), [executionLog]);

  if (!debugData) {
    return (
      <Empty
        description="暂无调试数据"
        style={{ marginTop: 48 }}
      />
    );
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* 错误汇总（如果有错误） */}
      {errors.length > 0 && <ErrorSummary errors={errors} />}

      {/* 路由决策 */}
      {routeDecision && (
        <Card
          title={
            <span>
              <BranchesOutlined style={{ marginRight: 8 }} />
              路由决策
            </span>
          }
          size="small"
        >
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="选择Agent">{routeDecision.selected_agent}</Descriptions.Item>
            {routeDecision.confidence !== undefined && (
              <Descriptions.Item label="置信度">
                {(routeDecision.confidence * 100).toFixed(1)}%
              </Descriptions.Item>
            )}
          </Descriptions>
          {routeDecision.reasoning && (
            <Collapse size="small" bordered={false} style={{ marginTop: 8 }}>
              <Collapse.Panel header="决策理由" key="reasoning">
                <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>
                  {routeDecision.reasoning}
                </div>
              </Collapse.Panel>
            </Collapse>
          )}
          <Collapse size="small" bordered={false} style={{ marginTop: 4 }}>
            <Collapse.Panel header="完整数据" key="full">
              <pre style={{ fontSize: 12 }}>{prettyJson(debugData.route_decision)}</pre>
            </Collapse.Panel>
          </Collapse>
        </Card>
      )}

      {/* 检索概览 */}
      <Card
        title={
          <span>
            <SearchOutlined style={{ marginRight: 8 }} />
            检索概览
          </span>
        }
        size="small"
      >
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="检索路径" value={retrievalSummary.totalPaths} suffix="路" />
          </Col>
          <Col span={8}>
            <Statistic title="总命中数" value={retrievalSummary.totalHits} suffix="条" />
          </Col>
          <Col span={8}>
            <Statistic
              title="错误/超时"
              value={retrievalSummary.totalErrors}
              valueStyle={{ color: retrievalSummary.totalErrors > 0 ? '#ff4d4f' : '#52c41a' }}
            />
          </Col>
        </Row>
        {retrievalSummary.pathDetails.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>路径详情：</div>
            <Space wrap size={[8, 8]}>
              {retrievalSummary.pathDetails.map((detail, idx) => (
                <Tag key={idx} color={detail.error ? 'red' : 'blue'}>
                  {detail.agentType}: {detail.count}条
                  {detail.error && ' (错误)'}
                </Tag>
              ))}
            </Space>
          </div>
        )}
      </Card>

      {/* 性能指标 */}
      <Card
        title={
          <span>
            <ClockCircleOutlined style={{ marginRight: 8 }} />
            性能指标
          </span>
        }
        size="small"
      >
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="总耗时"
              value={formatDuration(performance.totalDuration)}
              valueStyle={{ fontSize: 16 }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="检索"
              value={formatDuration(performance.retrievalDuration)}
              valueStyle={{ fontSize: 14 }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="生成"
              value={formatDuration(performance.generationDuration)}
              valueStyle={{ fontSize: 14 }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="路由"
              value={formatDuration(performance.routingDuration)}
              valueStyle={{ fontSize: 14 }}
            />
          </Col>
        </Row>
        <div style={{ marginTop: 12, fontSize: 12, color: '#999' }}>
          执行节点: {performance.nodeCount} | 错误: {performance.errorCount}
        </div>
      </Card>

      {/* Top Sources */}
      {topSources.length > 0 && (
        <Card
          title={
            <span>
              <FileTextOutlined style={{ marginRight: 8 }} />
              Top Sources
            </span>
          }
          size="small"
        >
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {topSources.map((sourceId, idx) => (
              <div
                key={sourceId}
                style={{
                  padding: '8px 12px',
                  background: '#fafafa',
                  borderRadius: 4,
                  cursor: onOpenSource ? 'pointer' : 'default',
                  transition: 'all 0.2s',
                }}
                onClick={() => onOpenSource?.(sourceId)}
                onMouseEnter={(e) => {
                  if (onOpenSource) {
                    e.currentTarget.style.background = '#f0f0f0';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = '#fafafa';
                }}
              >
                <span style={{ fontWeight: 500, marginRight: 8 }}>
                  {idx + 1}.
                </span>
                <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#1890ff' }}>
                  {sourceId}
                </span>
              </div>
            ))}
          </Space>
        </Card>
      )}
    </Space>
  );
};

export default OverviewTab;
```

### 3. `ErrorSummary.tsx` - 错误汇总组件

```typescript
import React from 'react';
import { Alert, Collapse, Descriptions } from 'antd';
import type { ErrorSummaryItem } from '../../utils/debugHelpers';

interface ErrorSummaryProps {
  errors: ErrorSummaryItem[];
}

const ErrorSummary: React.FC<ErrorSummaryProps> = ({ errors }) => {
  if (errors.length === 0) return null;

  return (
    <Alert
      type="error"
      showIcon
      message={`检测到 ${errors.length} 个错误`}
      description={
        <Collapse size="small" bordered={false} style={{ background: 'transparent' }}>
          <Collapse.Panel header="查看错误详情" key="errors">
            {errors.map((err, idx) => (
              <Descriptions
                key={idx}
                size="small"
                column={1}
                bordered
                style={{ marginBottom: idx < errors.length - 1 ? 12 : 0 }}
              >
                <Descriptions.Item label="节点">{err.node}</Descriptions.Item>
                <Descriptions.Item label="错误类型">{err.errorType}</Descriptions.Item>
                <Descriptions.Item label="错误信息">{err.errorMessage}</Descriptions.Item>
                <Descriptions.Item label="时间">{err.timestamp}</Descriptions.Item>
              </Descriptions>
            ))}
          </Collapse.Panel>
        </Collapse>
      }
    />
  );
};

export default ErrorSummary;
```

### 4. `TimelineTab.tsx` - 时间线Tab

```typescript
import React, { useMemo } from 'react';
import { Timeline, Card, Descriptions, Collapse, Empty, Tag } from 'antd';
import type { TimelineTabProps } from './debug.types';
import { convertToTimelineNodes, prettyJson } from '../../utils/debugHelpers';
import ErrorSummary from './ErrorSummary';
import { summarizeErrors } from '../../utils/debugHelpers';

const TimelineTab: React.FC<TimelineTabProps> = ({ executionLog, onOpenSource }) => {
  const timelineNodes = useMemo(() => convertToTimelineNodes(executionLog), [executionLog]);
  const errors = useMemo(() => summarizeErrors(executionLog), [executionLog]);

  if (executionLog.length === 0) {
    return (
      <Empty
        description="暂无执行轨迹（请开启调试模式并发送消息）"
        style={{ marginTop: 48 }}
      />
    );
  }

  return (
    <div>
      {errors.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <ErrorSummary errors={errors} />
        </div>
      )}

      <Timeline>
        {timelineNodes.map((item) => (
          <Timeline.Item key={item.index} color={item.color} dot={<span>{item.icon}</span>}>
            <Card
              size="small"
              title={
                <span>
                  <Tag color={item.color}>{item.index}</Tag>
                  <span style={{ fontWeight: 600 }}>{item.node.node}</span>
                </span>
              }
              extra={
                <span style={{ fontSize: 12, color: '#999' }}>
                  {item.timestamp} | {item.duration}
                </span>
              }
            >
              {/* 摘要字段 */}
              {Object.keys(item.summary).length > 0 && (
                <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
                  {Object.entries(item.summary).map(([key, value]) => (
                    <Descriptions.Item key={key} label={key}>
                      {String(value)}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              )}

              {/* 错误信息 */}
              {item.node.error && (
                <div
                  style={{
                    padding: 8,
                    background: '#fff2e8',
                    borderLeft: '3px solid #ff4d4f',
                    marginBottom: 12,
                    borderRadius: 4,
                  }}
                >
                  <div style={{ fontWeight: 500, color: '#ff4d4f', marginBottom: 4 }}>
                    {item.node.error.type}
                  </div>
                  <div style={{ fontSize: 12, color: '#666' }}>
                    {item.node.error.message}
                  </div>
                </div>
              )}

              {/* 输入/输出 */}
              <Collapse size="small" bordered={false}>
                <Collapse.Panel header="输入 (Input)" key="input">
                  <pre style={{ fontSize: 11, maxHeight: 300, overflow: 'auto' }}>
                    {prettyJson(item.node.input ?? {})}
                  </pre>
                </Collapse.Panel>
                <Collapse.Panel header="输出 (Output)" key="output">
                  <pre style={{ fontSize: 11, maxHeight: 300, overflow: 'auto' }}>
                    {prettyJson(item.node.output ?? {})}
                  </pre>
                </Collapse.Panel>
              </Collapse>
            </Card>
          </Timeline.Item>
        ))}
      </Timeline>
    </div>
  );
};

export default TimelineTab;
```

### 5. `RetrievalTab.tsx` - 检索Tab

```typescript
import React, { useMemo } from 'react';
import { Table, Card, Empty, Space, Tag } from 'antd';
import type { RetrievalTabProps, SourceAggregation } from './debug.types';
import { aggregateSources, formatNumber } from '../../utils/debugHelpers';
import SourceCard from './SourceCard';

const RetrievalTab: React.FC<RetrievalTabProps> = ({
  ragRuns,
  execution Log,
  onOpenSource,
}) => {
  const sources = useMemo(
    () => aggregateSources(ragRuns, executionLog),
    [ragRuns, executionLog]
  );

  if (ragRuns.length === 0) {
    return (
      <Empty
        description="暂无检索数据（需要 debug=true 且走检索路径）"
        style={{ marginTop: 48 }}
      />
    );
  }

  const columns = [
    {
      title: 'Agent Type',
      dataIndex: 'agent_type',
      key: 'agent_type',
      width: 200,
    },
    {
      title: '检索数',
      dataIndex: 'retrieval_count',
      key: 'retrieval_count',
      width: 100,
      render: (count: number) => (
        <Tag color={count > 0 ? 'blue' : 'default'}>{count}</Tag>
      ),
    },
    {
      title: '上下文长度',
      dataIndex: 'context_length',
      key: 'context_length',
      width: 120,
      render: (len: number) => formatNumber(len),
    },
    {
      title: '粒度',
      dataIndex: 'granularity',
      key: 'granularity',
      width: 100,
      render: (g: string) => g || '-',
    },
    {
      title: '错误',
      dataIndex: 'error',
      key: 'error',
      render: (err: string) => (err ? <Tag color="red">{err}</Tag> : '-'),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* 检索路径表格 */}
      <Card title="检索路径" size="small">
        <Table
          dataSource={ragRuns}
          columns={columns}
          pagination={false}
          size="small"
          rowKey="agent_type"
        />
      </Card>

      {/* Source聚合 */}
      {sources.length > 0 && (
        <Card title={`Source聚合 (${sources.length}个)`} size="small">
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {sources.map((source) => (
              <SourceCard
                key={source.sourceId}
                source={source}
                onOpenSource={onOpenSource}
              />
            ))}
          </Space>
        </Card>
      )}
    </Space>
  );
};

export default RetrievalTab;
```

### 6. `SourceCard.tsx` - Source卡片组件

```typescript
import React from 'react';
import { Card, Tag, Space, Button } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import type { SourceAggregation } from './debug.types';

interface SourceCardProps {
  source: SourceAggregation;
  onOpenSource?: (sourceId: string) => void;
}

const SourceCard: React.FC<SourceCardProps> = ({ source, onOpenSource }) => {
  return (
    <Card
      size="small"
      style={{ background: '#fafafa' }}
      title={
        <Space>
          <FileTextOutlined />
          <code style={{ fontSize: 12, color: '#1890ff' }}>{source.sourceId}</code>
        </Space>
      }
      extra={<Tag color="blue">{source.hitCount}次</Tag>}
    >
      {/* 来源路径 */}
      <div style={{ marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: '#666', marginRight: 8 }}>来源路径:</span>
        <Space size={4}>
          {source.paths.map((path) => (
            <Tag key={path.agentType} size="small">
              {path.agentType}({path.count})
            </Tag>
          ))}
        </Space>
      </div>

      {/* Sample Evidence */}
      {source.sampleEvidence && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Sample Evidence:</div>
          <div
            style={{
              padding: 8,
              background: '#fff',
              borderRadius: 4,
              fontSize: 12,
              lineHeight: 1.6,
              color: '#333',
            }}
          >
            {source.sampleEvidence}
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      {onOpenSource && (
        <Button type="link" size="small" onClick={() => onOpenSource(source.sourceId)}>
          在源内容中打开
        </Button>
      )}
    </Card>
  );
};

export default SourceCard;
```

### 7. `RawTab.tsx` - 原始Tab

```typescript
import React, { useState } from 'react';
import { Button, Space, message, Radio, Empty } from 'antd';
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons';
import type { DebugTabProps } from './debug.types';
import { prettyJson } from '../../utils/debugHelpers';

const RawTab: React.FC<DebugTabProps> = ({ debugData }) => {
  const [filter, setFilter] = useState<'all' | 'execution_log' | 'rag_runs' | 'route_decision'>(
    'all'
  );

  if (!debugData) {
    return <Empty description="暂无原始数据" style={{ marginTop: 48 }} />;
  }

  const getFilteredData = () => {
    switch (filter) {
      case 'execution_log':
        return { execution_log: debugData.execution_log };
      case 'rag_runs':
        return { rag_runs: debugData.rag_runs };
      case 'route_decision':
        return { route_decision: debugData.route_decision };
      default:
        return debugData;
    }
  };

  const jsonString = prettyJson(getFilteredData());

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonString);
    message.success('已复制到剪贴板');
  };

  const handleDownload = () => {
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `debug_${debugData.request_id || 'unknown'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success('下载成功');
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* 工具栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Radio.Group value={filter} onChange={(e) => setFilter(e.target.value)} size="small">
          <Radio.Button value="all">全部</Radio.Button>
          <Radio.Button value="execution_log">execution_log</Radio.Button>
          <Radio.Button value="rag_runs">rag_runs</Radio.Button>
          <Radio.Button value="route_decision">route_decision</Radio.Button>
        </Radio.Group>

        <Space>
          <Button icon={<CopyOutlined />} size="small" onClick={handleCopy}>
            复制
          </Button>
          <Button icon={<DownloadOutlined />} size="small" onClick={handleDownload}>
            下载
          </Button>
        </Space>
      </div>

      {/* JSON显示 */}
      <pre
        style={{
          background: '#f5f5f5',
          padding: 16,
          borderRadius: 4,
          fontSize: 12,
          lineHeight: 1.5,
          maxHeight: 600,
          overflow: 'auto',
          border: '1px solid #e0e0e0',
        }}
      >
        {jsonString}
      </pre>
    </Space>
  );
};

export default RawTab;
```

---

## 样式规范

### `debug.css`

```css
/* ========== 调试抽屉样式 ========== */

.debug-drawer .ant-drawer-body {
  padding: 16px;
}

.debug-drawer .ant-tabs-nav {
  margin-bottom: 16px;
}

/* ========== 卡片样式 ========== */

.debug-drawer .ant-card {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.debug-drawer .ant-card-head {
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

/* ========== 时间线样式 ========== */

.debug-drawer .ant-timeline-item {
  padding-bottom: 24px;
}

.debug-drawer .ant-timeline-item-content {
  margin-left: 28px;
}

/* ========== 统计卡片样式 ========== */

.debug-drawer .ant-statistic-title {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.debug-drawer .ant-statistic-content {
  font-size: 20px;
  font-weight: 600;
}

/* ========== Descriptions样式 ========== */

.debug-drawer .ant-descriptions-item-label {
  font-Weight: 500;
  color: #666;
}

.debug-drawer .ant-descriptions-item-content {
  color: #333;
}

/* ========== Collapse样式 ========== */

.debug-drawer .ant-collapse {
  background: transparent;
}

.debug-drawer .ant-collapse-header {
  font-size: 13px;
  padding: 8px 12px !important;
  background: #f9f9f9;
  border-radius: 4px;
}

.debug-drawer .ant-collapse-content-box {
  padding: 12px;
  background: #fafafa;
}

/* ========== 错误样式 ========== */

.debug-drawer .ant-alert-error {
  border-left: 4px solid #ff4d4f;
}

/* ========== Source卡片hover效果 ========== */

.debug-drawer .source-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  transform: translateY(-1px);
  transition: all 0.2s;
}

/* ========== 代码块样式 ========== */

.debug-drawer pre {
  font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
  background: #2d2d2d;
  color: #f8f8f2;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
}

/* ========== Tag样式优化 ========== */

.debug-drawer .ant-tag {
  margin: 2px;
  border-radius: 4px;
}
```

---

## 集成指南

### Step 1: 安装依赖

```bash
npm install dayjs
```

### Step 2: 创建文件

按照[文件结构](#文件结构)创建所有必要的文件。

### Step 3: 在ChatPage.tsx中集成

```typescript
// 在ChatPage.tsx顶部导入
import DebugDrawer from '../components/debug/DebugDrawer';

// 在ChatPage组件中替换原有的Drawer
<DebugDrawer
  open={debugDrawerOpen}
  onClose={() => setDebugDrawerOpen(false)}
  debugData={latestDebugData}
  debugMode={debugMode}
  onOpenSource={(sourceId) => {
    // 打开Source Drawer的逻辑
    openSourceDrawerWithId(sourceId);
  }}
/>
```

### Step 4: 导入样式

```typescript
// 在main.tsx或App.tsx中导入
import './styles/debug.css';
```

### Step 5:验证

1. 开启调试模式
2. 发送一条消息
3. 点击"调试信息"按钮
4. 验证4个Tab都能正常显示

---

## 完成标准

- [ ] 所有组件无TypeScript错误
- [ ] 所有Tab能正常切换
- [ ] 概览Tab显示核心指标
- [ ] 时间线Tab正确显示所有节点
- [ ] 检索Tab显示Source聚合
- [ ] 原始Tab能复制和下载
- [ ] 错误高亮显示
- [ ] Source点击能打开Source Drawer
- [ ] 样式美观、间距合理
- [ ] 空状态有友好提示

---

## 后续优化

1. **性能优化**：对大数据量（>100节点）使用虚拟滚动
2. **交互增强**：添加搜索/筛选功能
3. **可视化**：用图表展示性能指标和检索分布
4. **导出增强**：支持导出为HTML/PDF
5. **国际化**：支持中英文切换

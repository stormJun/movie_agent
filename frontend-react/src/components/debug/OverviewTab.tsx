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
    extractConversationSummaryText,
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
    const summaryText = useMemo(() => extractConversationSummaryText(debugData), [debugData]);

    const performance = useMemo(() => calculatePerformanceMetrics(debugData), [debugData]);
    const retrievalSummary = useMemo(() => aggregateRetrievalSummary(ragRuns), [ragRuns]);
    const topSources = useMemo(() => extractTopSources(ragRuns, 5), [ragRuns]);
    const errors = useMemo(() => summarizeErrors(executionLog), [executionLog]);

    if (!debugData) {
        return <Empty description="暂无调试数据" style={{ marginTop: 48 }} />;
    }

    return (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {errors.length > 0 && <ErrorSummary errors={errors} />}

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
                        <Collapse
                            size="small"
                            bordered={false}
                            style={{ marginTop: 8 }}
                            items={[
                                {
                                    key: 'reasoning',
                                    label: '决策理由',
                                    children: (
                                        <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>
                                            {routeDecision.reasoning}
                                        </div>
                                    ),
                                },
                            ]}
                        />
                    )}
                    <Collapse
                        size="small"
                        bordered={false}
                        style={{ marginTop: 4 }}
                        items={[
                            {
                                key: 'full',
                                label: '完整数据',
                                children: <pre style={{ fontSize: 12 }}>{prettyJson(debugData.route_decision)}</pre>,
                            },
                        ]}
                    />
                </Card>
            )}

            <Card
                title={
                    <span>
                        <FileTextOutlined style={{ marginRight: 8 }} />
                        对话摘要（Phase 1）
                    </span>
                }
                size="small"
            >
                {summaryText ? (
                    <Collapse
                        size="small"
                        bordered={false}
                        items={[
                            {
                                key: 'summary',
                                label: '查看摘要内容',
                                children: <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{summaryText}</div>,
                            },
                        ]}
                    />
                ) : (
                    <div style={{ color: '#999', fontSize: 13 }}>
                        暂无摘要（需要对话达到一定长度后才会生成；并在 debug=true 时可在此查看）
                    </div>
                )}
            </Card>

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
                                <span style={{ fontWeight: 500, marginRight: 8 }}>{idx + 1}.</span>
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

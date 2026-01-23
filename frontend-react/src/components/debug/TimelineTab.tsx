import React, { useMemo } from 'react';
import { Timeline, Card, Descriptions, Collapse, Empty, Tag } from 'antd';
import type { TimelineTabProps } from './debug.types';
import { convertToTimelineNodes, prettyJson, summarizeErrors } from '../../utils/debugHelpers';
import ErrorSummary from './ErrorSummary';

const TimelineTab: React.FC<TimelineTabProps> = ({ executionLog }) => {
    const timelineNodes = useMemo(() => convertToTimelineNodes(executionLog), [executionLog]);
    const errors = useMemo(() => summarizeErrors(executionLog), [executionLog]);

    if (executionLog.length === 0) {
        return (
            <Empty description="暂无执行轨迹（请开启调试模式并发送消息）" style={{ marginTop: 48 }} />
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
                            {Object.keys(item.summary).length > 0 && (
                                <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
                                    {Object.entries(item.summary).map(([key, value]) => (
                                        <Descriptions.Item key={key} label={key}>
                                            {String(value)}
                                        </Descriptions.Item>
                                    ))}
                                </Descriptions>
                            )}

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
                                    <div style={{ fontSize: 12, color: '#666' }}>{item.node.error.message}</div>
                                </div>
                            )}

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

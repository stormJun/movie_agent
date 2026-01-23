import React, { useMemo } from 'react';
import { Table, Card, Empty, Space } from 'antd';
import type { RetrievalTabProps } from './debug.types';
import { aggregateSources, formatNumber } from '../../utils/debugHelpers';
import SourceCard from './SourceCard';
import type { ColumnsType } from 'antd/es/table';
import type { RagRun } from './debug.types';

const RetrievalTab: React.FC<RetrievalTabProps> = ({ ragRuns, executionLog, onOpenSource }) => {
    const sources = useMemo(() => aggregateSources(ragRuns, executionLog), [ragRuns, executionLog]);

    if (ragRuns.length === 0) {
        return (
            <Empty
                description="暂无检索数据（需要 debug=true 且走检索路径）"
                style={{ marginTop: 48 }}
            />
        );
    }

    const columns: ColumnsType<RagRun> = [
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
            render: (err: string) => err || '-',
        },
    ];

    return (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Card title="检索路径" size="small">
                <Table
                    dataSource={ragRuns}
                    columns={columns}
                    pagination={false}
                    size="small"
                    rowKey="agent_type"
                />
            </Card>

            {sources.length > 0 && (
                <Card title={`Source聚合 (${sources.length}个)`} size="small">
                    <Space direction="vertical" style={{ width: '100%' }} size="small">
                        {sources.map((source) => (
                            <SourceCard key={source.sourceId} source={source} onOpenSource={onOpenSource} />
                        ))}
                    </Space>
                </Card>
            )}
        </Space>
    );
};

export default RetrievalTab;

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
            <div style={{ marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: '#666', marginRight: 8 }}>来源路径:</span>
                <Space size={4}>
                    {source.paths.map((path, idx) => (
                        <Tag key={`${path.agentType}-${idx}`}>
                            {path.agentType}({path.count})
                        </Tag>
                    ))}
                </Space>
            </div>

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

            {onOpenSource && (
                <Button type="link" size="small" onClick={() => onOpenSource(source.sourceId)}>
                    在源内容中打开
                </Button>
            )}
        </Card>
    );
};

export default SourceCard;

import React from 'react';
import { Empty, List, Tag, Typography } from 'antd';
import type { EpisodicTabProps } from './debug.types';
import { formatNumber, truncateText } from '../../utils/debugHelpers';

const EpisodicTab: React.FC<EpisodicTabProps> = ({ episodes }) => {
    if (!episodes || episodes.length === 0) {
        return (
            <Empty description="暂无情节记忆召回（需开启：情节记忆功能 EPISODIC_MEMORY_ENABLE=true，并在请求中设置 debug=true）" />
        );
    }

    return (
        <div>
            <Typography.Paragraph style={{ marginBottom: 12, color: '#666' }}>
                这是本次对话中通过语义检索召回的相关历史片段（Episodic Memory）。
            </Typography.Paragraph>
            <List
                itemLayout="vertical"
                dataSource={episodes}
                renderItem={(ep, idx) => (
                    <List.Item key={ep.assistant_message_id || idx}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                            <Tag color="purple">Episode #{idx + 1}</Tag>
                            {typeof ep.similarity === 'number' ? (
                                <Tag color={ep.similarity >= 0.6 ? 'green' : ep.similarity >= 0.35 ? 'blue' : 'default'}>
                                    sim={formatNumber(ep.similarity)}
                                </Tag>
                            ) : null}
                        </div>
                        <Typography.Text strong>用户</Typography.Text>
                        <Typography.Paragraph style={{ marginTop: 4, marginBottom: 8 }}>
                            {truncateText(ep.user_message || '', 300) || '（空）'}
                        </Typography.Paragraph>
                        <Typography.Text strong>助手</Typography.Text>
                        <Typography.Paragraph style={{ marginTop: 4, marginBottom: 0 }}>
                            {truncateText(ep.assistant_message || '', 300) || '（空）'}
                        </Typography.Paragraph>
                    </List.Item>
                )}
            />
        </div>
    );
};

export default EpisodicTab;

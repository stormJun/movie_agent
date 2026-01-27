import React from 'react';
import { Alert, Collapse, Descriptions } from 'antd';
import type { ErrorSummaryItem } from './debug.types';

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
                <Collapse
                    size="small"
                    bordered={false}
                    style={{ background: 'transparent' }}
                    items={[
                        {
                            key: 'errors',
                            label: '查看错误详情',
                            children: errors.map((err, idx) => (
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
                            )),
                        },
                    ]}
                />
            }
        />
    );
};

export default ErrorSummary;

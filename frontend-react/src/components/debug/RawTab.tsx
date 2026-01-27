import React, { useState } from 'react';
import { Button, Space, message, Radio, Empty } from 'antd';
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons';
import type { DebugTabProps } from './debug.types';
import { prettyJson } from '../../utils/debugHelpers';

const RawTab: React.FC<DebugTabProps> = ({ debugData }) => {
    const [filter, setFilter] = useState<
        'all' | 'execution_log' | 'rag_runs' | 'route_decision' | 'combined_context'
    >(
        'all'
    );

    console.log('[RawTab] Received debugData:', debugData);

    if (!debugData) {
        console.log('[RawTab] debugData is null/undefined, showing empty state');
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
            case 'combined_context':
                return { combined_context: debugData.combined_context };
            default:
                return debugData;
        }
    };

    const jsonString = prettyJson(getFilteredData());
    console.log('[RawTab] jsonString length:', jsonString.length, 'preview:', jsonString.substring(0, 100));

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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Radio.Group value={filter} onChange={(e) => setFilter(e.target.value)} size="small">
                    <Radio.Button value="all">全部</Radio.Button>
                    <Radio.Button value="execution_log">execution_log</Radio.Button>
                    <Radio.Button value="rag_runs">rag_runs</Radio.Button>
                    <Radio.Button value="route_decision">route_decision</Radio.Button>
                    <Radio.Button value="combined_context">combined_context</Radio.Button>
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

            <pre
                className="raw-json-display"
                style={{
                    background: '#f5f5f5',
                    color: '#333',
                    padding: 16,
                    borderRadius: 4,
                    fontSize: 12,
                    fontFamily: 'SF Mono, Monaco, Menlo, monospace',
                    lineHeight: 1.5,
                    maxHeight: 600,
                    overflow: 'auto',
                    border: '1px solid #e0e0e0',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                }}
            >
                {jsonString}
            </pre>
        </Space>
    );
};

export default RawTab;

import React from 'react';
import { Button, Empty, Space, Tag, message as antdMessage } from 'antd';
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons';
import type { DebugTabProps } from './debug.types';

const ContextTab: React.FC<DebugTabProps> = ({ debugData }) => {
  const ctx = debugData?.combined_context;
  const text = (ctx?.text || '').toString();

  if (!debugData) {
    return <Empty description="暂无调试数据" style={{ marginTop: 48 }} />;
  }
  if (!ctx) {
    return <Empty description="暂无 combined_context（需开启调试模式）" style={{ marginTop: 48 }} />;
  }

  const meta = {
    total_chars: ctx.total_chars ?? text.length,
    max_chars: ctx.max_chars ?? undefined,
    truncated: Boolean(ctx.truncated),
    has_enrichment: Boolean(ctx.has_enrichment),
  };

  const header = (
    <Space wrap size="small">
      <Tag>total_chars: {meta.total_chars}</Tag>
      {typeof meta.max_chars === 'number' ? <Tag>max_chars: {meta.max_chars}</Tag> : null}
      <Tag color={meta.truncated ? 'orange' : 'green'}>{meta.truncated ? 'truncated' : 'full'}</Tag>
      <Tag color={meta.has_enrichment ? 'blue' : 'default'}>
        {meta.has_enrichment ? 'has_enrichment' : 'no_enrichment'}
      </Tag>
    </Space>
  );

  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    antdMessage.success('已复制到剪贴板');
  };

  const handleDownload = () => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `combined_context_${debugData.request_id || 'unknown'}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    antdMessage.success('下载成功');
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {header}
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
        {text || '(empty)'}
      </pre>
    </Space>
  );
};

export default ContextTab;

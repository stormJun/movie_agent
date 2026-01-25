import React from 'react';
import { Drawer, Tabs, Alert, Button } from 'antd';
import { ExportOutlined } from '@ant-design/icons';
import type { DebugData } from '../../types/chat';
import OverviewTab from './OverviewTab';
import TimelineTab from './TimelineTab';
import RetrievalTab from './RetrievalTab';
import EpisodicTab from './EpisodicTab';
import RawTab from './RawTab';
import { extractExecutionLog, extractRagRuns, extractEpisodicEpisodes } from '../../utils/debugHelpers';

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
    const episodicEpisodes = extractEpisodicEpisodes(debugData);

    console.log('[DebugDrawer] Props:', {
        open,
        debugMode,
        hasDebugData: !!debugData,
                debugDataKeys: debugData ? Object.keys(debugData) : [],
        executionLogCount: executionLog.length,
        ragRunsCount: ragRuns.length,
        episodicCount: episodicEpisodes.length,
    });

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
                        children: <TimelineTab executionLog={executionLog} onOpenSource={onOpenSource} />,
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
                        key: 'episodic',
                        label: `情节记忆 (${episodicEpisodes.length})`,
                        children: <EpisodicTab episodes={episodicEpisodes} />,
                    },
                    {
                        key: 'raw',
                        label: '原始数据',
                        children: <RawTab debugData={debugData} />,
                    },
                ]}
            />

            {/* Langfuse Link Button */}
            {debugData?.request_id && (
                <div style={{ marginTop: 24, textAlign: 'center', borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
                    <Button
                        type="link"
                        icon={<ExportOutlined />}
                        onClick={() => {
                            const langfuseHost = 'http://localhost:3000';
                            window.open(`${langfuseHost}/trace/${debugData.request_id}`, '_blank');
                        }}
                    >
                        在 Langfuse 中查看 LLM 调用详情
                    </Button>
                </div>
            )}
        </Drawer>
    );
};

export default DebugDrawer;

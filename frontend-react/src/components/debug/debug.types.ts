import type { DebugData } from '../../types/chat';

// ========== 执行日志节点类型 ==========

export interface ExecutionLogNode {
    node: string;
    node_type?: 'retrieval' | 'generation' | 'routing' | 'other';
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

// ========== Phase 2: 情节记忆（Episodic Memory）==========

export interface EpisodicEpisode {
    user_message?: string;
    assistant_message?: string;
    similarity?: number;
    created_at?: unknown;
    assistant_message_id?: string;
    user_message_id?: string;
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

export interface ErrorSummaryItem {
    node: string;
    errorType: string;
    errorMessage: string;
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

export interface EpisodicTabProps {
    episodes: EpisodicEpisode[];
}

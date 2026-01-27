import dayjs from 'dayjs';
import type {
    ExecutionLogNode,
    RagRun,
    RouteDecision,
    PerformanceMetrics,
    RetrievalSummary,
    SourceAggregation,
    TimelineNode,
    ErrorSummaryItem,
    EpisodicEpisode,
} from '../components/debug/debug.types';
import type { DebugData } from '../types/chat';
import type { JsonValue } from '../types/api';

// ========== 类型守卫 ==========

export function isPlainRecord(value: unknown): value is Record<string, unknown> {
    return !!value && typeof value === 'object' && !Array.isArray(value);
}

export function isExecutionLogNode(value: unknown): value is ExecutionLogNode {
    return isPlainRecord(value) && typeof value.node === 'string';
}

export function isRagRun(value: unknown): value is RagRun {
    return (
        isPlainRecord(value) &&
        typeof value.agent_type === 'string' &&
        typeof value.retrieval_count === 'number'
    );
}

// ========== 格式化工具 ==========

export function formatTimestamp(ts: string): string {
    try {
        return dayjs(ts).format('HH:mm:ss.SSS');
    } catch {
        return ts;
    }
}

export function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
}

export function formatNumber(num: number): string {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return String(num);
}

export function truncateText(text: string, maxLength: number): string {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
}

export function prettyJson(value: unknown): string {
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
}

// ========== 数据提取 ==========

export function extractExecutionLog(debugData: DebugData | null): ExecutionLogNode[] {
    if (!debugData?.execution_log) return [];
    const normalize = (raw: unknown): ExecutionLogNode | null => {
        if (!isExecutionLogNode(raw)) return null;
        const item = raw as ExecutionLogNode;
        const subSteps: ExecutionLogNode[] = [];
        if (Array.isArray((raw as any).sub_steps)) {
            for (const s of (raw as any).sub_steps) {
                const n = normalize(s);
                if (n) subSteps.push(n);
            }
        }
        return {
            node: item.node,
            timestamp: item.timestamp as any,
            duration_ms: item.duration_ms,
            status: item.error ? ('error' as const) : ('ok' as const),
            input: item.input,
            output: item.output,
            error: item.error,
            retrieval_count: item.retrieval_count,
            granularity: item.granularity,
            top_sources: item.top_sources,
            sample_evidence: item.sample_evidence,
            context_length: item.context_length,
            model: item.model,
            tokens: item.tokens,
            prompt_tokens: item.prompt_tokens,
            completion_tokens: item.completion_tokens,
            finish_reason: item.finish_reason,
            selected_agent: item.selected_agent,
            reasoning: item.reasoning,
            confidence: item.confidence,
            sub_steps: subSteps.length > 0 ? subSteps : undefined,
        };
    };

    const logs: ExecutionLogNode[] = [];
    for (const raw of debugData.execution_log) {
        const n = normalize(raw);
        if (n) logs.push(n);
    }
    return logs;
}

export function extractRagRuns(debugData: DebugData | null): RagRun[] {
    if (!debugData?.rag_runs) return [];
    const runs: RagRun[] = [];

    for (const item of debugData.rag_runs) {
        if (isRagRun(item)) {
            runs.push(item);
        }
    }

    return runs;
}

export function extractRouteDecision(debugData: DebugData | null): RouteDecision | null {
    if (!debugData?.route_decision || !isPlainRecord(debugData.route_decision)) return null;
    const rd = debugData.route_decision;

    const deriveSelectedAgent = (): string => {
        const selected = typeof rd.selected_agent === 'string' ? rd.selected_agent.trim() : '';
        if (selected) return selected;

        const agentType = typeof rd.agent_type === 'string' ? rd.agent_type.trim() : '';
        if (agentType) return agentType;

        // worker_name v2 is typically: {kb_prefix}:{agent_type}:{agent_mode}
        const worker = typeof rd.worker_name === 'string' ? rd.worker_name.trim() : '';
        if (worker) {
            const parts = worker.split(':').map((p) => p.trim()).filter(Boolean);
            if (parts.length >= 2) return parts[1];
            return parts[0];
        }
        return 'unknown';
    };

    const alternatives: Array<{ agent: string; score: number }> = [];
    if (Array.isArray(rd.alternatives)) {
        for (const alt of rd.alternatives) {
            if (isPlainRecord(alt) && typeof alt.agent === 'string' && typeof alt.score === 'number') {
                alternatives.push({ agent: alt.agent, score: alt.score });
            }
        }
    }

    return {
        selected_agent: deriveSelectedAgent(),
        reasoning: rd.reasoning ? String(rd.reasoning) : undefined,
        confidence: typeof rd.confidence === 'number' ? rd.confidence : undefined,
        alternatives: alternatives.length > 0 ? alternatives : undefined,
    };
}

export function extractEpisodicEpisodes(debugData: DebugData | null): EpisodicEpisode[] {
    const raw = debugData?.episodic_memory;
    if (!Array.isArray(raw)) return [];
    const episodes: EpisodicEpisode[] = [];
    for (const item of raw) {
        if (!isPlainRecord(item)) continue;
        episodes.push({
            user_message: typeof item.user_message === 'string' ? item.user_message : undefined,
            assistant_message: typeof item.assistant_message === 'string' ? item.assistant_message : undefined,
            similarity: typeof item.similarity === 'number' ? item.similarity : undefined,
            created_at: item.created_at as unknown,
            assistant_message_id: typeof item.assistant_message_id === 'string' ? item.assistant_message_id : undefined,
            user_message_id: typeof item.user_message_id === 'string' ? item.user_message_id : undefined,
        });
    }
    return episodes;
}

export function extractConversationSummaryText(debugData: DebugData | null): string | null {
    const raw = debugData?.conversation_summary;
    if (!raw || !isPlainRecord(raw)) return null;
    const t = raw.text;
    if (typeof t !== 'string') return null;
    const s = t.trim();
    return s ? s : null;
}

// ========== 性能指标计算 ==========

export function calculatePerformanceMetrics(
    debugDataOrNodes: DebugData | null | ExecutionLogNode[]
): PerformanceMetrics {
    // If debugData is provided and has performance_metrics from backend, use it directly
    if (
        debugDataOrNodes &&
        !Array.isArray(debugDataOrNodes) &&
        'performance_metrics' in debugDataOrNodes &&
        debugDataOrNodes.performance_metrics
    ) {
        const metrics = debugDataOrNodes.performance_metrics;
        return {
            totalDuration: metrics.total_duration_ms,
            retrievalDuration: metrics.retrieval_duration_ms,
            generationDuration: metrics.generation_duration_ms,
            routingDuration: metrics.routing_duration_ms,
            nodeCount: metrics.node_count,
            errorCount: metrics.error_count,
        };
    }

    // Fallback: calculate from nodes (backward compatibility)
    // Extract nodes from debugData or use nodes array directly
    const nodes: ExecutionLogNode[] = Array.isArray(debugDataOrNodes)
        ? debugDataOrNodes
        : extractExecutionLog(debugDataOrNodes);

    if (nodes.length === 0) {
        return {
            totalDuration: 0,
            retrievalDuration: 0,
            generationDuration: 0,
            routingDuration: 0,
            nodeCount: 0,
            errorCount: 0,
        };
    }

    // Legacy frontend calculation (deprecated, kept for backward compatibility)
    let retrievalDuration = 0;
    let generationDuration = 0;
    let routingDuration = 0;
    let errorCount = 0;

    nodes.forEach((node) => {
        const duration = node.duration_ms || 0;
        const nodeName = node.node.toLowerCase();
        const nodeType = node.node_type?.toLowerCase();

        // Use explicit node_type if available, otherwise infer from node name
        if (nodeType === 'retrieval' || nodeName.includes('retrieval') || nodeName.includes('search')) {
            retrievalDuration += duration;
        } else if (nodeType === 'generation' || nodeName.includes('generation') || nodeName.includes('llm')) {
            generationDuration += duration;
        } else if (nodeType === 'routing' || nodeName.includes('route') || nodeName.includes('decision')) {
            routingDuration += duration;
        }

        if (node.error || node.status === 'error') {
            errorCount++;
        }
    });

    let totalDuration = 0;
    if (nodes.length >= 2) {
        try {
            const start = dayjs(nodes[0].timestamp);
            const end = dayjs(nodes[nodes.length - 1].timestamp);
            totalDuration = end.diff(start);
        } catch {
            totalDuration = nodes.reduce((sum, n) => sum + (n.duration_ms || 0), 0);
        }
    }

    return {
        totalDuration,
        retrievalDuration,
        generationDuration,
        routingDuration,
        nodeCount: nodes.length,
        errorCount,
    };
}

// ========== 检索数据聚合 ==========

export function aggregateRetrievalSummary(ragRuns: RagRun[]): RetrievalSummary {
    const totalPaths = ragRuns.length;
    const totalHits = ragRuns.reduce((sum, run) => sum + run.retrieval_count, 0);
    const totalErrors = ragRuns.filter((run) => run.error).length;

    const pathDetails = ragRuns.map((run) => ({
        agentType: run.agent_type,
        count: run.retrieval_count,
        error: run.error || undefined,
    }));

    return {
        totalPaths,
        totalHits,
        totalErrors,
        pathDetails,
    };
}

export function aggregateSources(
    ragRuns: RagRun[],
    executionLog: ExecutionLogNode[]
): SourceAggregation[] {
    const sourceMap = new Map<string, SourceAggregation>();

    ragRuns.forEach((run) => {
        if (!run.top_sources) return;
        run.top_sources.forEach((sourceId) => {
            if (!sourceMap.has(sourceId)) {
                sourceMap.set(sourceId, {
                    sourceId,
                    hitCount: 0,
                    paths: [],
                });
            }
            const existing = sourceMap.get(sourceId)!;
            existing.hitCount++;
            const pathIndex = existing.paths.findIndex((p) => p.agentType === run.agent_type);
            if (pathIndex >= 0) {
                existing.paths[pathIndex].count++;
            } else {
                existing.paths.push({ agentType: run.agent_type, count: 1 });
            }
        });
    });

    executionLog.forEach((node) => {
        if (!node.top_sources || !Array.isArray(node.top_sources)) return;
        node.top_sources.forEach((sourceId) => {
            const agg = sourceMap.get(sourceId);
            if (agg && node.sample_evidence && !agg.sampleEvidence) {
                agg.sampleEvidence = truncateText(node.sample_evidence, 200);
            }
        });
    });

    return Array.from(sourceMap.values()).sort((a, b) => b.hitCount - a.hitCount);
}

// ========== 时间线节点处理 ==========

export function extractNodeSummary(node: ExecutionLogNode): Record<string, any> {
    const nodeName = node.node.toLowerCase();
    const summary: Record<string, any> = {};

    if (nodeName.includes('retrieval') || nodeName.includes('search')) {
        const out = isPlainRecord(node.output) ? node.output : null;

        const retrievalCount =
            node.retrieval_count !== undefined
                ? node.retrieval_count
                : out && typeof out.retrieval_count === 'number'
                    ? out.retrieval_count
                    : undefined;
        if (retrievalCount !== undefined) summary['检索数'] = retrievalCount;

        if (out) {
            const mapping: Array<[string, string]> = [
                ['raw_doc_count', 'raw_doc_count'],
                ['filtered_doc_count', 'filtered_doc_count'],
                ['community_count', 'community_count'],
                ['evidence_count', 'evidence_count'],
                ['content_length', 'content_length'],
                ['node_count', 'node_count'],
                ['edge_count', 'edge_count'],
                ['elapsed_ms', 'elapsed_ms'],
            ];
            for (const [k, label] of mapping) {
                const v = (out as any)[k];
                if (typeof v === 'number') summary[label] = v;
                else if (typeof v === 'string' && v.trim()) summary[label] = v.trim();
            }
        }
        if (node.granularity) {
            summary['粒度'] = node.granularity;
        }
        if (node.context_length) {
            summary['上下文长度'] = formatNumber(node.context_length);
        }
        if (node.top_sources && node.top_sources.length > 0) {
            summary['Top Sources'] = node.top_sources.slice(0, 3).join(', ');
        }
        if (node.sample_evidence) {
            summary['样例证据'] = truncateText(node.sample_evidence, 100);
        }
    } else if (nodeName.includes('generation') || nodeName.includes('llm')) {
        if (node.model) {
            summary['模型'] = node.model;
        }
        if (node.tokens) {
            summary['生成Token数'] = node.tokens;
        }
        if (node.prompt_tokens && node.completion_tokens) {
            summary['Token分布'] = `${node.prompt_tokens} + ${node.completion_tokens}`;
        }
        if (node.finish_reason) {
            summary['结束原因'] = node.finish_reason;
        }
    } else if (nodeName.includes('route') || nodeName.includes('decision')) {
        if (node.selected_agent) {
            summary['选择Agent'] = node.selected_agent;
        }
        if (node.reasoning) {
            summary['理由'] = truncateText(node.reasoning, 150);
        }
        if (node.confidence !== undefined) {
            summary['置信度'] = `${(node.confidence * 100).toFixed(1)}%`;
        }
    }

    return summary;
}

export function getNodeStatusAndColor(node: ExecutionLogNode): {
    status: 'success' | 'error' | 'timeout' | 'warning';
    color: string;
    icon: string;
} {
    if (node.error) {
        const errorType = node.error.type?.toLowerCase() || '';
        if (errorType.includes('timeout')) {
            return { status: 'timeout', color: 'orange', icon: '⏱' };
        }
        return { status: 'error', color: 'red', icon: '✗' };
    }

    if (
        (node.node.includes('retrieval') || node.node.includes('search')) &&
        node.retrieval_count === 0
    ) {
        return { status: 'warning', color: 'gold', icon: '⚠' };
    }

    return { status: 'success', color: 'green', icon: '✓' };
}

export function convertToTimelineNodes(nodes: ExecutionLogNode[]): TimelineNode[] {
    return nodes.map((node, index) => {
        const { status, color, icon } = getNodeStatusAndColor(node);
        const summary = extractNodeSummary(node);
        const duration = node.duration_ms ? formatDuration(node.duration_ms) : '-';
        const timestamp = formatTimestamp(node.timestamp);

        return {
            index: index + 1,
            node,
            status,
            color,
            icon,
            summary,
            duration,
            timestamp,
        };
    });
}

// ========== Top Sources提取 ==========

export function extractTopSources(ragRuns: RagRun[], limit: number = 5): string[] {
    const sourceCountMap = new Map<string, number>();

    ragRuns.forEach((run) => {
        if (!run.top_sources) return;
        run.top_sources.forEach((sourceId) => {
            sourceCountMap.set(sourceId, (sourceCountMap.get(sourceId) || 0) + 1);
        });
    });

    return Array.from(sourceCountMap.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, limit)
        .map(([sourceId]) => sourceId);
}

// ========== 错误汇总 ==========

export function summarizeErrors(nodes: ExecutionLogNode[]): ErrorSummaryItem[] {
    return nodes
        .filter((node) => node.error)
        .map((node) => ({
            node: node.node,
            errorType: node.error!.type || 'UnknownError',
            errorMessage: node.error!.message || 'No message',
            timestamp: formatTimestamp(node.timestamp),
        }));
}

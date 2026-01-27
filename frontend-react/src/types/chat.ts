import type { JsonValue } from "./api";

export type AgentType =
  | "graph_agent"
  | "hybrid_agent"
  | "naive_rag_agent"
  | "deep_research_agent"
  | "fusion_agent";

export interface ChatRequest {
  message: string;
  user_id: string;
  session_id: string;
  kb_prefix?: string;
  debug?: boolean;
  incognito?: boolean;
  watchlist_auto_capture?: boolean | null;
  use_deeper_tool?: boolean;
  show_thinking?: boolean;
}

export interface KnowledgeGraphData {
  nodes: Array<Record<string, JsonValue>>;
  links: Array<Record<string, JsonValue>>;
}

export interface ChatResponse {
  answer: string;
  execution_log?: Array<Record<string, JsonValue>>;
  kg_data?: KnowledgeGraphData;
  reference?: Record<string, JsonValue>;
  iterations?: Array<Record<string, JsonValue>>;
  raw_thinking?: string;
  execution_logs?: Array<JsonValue>;
  rag_runs?: Array<JsonValue>;
  route_decision?: JsonValue;
  watchlist_auto_capture?: {
    added?: Array<Record<string, JsonValue>>;
  };
}

export type StreamEvent =
  | { status: "start"; request_id?: string }
  | { status: "token"; content: string }
  | { status: "execution_log"; content: JsonValue }
  | { status: "execution_logs"; content: JsonValue }
  | {
    status: "progress";
    content: {
      stage: string;
      completed: number;
      total: number;
      error: string | null;
      agent_type?: string;
      retrieval_count?: number | null;
    };
  }
  | { status: "done"; request_id?: string }
  | { status: "error"; message?: string }
  | { status: string;[k: string]: JsonValue | undefined };

export interface DebugData {
  request_id: string;
  user_id: string;
  session_id: string;
  timestamp: string;
  execution_log: Array<JsonValue>;
  progress_events: Array<JsonValue>;
  error_events: Array<{ message: string; timestamp: string }>;
  route_decision: JsonValue | null;
  rag_runs: Array<JsonValue>;
  episodic_memory?: Array<JsonValue>;
  conversation_summary?: JsonValue | null;
  combined_context?: {
    text?: string;
    total_chars?: number;
    max_chars?: number;
    truncated?: boolean;
    has_enrichment?: boolean;
  } | null;
  trace: Array<JsonValue>;
  kg_data: JsonValue | null;
  performance_metrics?: {
    total_duration_ms: number;
    retrieval_duration_ms: number;
    generation_duration_ms: number;
    routing_duration_ms: number;
    node_count: number;
    error_count: number;
  };
}

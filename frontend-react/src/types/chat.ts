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
  agent_type: AgentType;
  use_deeper_tool?: boolean;
  show_thinking?: boolean;
  use_chain_exploration?: boolean;
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
}

export type StreamEvent =
  | { status: "start" }
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
  | { status: "done" }
  | { status: "error"; message?: string }
  | { status: string; [k: string]: JsonValue | undefined };

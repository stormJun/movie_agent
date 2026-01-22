import type { JsonValue } from "./api";

export type KnowledgeGraphNode = Record<string, JsonValue>;
export type KnowledgeGraphLink = Record<string, JsonValue>;

export interface KnowledgeGraphResponse {
  nodes: KnowledgeGraphNode[];
  links: KnowledgeGraphLink[];
  error?: string;
  [k: string]: JsonValue | undefined;
}

export interface KgReasoningRequest {
  reasoning_type: string;
  entity_a: string;
  entity_b?: string;
  max_depth?: number;
  algorithm?: string;
}


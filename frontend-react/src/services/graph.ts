import { http } from "./http";
import type { KnowledgeGraphResponse, KgReasoningRequest } from "../types/graph";

export async function getKnowledgeGraph(params: {
  limit?: number;
  query?: string;
}): Promise<KnowledgeGraphResponse> {
  const response = await http.get<KnowledgeGraphResponse>("/api/v1/knowledge_graph", {
    params,
  });
  return response.data;
}

export async function getKnowledgeGraphFromMessage(params: {
  message?: string;
  query?: string;
}): Promise<KnowledgeGraphResponse> {
  const response = await http.get<KnowledgeGraphResponse>("/api/v1/knowledge_graph_from_message", {
    params,
  });
  return response.data;
}

export async function kgReasoning(
  payload: KgReasoningRequest,
): Promise<Record<string, unknown>> {
  const response = await http.post<Record<string, unknown>>("/api/v1/kg_reasoning", payload);
  return response.data;
}

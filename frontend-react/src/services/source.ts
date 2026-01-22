import { http } from "./http";
import type { ChunksResponse, SourceResponse } from "../types/source";

export async function getChunks(params: {
  limit?: number;
  offset?: number;
}): Promise<ChunksResponse> {
  const resp = await http.get<ChunksResponse>("/api/v1/chunks", { params });
  return resp.data;
}

export async function getSourceContent(sourceId: string): Promise<SourceResponse> {
  const resp = await http.post<SourceResponse>("/api/v1/source", { source_id: sourceId });
  return resp.data;
}

export async function getSourceInfoBatch(
  sourceIds: string[],
): Promise<Record<string, { file_name?: string }>> {
  const resp = await http.post<Record<string, { file_name?: string }>>(
    "/api/v1/source_info_batch",
    { source_ids: sourceIds },
  );
  return resp.data;
}

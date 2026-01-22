import type { JsonValue } from "./api";

export interface Chunk {
  id: string;
  fileName?: string;
  text?: string;
  [k: string]: JsonValue | undefined;
}

export interface ChunksResponse {
  chunks: Chunk[];
  total?: number;
  error?: string;
}

export interface SourceRequest {
  source_id: string;
}

export interface SourceResponse {
  content: string;
}


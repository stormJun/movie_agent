import type { JsonValue } from "./api";

export interface EntitySearchFilter {
  term?: string;
  type?: string;
  limit?: number;
}

export interface EntityData {
  id: string;
  name: string;
  type: string;
  description?: string;
  properties?: Record<string, JsonValue>;
}

export interface EntityUpdateData {
  id: string;
  name?: string;
  type?: string;
  description?: string;
  properties?: Record<string, JsonValue>;
}

export interface RelationSearchFilter {
  source?: string;
  target?: string;
  type?: string;
  limit?: number;
}

export interface RelationData {
  source: string;
  type: string;
  target: string;
  description?: string;
  weight?: number;
  properties?: Record<string, JsonValue>;
}

export interface RelationUpdateData {
  source: string;
  original_type: string;
  target: string;
  new_type?: string;
  description?: string;
  weight?: number;
  properties?: Record<string, JsonValue>;
}


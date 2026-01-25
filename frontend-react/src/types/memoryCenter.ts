export interface MemoryDashboardResponse {
  summary: {
    content: string;
    updated_at: string | null;
  };
  taste_profile: Array<{
    id: string;
    tag: string;
    category?: string | null;
    confidence?: number;
  }>;
  watchlist?: Array<{
    id: string;
    title: string;
    year?: number | null;
    status?: "to_watch" | "watched" | "dismissed";
    created_at?: string | null;
    updated_at?: string | null;
    deleted_at?: string | null;
    source?: string | null;
    capture_trigger?: string | null;
    capture_origin?: string | null;
    capture_evidence?: string | null;
    conversation_id?: string | null;
    user_message_id?: string | null;
    assistant_message_id?: string | null;
    metadata?: Record<string, any>;
  }>;
  stats: {
    total_memories: number;
    watchlist_count: number;
  };
}

export type WatchlistStatus = "to_watch" | "watched" | "dismissed";

export interface WatchlistItemDto {
  id: string;
  title: string;
  year?: number | null;
  status?: WatchlistStatus;
  created_at?: string | null;
  updated_at?: string | null;
  deleted_at?: string | null;
  source?: string | null;
  capture_trigger?: string | null;
  capture_origin?: string | null;
  capture_evidence?: string | null;
  conversation_id?: string | null;
  user_message_id?: string | null;
  assistant_message_id?: string | null;
  metadata?: Record<string, any>;
}

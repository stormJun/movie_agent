import { http } from "./http";
import type { MemoryDashboardResponse, WatchlistItemDto, WatchlistStatus } from "../types/memoryCenter";

export async function getMemoryDashboard(params: {
  conversation_id: string;
  user_id: string;
}): Promise<MemoryDashboardResponse> {
  const resp = await http.get<MemoryDashboardResponse>("/api/v1/memory/dashboard", { params });
  return resp.data;
}

export async function deleteMemoryItem(params: {
  memory_id: string;
  user_id: string;
}): Promise<void> {
  await http.delete(`/api/v1/memory/items/${encodeURIComponent(params.memory_id)}`, {
    params: { user_id: params.user_id },
  });
}

export async function listWatchlist(params: {
  user_id: string;
  status?: WatchlistStatus;
  query?: string;
  include_deleted?: boolean;
  only_deleted?: boolean;
  limit?: number;
  offset?: number;
}): Promise<WatchlistItemDto[]> {
  const resp = await http.get<WatchlistItemDto[]>("/api/v1/memory/watchlist", { params });
  return resp.data;
}

export async function addWatchlistItem(body: {
  user_id: string;
  title: string;
  year?: number | null;
  metadata?: Record<string, any> | null;
}): Promise<WatchlistItemDto> {
  const resp = await http.post<WatchlistItemDto>("/api/v1/memory/watchlist", body);
  return resp.data;
}

export async function deleteWatchlistItem(params: {
  user_id: string;
  item_id: string;
}): Promise<void> {
  await http.delete(`/api/v1/memory/watchlist/${encodeURIComponent(params.item_id)}`, {
    params: { user_id: params.user_id },
  });
}

export async function updateWatchlistItem(params: {
  item_id: string;
  user_id: string;
  title?: string | null;
  year?: number | null;
  status?: WatchlistStatus | null;
  metadata?: Record<string, any> | null;
}): Promise<WatchlistItemDto> {
  const resp = await http.patch<WatchlistItemDto>(`/api/v1/memory/watchlist/${encodeURIComponent(params.item_id)}`, {
    user_id: params.user_id,
    title: params.title ?? undefined,
    year: params.year ?? undefined,
    status: params.status ?? undefined,
    metadata: params.metadata ?? undefined,
  });
  return resp.data;
}

export async function restoreWatchlistItem(params: { user_id: string; item_id: string }): Promise<WatchlistItemDto> {
  const resp = await http.post<WatchlistItemDto>(
    `/api/v1/memory/watchlist/${encodeURIComponent(params.item_id)}/restore`,
    null,
    { params: { user_id: params.user_id } },
  );
  return resp.data;
}

export async function dedupMergeWatchlist(params: { user_id: string }): Promise<{ result: Record<string, number> }> {
  const resp = await http.post<{ result: Record<string, number> }>("/api/v1/memory/watchlist/dedup_merge", null, {
    params: { user_id: params.user_id },
  });
  return resp.data;
}

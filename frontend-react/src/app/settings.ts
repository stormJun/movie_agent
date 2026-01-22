const API_BASE_URL_KEY = "graphrag.apiBaseUrl";

export function getApiBaseUrl(): string {
  const saved = localStorage.getItem(API_BASE_URL_KEY);
  if (saved && saved.trim()) return saved.trim();
  // Default to same-origin root (no /api prefix)
  return import.meta.env.VITE_API_BASE_URL || "";
}

export function setApiBaseUrl(value: string): void {
  localStorage.setItem(API_BASE_URL_KEY, value.trim());
}

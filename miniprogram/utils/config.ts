// Default backend port per `scripts/dev.sh` (BACKEND_PORT=8324).
// Use 127.0.0.1 instead of localhost to avoid occasional resolver quirks in devtools.
export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8324';

export function getApiBaseUrl(): string {
  try {
    const v = wx.getStorageSync('API_BASE_URL');
    if (typeof v === 'string' && v.trim()) {
      return v.trim();
    }
  } catch (_e) {}
  return DEFAULT_API_BASE_URL;
}

export function mpApi(path: string): string {
  const base = getApiBaseUrl().replace(/\/+$/, '');
  const p = (path || '').startsWith('/') ? path : `/${path}`;
  return `${base}${p}`;
}

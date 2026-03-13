export function randomId(prefix = ''): string {
  const s = `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}-${Math.random()
    .toString(16)
    .slice(2)}`;
  return prefix ? `${prefix}-${s}` : s;
}


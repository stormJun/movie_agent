import type { StreamEvent } from "../types/chat";
import { getApiBaseUrl } from "../app/settings";

function parseSseFrames(buffer: string): { frames: string[]; rest: string } {
  // SSE 以空行分帧；末尾残留的部分保留在 rest
  const parts = buffer.split("\n\n");
  return { frames: parts.slice(0, -1), rest: parts[parts.length - 1] || "" };
}

function extractDataLines(frame: string): string[] {
  // 只取 data: 行，去掉前缀
  return frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trimStart());
}

export async function postSseJson(
  url: string,
  body: unknown,
  onEvent: (event: StreamEvent) => void,
  options?: { signal?: AbortSignal; baseUrl?: string },
): Promise<void> {
  const requestId = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  const baseUrl = options?.baseUrl ?? getApiBaseUrl();

  console.debug("[SSE] request start", { requestId, url: `${baseUrl}${url}` });

  const response = await fetch(`${baseUrl}${url}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal: options?.signal,
  });

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => "");
    console.error("[SSE] request failed", { requestId, status: response.status, text });
    throw new Error(`SSE request failed: ${response.status} ${text}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let frameCount = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const { frames, rest } = parseSseFrames(buffer);
    buffer = rest;

    for (const frame of frames) {
      const dataLines = extractDataLines(frame);
      for (const data of dataLines) {
        if (!data) continue;
        try {
          const parsed = JSON.parse(data) as StreamEvent;
          frameCount += 1;
          if (frameCount <= 5 || frameCount % 20 === 0) {
            // 只在前几条和每 20 条打印一次，避免刷屏
            console.debug("[SSE] event", { requestId, frameCount, data: parsed });
          }
          onEvent(parsed);
        } catch {
          console.error("[SSE] invalid JSON payload", { requestId, raw: data });
          onEvent({ status: "error", message: "Invalid SSE JSON payload" });
        }
      }
    }
  }

  console.debug("[SSE] request end", { requestId, frames: frameCount });
}

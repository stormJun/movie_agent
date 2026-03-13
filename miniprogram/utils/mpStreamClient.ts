export type MpStreamFrame = {
  type: string;
  content?: any;
  answer?: string;
  response?: any;
  request_id?: string;
  meta?: any;
};

// MiniProgram TS lib doesn't include DOM typings by default.
declare const TextDecoder: any;

type MpStreamHandlers = {
  onFrame?: (frame: MpStreamFrame) => void;
  onError?: (err: any) => void;
  onComplete?: () => void;
};

function parseSseEventsFromBuffer(buffer: string): { events: MpStreamFrame[]; rest: string } {
  const events: MpStreamFrame[] = [];
  let rest = buffer;

  while (true) {
    const idx = rest.indexOf('\n\n');
    if (idx === -1) {
      break;
    }
    const block = rest.slice(0, idx);
    rest = rest.slice(idx + 2);

    const lines = block.split('\n');
    const dataLines: string[] = [];
    for (const line of lines) {
      if (!line || line.startsWith(':')) {
        continue;
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart());
      }
    }
    if (!dataLines.length) {
      continue;
    }

    const dataStr = dataLines.join('\n');
    try {
      const obj = JSON.parse(dataStr);
      if (obj && typeof obj === 'object' && typeof obj.type === 'string') {
        events.push(obj as MpStreamFrame);
      }
    } catch (_e) {
      // Ignore malformed frames (best-effort).
    }
  }

  return { events, rest };
}

export function mpPostSse(
  url: string,
  body: any,
  handlers: MpStreamHandlers,
): { abort: () => void } {
  const decoder = typeof TextDecoder !== 'undefined' ? new TextDecoder('utf-8') : null;
  let buffer = '';

  const reqTask = wx.request({
    url,
    method: 'POST',
    data: body,
    header: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    enableChunked: true,
    dataType: 'ArrayBuffer',
    responseType: 'arraybuffer',
    success: (_res: any) => {
      // Stream response is handled in onChunkReceived.
    },
    fail: (err: any) => {
      handlers.onError?.(err);
    },
    complete: () => {
      handlers.onComplete?.();
    },
  });

  reqTask.onChunkReceived((res: any) => {
    try {
      const ab = res?.data as ArrayBuffer | undefined;
      if (!ab) {
        return;
      }
      let chunkText = '';
      if (decoder) {
        chunkText = decoder.decode(new Uint8Array(ab), { stream: true } as any);
      } else {
        const bytes = new Uint8Array(ab);
        chunkText = String.fromCharCode(...Array.from(bytes));
      }

      if (!chunkText) {
        return;
      }

      buffer += chunkText;
      const parsed = parseSseEventsFromBuffer(buffer);
      buffer = parsed.rest;

      for (const ev of parsed.events) {
        handlers.onFrame?.(ev);
      }
    } catch (err) {
      handlers.onError?.(err);
    }
  });

  return {
    abort: () => {
      try {
        reqTask.abort();
      } catch (_e) {}
    },
  };
}

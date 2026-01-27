import { http } from "./http";
import type { ChatRequest, ChatResponse, DebugData, StreamEvent } from "../types/chat";
import { postSseJson } from "../utils/sse";

export async function chat(request: ChatRequest): Promise<ChatResponse> {
  // 普通（非流式）聊天请求，直接走 Axios 封装
  console.debug("[chat] POST /api/v1/chat", { debug: request.debug });
  const response = await http.post<ChatResponse>("/api/v1/chat", request);
  return response.data;
}

export async function chatStream(
  request: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  options?: { signal?: AbortSignal },
): Promise<void> {
  // 流式聊天：通过 SSE 把事件推给前端状态机
  console.debug("[chatStream] start SSE /api/v1/chat/stream", {
    debug: request.debug,
    session_id: request.session_id,
  });
  await postSseJson("/api/v1/chat/stream", request, onEvent, options);
}

export async function clearChat(userId: string, sessionId: string, kbPrefix?: string): Promise<void> {
  await http.post("/api/v1/clear", { user_id: userId, session_id: sessionId, kb_prefix: kbPrefix });
}

export async function getExampleQuestions(): Promise<string[]> {
  const resp = await http.get<string[]>("/api/v1/examples");
  return resp.data;
}

export async function getDebugData(params: {
  request_id: string;
  user_id: string;
  session_id?: string;
}): Promise<DebugData> {
  const { request_id, user_id, session_id } = params;
  const resp = await http.get<DebugData>(`/api/v1/debug/${request_id}`, {
    params: { user_id, session_id },
  });
  return resp.data;
}

/** 历史会话项 */
export interface ConversationItem {
  id: string;
  session_id: string;
  created_at: string;
  updated_at: string;
  first_message?: string;
}

/** 列出用户的历史会话列表 */
export async function listConversations(userId: string, limit = 50): Promise<ConversationItem[]> {
  const resp = await http.get<ConversationItem[]>("/api/v1/conversations", {
    params: { user_id: userId, limit },
  });
  return resp.data;
}

/** 历史消息项 */
export interface MessageItem {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
  citations?: Record<string, unknown>;
  debug?: Record<string, unknown>;
}

/** 获取指定会话的历史消息 */
export async function getMessages(
  userId: string,
  sessionId: string,
  limit = 100
): Promise<MessageItem[]> {
  // 先获取 conversation_id，然后获取消息
  // 这里简化处理：直接调用 conversations 接口找到对应的 conversation
  const conversations = await listConversations(userId);
  const conv = conversations.find((c) => c.session_id === sessionId);
  if (!conv) return [];

  const resp = await http.get<MessageItem[]>("/api/v1/messages", {
    params: { conversation_id: conv.id, limit },
  });
  return resp.data;
}

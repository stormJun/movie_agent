export interface FeedbackRequest {
  message_id: string;
  query: string;
  is_positive: boolean;
  thread_id: string;
  // Langfuse trace id (aka request_id from /chat/stream). Optional for backends
  // that don't support tracing.
  request_id?: string;
  agent_type?: string;
}

export interface FeedbackResponse {
  status: string;
  action: string;
}

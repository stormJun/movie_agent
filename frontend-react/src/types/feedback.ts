export interface FeedbackRequest {
  message_id: string;
  query: string;
  is_positive: boolean;
  thread_id: string;
  agent_type?: string;
}

export interface FeedbackResponse {
  status: string;
  action: string;
}


import { http } from "./http";
import type { FeedbackRequest, FeedbackResponse } from "../types/feedback";

export async function sendFeedback(payload: FeedbackRequest): Promise<FeedbackResponse> {
  const resp = await http.post<FeedbackResponse>("/api/v1/feedback", payload);
  return resp.data;
}

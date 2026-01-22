import axios from "axios";

import { getApiBaseUrl } from "../app/settings";

export const http = axios.create({
  timeout: 300_000,  // 5分钟超时，适配深度研究 Agent
  headers: { "Content-Type": "application/json" },
});

http.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl();
  return config;
});

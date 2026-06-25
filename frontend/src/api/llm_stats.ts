import { apiRequest } from "./client";
import type { LLMStatsResponse } from "./types";

/** OBS-LLM-01: текущая статистика latency LLM вызовов. */
export function getLLMStats(): Promise<LLMStatsResponse> {
  return apiRequest("/observability/llm-stats");
}

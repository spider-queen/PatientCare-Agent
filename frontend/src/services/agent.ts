import type { AgentQueryRequest, AgentQueryResponse } from "../types/agent";
import { apiFetch } from "./api";

export function queryAgent(payload: AgentQueryRequest) {
  return apiFetch<AgentQueryResponse>("/api/agent/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}


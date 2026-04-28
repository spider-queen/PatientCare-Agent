import type { AgentQueryRequest, AgentQueryResponse } from "../types/agent";
import { apiFetch } from "./api";

export function queryAgent(payload: AgentQueryRequest) {
  return apiFetch<AgentQueryResponse>("/api/agent/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Agent-Demo-Context": "true",
      "X-Agent-Actor-Role": "clinician",
      "X-Agent-Access-Purpose": "follow_up_care",
      "X-Agent-Operator-Id": "demo-clinician",
      "X-Agent-Tenant-Id": "demo-tenant"
    },
    body: JSON.stringify(payload)
  });
}

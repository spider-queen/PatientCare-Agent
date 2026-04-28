import type { AgentOpsOverviewResponse, PatientOverviewResponse } from "../types/dashboard";
import { apiFetch } from "./api";

export function getPatientOverview(patientCode: string) {
  const params = new URLSearchParams({ patient_code: patientCode });
  return apiFetch<PatientOverviewResponse>(`/api/dashboard/patient-overview?${params.toString()}`);
}

export function getAgentOpsOverview() {
  return apiFetch<AgentOpsOverviewResponse>("/api/dashboard/agent-ops");
}

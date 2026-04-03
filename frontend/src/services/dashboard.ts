import type { PatientOverviewResponse } from "../types/dashboard";
import { apiFetch } from "./api";

export function getPatientOverview(patientCode: string) {
  const params = new URLSearchParams({ patient_code: patientCode });
  return apiFetch<PatientOverviewResponse>(`/api/dashboard/patient-overview?${params.toString()}`);
}


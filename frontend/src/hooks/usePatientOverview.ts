import { useQuery } from "@tanstack/react-query";

import { getPatientOverview } from "../services/dashboard";

export function usePatientOverview(patientCode: string) {
  return useQuery({
    queryKey: ["patient-overview", patientCode],
    queryFn: () => getPatientOverview(patientCode),
    enabled: Boolean(patientCode)
  });
}


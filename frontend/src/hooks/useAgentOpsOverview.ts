import { useQuery } from "@tanstack/react-query";

import { getAgentOpsOverview } from "../services/dashboard";

export function useAgentOpsOverview() {
  return useQuery({
    queryKey: ["agent-ops-overview"],
    queryFn: () => getAgentOpsOverview()
  });
}

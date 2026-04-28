export type AgentImageInput = {
  image_base64: string;
  mime_type: string;
};

export type AgentQueryRequest = {
  query: string;
  patient_code?: string | null;
  identity_verification?: {
    phone?: string;
    id_number?: string;
  } | null;
  images: AgentImageInput[];
  debug_planner: boolean;
  force_full_agent?: boolean;
};

export type AgentToolOutput = {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
};

export type AgentQueryResponse = {
  answer: string;
  tool_outputs: AgentToolOutput[];
  intent?: string | null;
  intent_confidence?: number | null;
  route_type?: string | null;
  route_reason?: string | null;
  cache_hit?: boolean | null;
  evidence?: Record<string, unknown>[];
  risk_level?: string | null;
  recommended_action?: string | null;
  runtime_metrics?: Record<string, unknown> | null;
  planner_debug?: Record<string, unknown> | null;
  run_id?: string | null;
  memory_refresh_scheduled?: boolean | null;
  execution_trace?: Record<string, unknown> | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  imageUrl?: string;
  toolOutputs?: AgentToolOutput[];
  intent?: string | null;
  intentConfidence?: number | null;
  routeType?: string | null;
  routeReason?: string | null;
  cacheHit?: boolean | null;
  evidence?: Record<string, unknown>[];
  riskLevel?: string | null;
  recommendedAction?: string | null;
  status?: "pending" | "error" | "done";
};

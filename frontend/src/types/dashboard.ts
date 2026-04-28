export type Patient = {
  id: number;
  patient_code: string;
  full_name: string;
  gender?: string | null;
  date_of_birth?: string | null;
  phone?: string | null;
  id_number?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
};

export type VisitRecord = {
  id: number;
  visit_code: string;
  visit_type: string;
  department?: string | null;
  physician_name?: string | null;
  visit_time: string;
  summary?: string | null;
  notes?: string | null;
};

export type UserProfile = {
  profile_summary?: string | null;
  communication_style?: string | null;
  preferred_topics?: string | null;
  stable_preferences?: string | null;
  source_summary?: string | null;
};

export type MemoryPreference = {
  preferred_name?: string | null;
  response_style?: string | null;
  response_length?: string | null;
  preferred_language?: string | null;
  focus_topics?: string | null;
  additional_preferences?: string | null;
};

export type MemoryEvent = {
  id: number;
  event_type: string;
  event_time: string;
  title: string;
  summary?: string | null;
  source_type: string;
};

export type PatientOverviewResponse = {
  patient: Patient;
  latest_visit?: VisitRecord | null;
  user_profile?: UserProfile | null;
  memory_preference?: MemoryPreference | null;
  recent_memory_events: MemoryEvent[];
};

export type AgentStageTimingSummary = {
  patient_resolution_ms: number;
  memory_context_ms: number;
  agent_execution_ms: number;
  persistence_ms: number;
};

export type AgentOpsSummary = {
  window_size: number;
  success_rate: number;
  avg_total_duration_ms: number;
  p50_total_duration_ms: number;
  p95_total_duration_ms: number;
  fast_path_hit_rate: number;
  high_frequency_acceleration_rate: number;
  adaptive_route_hit_rate: number;
  semantic_cache_hit_rate: number;
  evidence_cache_invalid_rate: number;
  agent_loop_fallback_rate: number;
  avg_latency_saved_ms: number;
  low_confidence_intent_rate: number;
  risk_guard_block_count: number;
  identity_verification_rate: number;
  memory_fallback_rate: number;
  memory_refresh_rate: number;
  tool_success_rate: number;
  privacy_block_rate: number;
  risk_escalation_count: number;
  risk_escalation_rate: number;
  smalltalk_rate: number;
  out_of_domain_rate: number;
  fast_path_avg_duration_ms: number;
  full_agent_avg_duration_ms: number;
  avg_tool_count: number;
  stage_breakdown_avg_ms: AgentStageTimingSummary;
};

export type AgentRunMetric = {
  run_id: string;
  patient_code?: string | null;
  intent: string;
  status: string;
  execution_mode: string;
  route_type?: string | null;
  route_reason?: string | null;
  intent_confidence: number;
  cache_hit: boolean;
  latency_saved_ms: number;
  fast_path: boolean;
  identity_verified: boolean;
  used_memory_fallback: boolean;
  tool_count: number;
  tool_blocked_count: number;
  risk_level?: string | null;
  total_duration_ms: number;
  created_at: string;
};

export type AgentOpsOverviewResponse = {
  summary: AgentOpsSummary;
  recent_runs: AgentRunMetric[];
};

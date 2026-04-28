from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.memory import MemoryEventRead, UserProfileRead
from app.schemas.memory_preference import MemoryPreferenceRead
from app.schemas.patient import PatientRead
from app.schemas.visit_record import VisitRecordRead


class PatientOverviewResponse(BaseModel):
    patient: PatientRead
    latest_visit: Optional[VisitRecordRead] = None
    user_profile: Optional[UserProfileRead] = None
    memory_preference: Optional[MemoryPreferenceRead] = None
    recent_memory_events: list[MemoryEventRead]


class AgentStageTimingSummary(BaseModel):
    patient_resolution_ms: int
    memory_context_ms: int
    agent_execution_ms: int
    persistence_ms: int


class AgentOpsSummary(BaseModel):
    window_size: int
    success_rate: float
    avg_total_duration_ms: int
    p50_total_duration_ms: int
    p95_total_duration_ms: int
    fast_path_hit_rate: float
    high_frequency_acceleration_rate: float
    adaptive_route_hit_rate: float
    semantic_cache_hit_rate: float
    evidence_cache_invalid_rate: float
    agent_loop_fallback_rate: float
    avg_latency_saved_ms: int
    low_confidence_intent_rate: float
    risk_guard_block_count: int
    identity_verification_rate: float
    memory_fallback_rate: float
    memory_refresh_rate: float
    tool_success_rate: float
    privacy_block_rate: float
    risk_escalation_count: int
    risk_escalation_rate: float
    smalltalk_rate: float
    out_of_domain_rate: float
    fast_path_avg_duration_ms: int
    full_agent_avg_duration_ms: int
    avg_tool_count: int
    stage_breakdown_avg_ms: AgentStageTimingSummary


class AgentRunMetricRead(BaseModel):
    run_id: str
    patient_code: Optional[str] = None
    intent: str
    status: str
    execution_mode: str
    route_type: Optional[str] = None
    route_reason: Optional[str] = None
    intent_confidence: float = 0
    cache_hit: bool = False
    latency_saved_ms: int = 0
    fast_path: bool
    identity_verified: bool
    used_memory_fallback: bool
    tool_count: int
    tool_blocked_count: int = 0
    risk_level: Optional[str] = None
    total_duration_ms: int
    created_at: datetime


class AgentOpsOverviewResponse(BaseModel):
    summary: AgentOpsSummary
    recent_runs: list[AgentRunMetricRead]

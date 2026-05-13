
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    id_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    medical_cases: Mapped[list["MedicalCase"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    visit_records: Mapped[list["VisitRecord"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    follow_up_plans: Mapped[list["FollowUpPlan"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    medication_reminders: Mapped[list["MedicationReminder"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    risk_events: Mapped[list["RiskEvent"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    semantic_evidence_caches: Mapped[list["SemanticEvidenceCache"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    memory_preference: Mapped[Optional["MemoryPreference"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    user_profile: Mapped[Optional["UserProfile"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    memory_events: Mapped[list["MemoryEvent"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    conversation_memories: Mapped[list["ConversationMemory"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class MedicalCase(Base):
    __tablename__ = "medical_cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    case_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    diagnosis: Mapped[str] = mapped_column(String(255))
    chief_complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    present_illness: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    past_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attending_physician: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["Patient"] = relationship(back_populates="medical_cases")


class VisitRecord(Base):
    __tablename__ = "visit_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    visit_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    visit_type: Mapped[str] = mapped_column(String(32))
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    physician_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    visit_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["Patient"] = relationship(back_populates="visit_records")


class FollowUpPlan(Base):
    __tablename__ = "follow_up_plans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    goal: Mapped[str] = mapped_column(String(255))
    source_visit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("visit_records.id"), nullable=True, index=True
    )
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    doctor_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["Patient"] = relationship(back_populates="follow_up_plans")


class MedicationReminder(Base):
    __tablename__ = "medication_reminders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    medication_name: Mapped[str] = mapped_column(String(255))
    dosage: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_case_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medical_cases.id"), nullable=True, index=True
    )
    source_visit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("visit_records.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["Patient"] = relationship(back_populates="medication_reminders")


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(32), index=True)
    risk_category: Mapped[str] = mapped_column(String(64), index=True)
    trigger_terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    patient: Mapped[Optional["Patient"]] = relationship(back_populates="risk_events")


class MemoryPreference(Base):
    __tablename__ = "memory_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), unique=True, index=True
    )
    preferred_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    response_style: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    response_length: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    preferred_language: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    focus_topics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    additional_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["Patient"] = relationship(back_populates="memory_preference")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"), unique=True, index=True
    )
    profile_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    communication_style: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    preferred_topics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stable_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["Patient"] = relationship(back_populates="user_profile")


class MemoryEvent(Base):
    __tablename__ = "memory_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["Patient"] = relationship(back_populates="memory_events")


class ConversationMemory(Base):
    __tablename__ = "conversation_memories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    multimodal_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    patient: Mapped["Patient"] = relationship(back_populates="conversation_memories")


class AgentRunMetric(Base):
    __tablename__ = "agent_run_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    patient_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    intent: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    execution_mode: Mapped[str] = mapped_column(String(32), index=True)
    route_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    route_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    access_purpose: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    operator_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    is_demo_context: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cache_match_strategy: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    cache_similarity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    intent_confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_saved_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fallback_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fast_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    used_relevant_events: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_memory_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    memory_refresh_scheduled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    planner_candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_blocked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fallback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    patient_resolution_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_context_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agent_execution_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    persistence_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )


class SemanticEvidenceCache(Base):
    __tablename__ = "semantic_evidence_caches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    actor_role: Mapped[str] = mapped_column(String(32), index=True)
    access_purpose: Mapped[str] = mapped_column(String(64), index=True)
    intent: Mapped[str] = mapped_column(String(64), index=True)
    normalized_query: Mapped[str] = mapped_column(Text)
    query_terms: Mapped[str] = mapped_column(Text)
    query_embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128), index=True)
    tool_arguments: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    source_version: Mapped[str] = mapped_column(Text)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    patient: Mapped["Patient"] = relationship(back_populates="semantic_evidence_caches")

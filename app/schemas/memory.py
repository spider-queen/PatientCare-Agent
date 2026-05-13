
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BusinessMemoryExtractRequest(BaseModel):
    patient_id: Optional[int] = None
    patient_code: Optional[str] = None


class ConversationMemoryExtractRequest(BaseModel):
    patient_id: int
    recent_limit: int = Field(default=10, ge=1, le=50)


class ConversationMemoryCreate(BaseModel):
    patient_id: int
    session_id: str
    role: str
    content: str
    multimodal_payload: Optional[str] = None


class ConversationMemoryRead(BaseModel):
    id: int
    patient_id: int
    session_id: str
    role: str
    content: str
    multimodal_payload: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryEventRead(BaseModel):
    id: int
    patient_id: int
    event_type: str
    event_time: datetime
    title: str
    summary: Optional[str] = None
    source_type: str
    source_id: Optional[str] = None

    model_config = {"from_attributes": True}


class MemoryEventSearchRequest(BaseModel):
    patient_id: Optional[int] = None
    patient_code: Optional[str] = None
    query: str
    top_n: int = Field(default=5, ge=1, le=20)


class MemoryEventSearchItem(MemoryEventRead):
    retrieval_score: float
    retrieval_sources: list[str]
    retrieval_label: str
    matched_by_keyword: bool
    matched_by_vector: bool
    keyword_score: float
    vector_score: float


class MemoryEventSearchResponse(BaseModel):
    patient_id: int
    query: str
    top_n: int
    results: list[MemoryEventSearchItem]


class UserProfileRead(BaseModel):
    id: int
    patient_id: int
    profile_summary: Optional[str] = None
    communication_style: Optional[str] = None
    preferred_topics: Optional[str] = None
    stable_preferences: Optional[str] = None
    source_summary: Optional[str] = None
    refreshed_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BusinessMemoryExtractResponse(BaseModel):
    patient_id: int
    event_count: int
    memory_events: list[MemoryEventRead]


class ConversationMemoryExtractResponse(BaseModel):
    patient_id: int
    event_count: int
    profile_updated: bool
    memory_events: list[MemoryEventRead]
    user_profile: Optional[UserProfileRead] = None

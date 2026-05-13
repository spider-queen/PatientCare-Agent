
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MemoryPreferenceBase(BaseModel):
    preferred_name: Optional[str] = None
    response_style: Optional[str] = None
    response_length: Optional[str] = None
    preferred_language: Optional[str] = None
    focus_topics: Optional[str] = None
    additional_preferences: Optional[str] = None


class MemoryPreferenceUpsert(MemoryPreferenceBase):
    patient_id: int


class MemoryPreferenceRead(MemoryPreferenceBase):
    id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

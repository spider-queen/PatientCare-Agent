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


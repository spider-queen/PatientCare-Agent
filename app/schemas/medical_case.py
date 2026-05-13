
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MedicalCaseBase(BaseModel):
    patient_id: int
    case_code: str
    diagnosis: str
    chief_complaint: Optional[str] = None
    present_illness: Optional[str] = None
    past_history: Optional[str] = None
    treatment_plan: Optional[str] = None
    attending_physician: Optional[str] = None
    recorded_at: Optional[datetime] = None


class MedicalCaseCreate(MedicalCaseBase):
    pass


class MedicalCaseUpdate(BaseModel):
    diagnosis: Optional[str] = None
    chief_complaint: Optional[str] = None
    present_illness: Optional[str] = None
    past_history: Optional[str] = None
    treatment_plan: Optional[str] = None
    attending_physician: Optional[str] = None
    recorded_at: Optional[datetime] = None


class MedicalCaseRead(MedicalCaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime

# 作者：小红书@人间清醒的李某人

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class VisitRecordBase(BaseModel):
    patient_id: int
    visit_code: str
    visit_type: str
    department: Optional[str] = None
    physician_name: Optional[str] = None
    visit_time: Optional[datetime] = None
    summary: Optional[str] = None
    notes: Optional[str] = None


class VisitRecordCreate(VisitRecordBase):
    pass


class VisitRecordUpdate(BaseModel):
    visit_type: Optional[str] = None
    department: Optional[str] = None
    physician_name: Optional[str] = None
    visit_time: Optional[datetime] = None
    summary: Optional[str] = None
    notes: Optional[str] = None


class VisitRecordRead(VisitRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_time: datetime
    created_at: datetime
    updated_at: datetime

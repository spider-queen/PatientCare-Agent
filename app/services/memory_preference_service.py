# 作者：小红书@人间清醒的李某人

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MemoryPreference, Patient
from app.schemas.memory_preference import MemoryPreferenceUpsert


def get_memory_preference_by_patient_id(
    db: Session, patient_id: int
) -> Optional[MemoryPreference]:
    stmt = select(MemoryPreference).where(MemoryPreference.patient_id == patient_id)
    return db.scalar(stmt)


def get_memory_preference_by_patient_code(
    db: Session, patient_code: str
) -> Optional[MemoryPreference]:
    stmt = (
        select(MemoryPreference)
        .join(Patient, Patient.id == MemoryPreference.patient_id)
        .where(Patient.patient_code == patient_code)
    )
    return db.scalar(stmt)


def upsert_memory_preference(
    db: Session, payload: MemoryPreferenceUpsert
) -> MemoryPreference:
    memory_preference = get_memory_preference_by_patient_id(db, payload.patient_id)
    if memory_preference is None:
        memory_preference = MemoryPreference(patient_id=payload.patient_id)

    for field, value in payload.model_dump().items():
        if field == "patient_id":
            continue
        setattr(memory_preference, field, value)

    db.add(memory_preference)
    db.commit()
    db.refresh(memory_preference)
    return memory_preference

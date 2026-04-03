# 作者：小红书@人间清醒的李某人

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MedicalCase, Patient
from app.schemas.medical_case import MedicalCaseCreate, MedicalCaseUpdate


def create_medical_case(db: Session, payload: MedicalCaseCreate) -> MedicalCase:
    medical_case = MedicalCase(**payload.model_dump(exclude_none=True))
    db.add(medical_case)
    db.commit()
    db.refresh(medical_case)
    return medical_case


def get_medical_case_by_id(db: Session, case_id: int) -> Optional[MedicalCase]:
    return db.get(MedicalCase, case_id)


def list_medical_cases(
    db: Session, patient_id: Optional[int] = None
) -> list[MedicalCase]:
    stmt = select(MedicalCase).order_by(MedicalCase.recorded_at.desc())
    if patient_id is not None:
        stmt = stmt.where(MedicalCase.patient_id == patient_id)
    return list(db.scalars(stmt).all())


def update_medical_case(
    db: Session, medical_case: MedicalCase, payload: MedicalCaseUpdate
) -> MedicalCase:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(medical_case, field, value)
    db.add(medical_case)
    db.commit()
    db.refresh(medical_case)
    return medical_case


def patient_exists(db: Session, patient_id: int) -> bool:
    return db.get(Patient, patient_id) is not None

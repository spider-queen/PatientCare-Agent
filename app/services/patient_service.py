
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Patient
from app.schemas.patient import PatientCreate, PatientUpdate


def create_patient(db: Session, payload: PatientCreate) -> Patient:
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def list_patients(db: Session) -> list[Patient]:
    return list(db.scalars(select(Patient).order_by(Patient.id.desc())).all())


def get_patient_by_id(db: Session, patient_id: int) -> Optional[Patient]:
    return db.get(Patient, patient_id)


def get_patient_by_code(db: Session, patient_code: str) -> Optional[Patient]:
    stmt = select(Patient).where(Patient.patient_code == patient_code)
    return db.scalar(stmt)


def get_patient_by_phone(db: Session, phone: str) -> Optional[Patient]:
    stmt = select(Patient).where(Patient.phone == phone)
    return db.scalar(stmt)


def update_patient(db: Session, patient: Patient, payload: PatientUpdate) -> Patient:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient

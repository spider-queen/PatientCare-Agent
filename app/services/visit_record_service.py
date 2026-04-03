# 作者：小红书@人间清醒的李某人

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Patient, VisitRecord
from app.schemas.visit_record import VisitRecordCreate, VisitRecordUpdate


def create_visit_record(db: Session, payload: VisitRecordCreate) -> VisitRecord:
    visit_record = VisitRecord(**payload.model_dump(exclude_none=True))
    db.add(visit_record)
    db.commit()
    db.refresh(visit_record)
    return visit_record


def get_visit_record_by_id(
    db: Session, visit_record_id: int
) -> Optional[VisitRecord]:
    return db.get(VisitRecord, visit_record_id)


def list_visit_records(
    db: Session,
    patient_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> list[VisitRecord]:
    stmt = select(VisitRecord).order_by(VisitRecord.visit_time.desc())
    if patient_id is not None:
        stmt = stmt.where(VisitRecord.patient_id == patient_id)
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def update_visit_record(
    db: Session, visit_record: VisitRecord, payload: VisitRecordUpdate
) -> VisitRecord:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(visit_record, field, value)
    db.add(visit_record)
    db.commit()
    db.refresh(visit_record)
    return visit_record


def patient_exists(db: Session, patient_id: int) -> bool:
    return db.get(Patient, patient_id) is not None

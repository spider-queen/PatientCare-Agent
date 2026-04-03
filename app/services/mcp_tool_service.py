# 作者：小红书@人间清醒的李某人

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import MedicalCase, Patient, VisitRecord
from app.services import identity_service, medical_case_service, patient_service, visit_record_service


def serialize_patient(patient: Patient) -> dict:
    return {
        "id": patient.id,
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
        "gender": patient.gender,
        "date_of_birth": patient.date_of_birth.isoformat()
        if patient.date_of_birth
        else None,
        "phone": patient.phone,
        "id_number": patient.id_number,
        "address": patient.address,
        "emergency_contact_name": patient.emergency_contact_name,
        "emergency_contact_phone": patient.emergency_contact_phone,
        "created_at": patient.created_at.isoformat(),
        "updated_at": patient.updated_at.isoformat(),
    }


def serialize_medical_case(medical_case: MedicalCase) -> dict:
    return {
        "id": medical_case.id,
        "patient_id": medical_case.patient_id,
        "case_code": medical_case.case_code,
        "diagnosis": medical_case.diagnosis,
        "chief_complaint": medical_case.chief_complaint,
        "present_illness": medical_case.present_illness,
        "past_history": medical_case.past_history,
        "treatment_plan": medical_case.treatment_plan,
        "attending_physician": medical_case.attending_physician,
        "recorded_at": medical_case.recorded_at.isoformat(),
        "created_at": medical_case.created_at.isoformat(),
        "updated_at": medical_case.updated_at.isoformat(),
    }


def serialize_visit_record(visit_record: VisitRecord) -> dict:
    return {
        "id": visit_record.id,
        "patient_id": visit_record.patient_id,
        "visit_code": visit_record.visit_code,
        "visit_type": visit_record.visit_type,
        "department": visit_record.department,
        "physician_name": visit_record.physician_name,
        "visit_time": visit_record.visit_time.isoformat(),
        "summary": visit_record.summary,
        "notes": visit_record.notes,
        "created_at": visit_record.created_at.isoformat(),
        "updated_at": visit_record.updated_at.isoformat(),
    }


def get_patient_profile(
    db: Session,
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
) -> dict:
    patient = None
    if patient_id is not None:
        patient = patient_service.get_patient_by_id(db, patient_id)
    elif patient_code is not None:
        patient = patient_service.get_patient_by_code(db, patient_code)

    if patient is None:
        return {"found": False, "reason": "patient not found"}

    return {"found": True, "patient": serialize_patient(patient)}


def get_patient_medical_cases(
    db: Session,
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
) -> dict:
    patient = _resolve_patient(db, patient_id=patient_id, patient_code=patient_code)
    if patient is None:
        return {"found": False, "reason": "patient not found", "medical_cases": []}

    medical_cases = medical_case_service.list_medical_cases(db, patient_id=patient.id)
    return {
        "found": True,
        "patient": identity_service.serialize_patient_identity(patient),
        "medical_cases": [serialize_medical_case(item) for item in medical_cases],
    }


def get_patient_visit_records(
    db: Session,
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    patient = _resolve_patient(db, patient_id=patient_id, patient_code=patient_code)
    if patient is None:
        return {"found": False, "reason": "patient not found", "visit_records": []}

    visit_records = visit_record_service.list_visit_records(
        db,
        patient_id=patient.id,
        limit=limit,
    )
    return {
        "found": True,
        "patient": identity_service.serialize_patient_identity(patient),
        "count": len(visit_records),
        "visit_records": [serialize_visit_record(item) for item in visit_records],
    }


def verify_patient(
    db: Session,
    patient_code: str,
    phone: Optional[str] = None,
    id_number: Optional[str] = None,
) -> dict:
    return identity_service.verify_patient_identity(
        db,
        patient_code=patient_code,
        phone=phone,
        id_number=id_number,
    )


def _resolve_patient(
    db: Session,
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
) -> Optional[Patient]:
    if patient_id is not None:
        return patient_service.get_patient_by_id(db, patient_id)
    if patient_code is not None:
        return patient_service.get_patient_by_code(db, patient_code)
    return None

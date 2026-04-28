# 作者：小红书@人间清醒的李某人

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Patient
from app.services import patient_service


def mask_id_number(id_number: Optional[str]) -> Optional[str]:
    if not id_number:
        return id_number
    if len(id_number) <= 4:
        return "****"
    return f"****{id_number[-4:]}"


def mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return phone
    if len(phone) <= 4:
        return "****"
    return f"****{phone[-4:]}"


def verify_patient_identity(
    db: Session,
    patient_code: str,
    phone: Optional[str] = None,
    id_number: Optional[str] = None,
) -> dict:
    patient = patient_service.get_patient_by_code(db, patient_code)
    if patient is None:
        return {
            "verified": False,
            "reason": "patient not found",
            "patient_code": patient_code,
        }

    if not phone and not id_number:
        return {
            "verified": False,
            "reason": "phone or id_number is required",
            "patient_code": patient_code,
        }

    phone_match = phone is not None and phone == patient.phone
    id_match = id_number is not None and id_number == patient.id_number

    verified = phone_match or id_match
    return {
        "verified": verified,
        "reason": "ok" if verified else "credential mismatch",
        "patient": serialize_patient_identity(patient),
    }


def serialize_patient_identity(patient: Patient) -> dict:
    return {
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
        "gender": patient.gender,
        "phone_masked": mask_phone(patient.phone),
        "id_number_masked": mask_id_number(patient.id_number),
    }


import json
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import (
    FollowUpPlan,
    MedicalCase,
    MedicationReminder,
    Patient,
    RiskEvent,
    VisitRecord,
)
from app.services import identity_service, medical_case_service, patient_service, visit_record_service


def serialize_patient_internal(patient: Patient) -> dict:
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


def serialize_patient_safe(patient: Patient) -> dict:
    return {
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
        "gender": patient.gender,
        "birth_year": patient.date_of_birth.year if patient.date_of_birth else None,
        "phone_masked": identity_service.mask_phone(patient.phone),
        "id_number_masked": identity_service.mask_id_number(patient.id_number),
    }


def serialize_patient(patient: Patient) -> dict:
    return serialize_patient_safe(patient)


def serialize_medical_case(medical_case: MedicalCase) -> dict:
    return {
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


def serialize_follow_up_plan(plan: FollowUpPlan) -> dict:
    return {
        "goal": plan.goal,
        "department": plan.department,
        "doctor_name": plan.doctor_name,
        "scheduled_time": plan.scheduled_time.isoformat() if plan.scheduled_time else None,
        "status": plan.status,
        "notes": plan.notes,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
    }


def serialize_medication_reminder(reminder: MedicationReminder) -> dict:
    return {
        "medication_name": reminder.medication_name,
        "dosage": reminder.dosage,
        "frequency": reminder.frequency,
        "start_time": reminder.start_time.isoformat() if reminder.start_time else None,
        "end_time": reminder.end_time.isoformat() if reminder.end_time else None,
        "notes": reminder.notes,
        "created_at": reminder.created_at.isoformat(),
        "updated_at": reminder.updated_at.isoformat(),
    }


SENSITIVE_OUTPUT_KEYS = {
    "phone",
    "id_number",
    "address",
    "emergency_contact_name",
    "emergency_contact_phone",
}


def sanitize_agent_payload(value):
    if isinstance(value, list):
        return [sanitize_agent_payload(item) for item in value]
    if not isinstance(value, dict):
        return value

    sanitized = {}
    for key, item in value.items():
        if key in {"phone", "emergency_contact_phone"}:
            sanitized[f"{key}_masked"] = identity_service.mask_phone(
                str(item) if item is not None else None
            )
            continue
        if key == "id_number":
            sanitized["id_number_masked"] = identity_service.mask_id_number(
                str(item) if item is not None else None
            )
            continue
        if key in SENSITIVE_OUTPUT_KEYS:
            continue
        sanitized[key] = sanitize_agent_payload(item)
    return sanitized


def sanitize_tool_outputs(tool_outputs: list[dict]) -> list[dict]:
    return [sanitize_agent_payload(item) for item in tool_outputs]


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

    source_version = _patient_source_version(patient)
    return {
        "found": True,
        "count": 1,
        "patient": serialize_patient(patient),
        "source_version": source_version,
        "evidence": [
            {
                "source": "patients",
                "count": 1,
                "patient_code": patient.patient_code,
                "source_version": source_version,
            }
        ],
    }


def get_patient_medical_cases(
    db: Session,
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
) -> dict:
    patient = _resolve_patient(db, patient_id=patient_id, patient_code=patient_code)
    if patient is None:
        return {"found": False, "reason": "patient not found", "medical_cases": []}

    medical_cases = medical_case_service.list_medical_cases(db, patient_id=patient.id)
    source_version = _records_source_version("medical_cases", medical_cases)
    return {
        "found": True,
        "patient": identity_service.serialize_patient_identity(patient),
        "count": len(medical_cases),
        "medical_cases": [serialize_medical_case(item) for item in medical_cases],
        "source_version": source_version,
        "evidence": [
            {
                "source": "medical_cases",
                "count": len(medical_cases),
                "patient_code": patient.patient_code,
                "source_version": source_version,
            }
        ],
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
    source_version = _records_source_version("visit_records", visit_records)
    return {
        "found": True,
        "patient": identity_service.serialize_patient_identity(patient),
        "count": len(visit_records),
        "visit_records": [serialize_visit_record(item) for item in visit_records],
        "source_version": source_version,
        "evidence": [
            {
                "source": "visit_records",
                "count": len(visit_records),
                "patient_code": patient.patient_code,
                "source_version": source_version,
            }
        ],
    }


def get_follow_up_plans(
    db: Session,
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    patient = _resolve_patient(db, patient_id=patient_id, patient_code=patient_code)
    if patient is None:
        return {
            "found": False,
            "count": 0,
            "records": [],
            "evidence": [],
            "error": "patient not found",
        }

    query = db.query(FollowUpPlan).filter(FollowUpPlan.patient_id == patient.id)
    if status:
        query = query.filter(FollowUpPlan.status == status)
    records = query.order_by(FollowUpPlan.scheduled_time.asc(), FollowUpPlan.id.asc()).all()
    source_version = _records_source_version("follow_up_plans", records)
    return {
        "found": bool(records),
        "count": len(records),
        "records": [serialize_follow_up_plan(item) for item in records],
        "source_version": source_version,
        "evidence": [
            {
                "source": "follow_up_plans",
                "count": len(records),
                "patient_code": patient.patient_code,
                "source_version": source_version,
            }
        ],
        "error": None,
    }


def get_medication_reminders(
    db: Session,
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
) -> dict:
    patient = _resolve_patient(db, patient_id=patient_id, patient_code=patient_code)
    if patient is None:
        return {
            "found": False,
            "count": 0,
            "records": [],
            "evidence": [],
            "error": "patient not found",
        }

    records = (
        db.query(MedicationReminder)
        .filter(MedicationReminder.patient_id == patient.id)
        .order_by(MedicationReminder.start_time.asc(), MedicationReminder.id.asc())
        .all()
    )
    source_version = _records_source_version("medication_reminders", records)
    return {
        "found": bool(records),
        "count": len(records),
        "records": [serialize_medication_reminder(item) for item in records],
        "source_version": source_version,
        "evidence": [
            {
                "source": "medication_reminders",
                "count": len(records),
                "patient_code": patient.patient_code,
                "source_version": source_version,
            }
        ],
        "error": None,
    }


def get_patient_evidence_source_version(
    db: Session,
    *,
    tool_name: str,
    patient_id: Optional[int] = None,
    patient_code: Optional[str] = None,
    limit: Optional[int] = None,
    status: Optional[str] = None,
) -> str:
    patient = _resolve_patient(db, patient_id=patient_id, patient_code=patient_code)
    if patient is None:
        return "patient:not_found"
    if tool_name == "get_patient_profile":
        return _patient_source_version(patient)
    if tool_name == "get_patient_medical_cases":
        return _records_source_version(
            "medical_cases",
            medical_case_service.list_medical_cases(db, patient_id=patient.id),
        )
    if tool_name == "get_patient_visit_records":
        return _records_source_version(
            "visit_records",
            visit_record_service.list_visit_records(db, patient_id=patient.id, limit=limit),
        )
    if tool_name == "get_follow_up_plans":
        query = db.query(FollowUpPlan).filter(FollowUpPlan.patient_id == patient.id)
        if status:
            query = query.filter(FollowUpPlan.status == status)
        return _records_source_version(
            "follow_up_plans",
            query.order_by(FollowUpPlan.scheduled_time.asc(), FollowUpPlan.id.asc()).all(),
        )
    if tool_name == "get_medication_reminders":
        return _records_source_version(
            "medication_reminders",
            db.query(MedicationReminder)
            .filter(MedicationReminder.patient_id == patient.id)
            .order_by(MedicationReminder.start_time.asc(), MedicationReminder.id.asc())
            .all(),
        )
    return f"{tool_name}:unsupported"


RISK_RULES = (
    {
        "level": "urgent",
        "category": "cardiopulmonary",
        "terms": ("胸痛", "胸闷", "呼吸困难", "喘不上气", "气促"),
        "action": "建议立即联系急救或前往急诊，并同步联系主管医生。",
    },
    {
        "level": "urgent",
        "category": "allergy",
        "terms": ("严重过敏", "喉头水肿", "全身皮疹", "面唇肿胀"),
        "action": "建议立即停止自行处理，尽快急诊评估过敏风险。",
    },
    {
        "level": "high",
        "category": "medication_change",
        "terms": ("停药", "自行停药", "改药", "加量", "减量", "换药"),
        "action": "不要自行调整用药，请先联系开药医生或随访门诊确认。",
    },
)


def assess_follow_up_risk(query: str) -> dict:
    matched_terms: list[str] = []
    matched_rule = None
    for rule in RISK_RULES:
        terms = [term for term in rule["terms"] if term in query]
        if not terms:
            continue
        matched_terms.extend(terms)
        matched_rule = rule
        break

    if matched_rule is None:
        return {
            "found": False,
            "count": 0,
            "records": [],
            "evidence": [],
            "risk_level": "low",
            "risk_category": "none",
            "trigger_terms": [],
            "recommended_action": "未命中需要升级处理的随访风险规则。",
            "error": None,
        }

    return {
        "found": True,
        "count": 1,
        "records": [
            {
                "risk_level": matched_rule["level"],
                "risk_category": matched_rule["category"],
                "trigger_terms": matched_terms,
                "recommended_action": matched_rule["action"],
            }
        ],
        "evidence": [
            {
                "source": "rule_based_follow_up_risk",
                "trigger_terms": matched_terms,
            }
        ],
        "risk_level": matched_rule["level"],
        "risk_category": matched_rule["category"],
        "trigger_terms": matched_terms,
        "recommended_action": matched_rule["action"],
        "error": None,
    }


def create_risk_event(
    db: Session,
    *,
    run_id: str,
    patient_id: Optional[int],
    risk_result: dict,
) -> RiskEvent | None:
    if risk_result.get("risk_level") not in {"high", "urgent"}:
        return None
    event = RiskEvent(
        run_id=run_id,
        patient_id=patient_id,
        risk_level=risk_result["risk_level"],
        risk_category=risk_result.get("risk_category", "unknown"),
        trigger_terms=json.dumps(risk_result.get("trigger_terms", []), ensure_ascii=False),
        recommended_action=risk_result.get("recommended_action", ""),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _patient_source_version(patient: Patient) -> str:
    updated_at = patient.updated_at.isoformat() if patient.updated_at else "unknown"
    return f"patients:{patient.id}:{updated_at}"


def _records_source_version(source: str, records: list) -> str:
    if not records:
        return f"{source}:empty"
    tokens = []
    for record in records:
        updated_at = getattr(record, "updated_at", None)
        tokens.append(f"{record.id}:{updated_at.isoformat() if updated_at else 'unknown'}")
    return f"{source}:{'|'.join(tokens)}"


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

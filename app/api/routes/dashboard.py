from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dashboard import AgentOpsOverviewResponse, PatientOverviewResponse
from app.schemas.memory import MemoryEventRead, UserProfileRead
from app.schemas.memory_preference import MemoryPreferenceRead
from app.schemas.patient import PatientRead
from app.schemas.visit_record import VisitRecordRead
from app.services import (
    agent_metrics_service,
    memory_preference_service,
    memory_service,
    patient_service,
    visit_record_service,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _get_patient_or_400(
    db: Session,
    patient_id: Optional[int],
    patient_code: Optional[str],
):
    if patient_id is not None:
        patient = patient_service.get_patient_by_id(db, patient_id)
    elif patient_code is not None:
        patient = patient_service.get_patient_by_code(db, patient_code)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id or patient_code is required",
        )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )
    return patient


@router.get(
    "/patient-overview",
    response_model=PatientOverviewResponse,
    summary="查询工作台患者概览",
    description="返回工作台侧栏需要的患者基础信息、最近一次就诊、长期记忆摘要和偏好配置。",
)
def get_patient_overview(
    patient_id: Optional[int] = Query(default=None),
    patient_code: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> PatientOverviewResponse:
    patient = _get_patient_or_400(db, patient_id, patient_code)

    latest_visit = None
    visit_records = visit_record_service.list_visit_records(db, patient_id=patient.id, limit=1)
    if visit_records:
        latest_visit = VisitRecordRead.model_validate(visit_records[0])

    memory_preference = memory_preference_service.get_memory_preference_by_patient_id(
        db, patient.id
    )
    user_profile = memory_service.get_user_profile(db, patient.id)
    recent_memory_events = memory_service.list_memory_events(db, patient.id)[:5]

    return PatientOverviewResponse(
        patient=PatientRead.model_validate(patient),
        latest_visit=latest_visit,
        user_profile=(
            UserProfileRead.model_validate(user_profile)
            if user_profile is not None
            else None
        ),
        memory_preference=(
            MemoryPreferenceRead.model_validate(memory_preference)
            if memory_preference is not None
            else None
        ),
        recent_memory_events=[
            MemoryEventRead.model_validate(event) for event in recent_memory_events
        ],
    )


@router.get(
    "/agent-ops",
    response_model=AgentOpsOverviewResponse,
    summary="Get aggregate agent operations metrics.",
    description=(
        "Returns recent aggregate KPIs for the patient-support agent, including "
        "latency percentiles, fast-path hit rate, verification rate, and recent runs."
    ),
)
def get_agent_ops_overview(
    limit: int = Query(default=50, ge=5, le=500),
    recent_limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> AgentOpsOverviewResponse:
    overview = agent_metrics_service.get_agent_ops_overview(
        db,
        limit=limit,
        recent_limit=recent_limit,
    )
    return AgentOpsOverviewResponse(**overview)

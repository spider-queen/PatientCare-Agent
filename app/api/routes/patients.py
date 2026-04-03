from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.medical_case import MedicalCaseCreate, MedicalCaseRead, MedicalCaseUpdate
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.schemas.visit_record import VisitRecordCreate, VisitRecordRead, VisitRecordUpdate
from app.services import medical_case_service, patient_service, visit_record_service

router = APIRouter()


@router.post(
    "/patients",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Patients"],
    summary="创建患者",
)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)) -> PatientRead:
    existing = patient_service.get_patient_by_code(db, payload.patient_code)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="patient_code already exists",
        )
    return patient_service.create_patient(db, payload)


@router.get(
    "/patients",
    response_model=list[PatientRead],
    tags=["Patients"],
    summary="查询患者列表",
)
def list_patients(db: Session = Depends(get_db)) -> list[PatientRead]:
    return patient_service.list_patients(db)


@router.get(
    "/patients/{patient_id}",
    response_model=PatientRead,
    tags=["Patients"],
    summary="按 ID 查询患者",
)
def get_patient(patient_id: int, db: Session = Depends(get_db)) -> PatientRead:
    patient = patient_service.get_patient_by_id(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="patient not found")
    return patient


@router.put(
    "/patients/{patient_id}",
    response_model=PatientRead,
    tags=["Patients"],
    summary="更新患者信息",
)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
) -> PatientRead:
    patient = patient_service.get_patient_by_id(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="patient not found")
    return patient_service.update_patient(db, patient, payload)


@router.post(
    "/medical-cases",
    response_model=MedicalCaseRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Medical Cases"],
    summary="创建病历",
)
def create_medical_case(
    payload: MedicalCaseCreate, db: Session = Depends(get_db)
) -> MedicalCaseRead:
    if not medical_case_service.patient_exists(db, payload.patient_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="patient not found")
    return medical_case_service.create_medical_case(db, payload)


@router.get(
    "/medical-cases",
    response_model=list[MedicalCaseRead],
    tags=["Medical Cases"],
    summary="查询病历列表",
)
def list_medical_cases(
    patient_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MedicalCaseRead]:
    return medical_case_service.list_medical_cases(db, patient_id=patient_id)


@router.get(
    "/medical-cases/{case_id}",
    response_model=MedicalCaseRead,
    tags=["Medical Cases"],
    summary="按 ID 查询病历",
)
def get_medical_case(case_id: int, db: Session = Depends(get_db)) -> MedicalCaseRead:
    medical_case = medical_case_service.get_medical_case_by_id(db, case_id)
    if medical_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="medical case not found")
    return medical_case


@router.put(
    "/medical-cases/{case_id}",
    response_model=MedicalCaseRead,
    tags=["Medical Cases"],
    summary="更新病历",
)
def update_medical_case(
    case_id: int,
    payload: MedicalCaseUpdate,
    db: Session = Depends(get_db),
) -> MedicalCaseRead:
    medical_case = medical_case_service.get_medical_case_by_id(db, case_id)
    if medical_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="medical case not found")
    return medical_case_service.update_medical_case(db, medical_case, payload)


@router.post(
    "/visit-records",
    response_model=VisitRecordRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Visit Records"],
    summary="创建就诊记录",
)
def create_visit_record(
    payload: VisitRecordCreate, db: Session = Depends(get_db)
) -> VisitRecordRead:
    if not visit_record_service.patient_exists(db, payload.patient_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="patient not found")
    return visit_record_service.create_visit_record(db, payload)


@router.get(
    "/visit-records",
    response_model=list[VisitRecordRead],
    tags=["Visit Records"],
    summary="查询就诊记录列表",
)
def list_visit_records(
    patient_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VisitRecordRead]:
    return visit_record_service.list_visit_records(db, patient_id=patient_id)


@router.get(
    "/visit-records/{visit_record_id}",
    response_model=VisitRecordRead,
    tags=["Visit Records"],
    summary="按 ID 查询就诊记录",
)
def get_visit_record(
    visit_record_id: int,
    db: Session = Depends(get_db),
) -> VisitRecordRead:
    visit_record = visit_record_service.get_visit_record_by_id(db, visit_record_id)
    if visit_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="visit record not found",
        )
    return visit_record


@router.put(
    "/visit-records/{visit_record_id}",
    response_model=VisitRecordRead,
    tags=["Visit Records"],
    summary="更新就诊记录",
)
def update_visit_record(
    visit_record_id: int,
    payload: VisitRecordUpdate,
    db: Session = Depends(get_db),
) -> VisitRecordRead:
    visit_record = visit_record_service.get_visit_record_by_id(db, visit_record_id)
    if visit_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="visit record not found",
        )
    return visit_record_service.update_visit_record(db, visit_record, payload)


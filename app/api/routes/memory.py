from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.memory import (
    BusinessMemoryExtractRequest,
    BusinessMemoryExtractResponse,
    ConversationMemoryCreate,
    ConversationMemoryExtractRequest,
    ConversationMemoryExtractResponse,
    ConversationMemoryRead,
    MemoryEventRead,
    MemoryEventSearchItem,
    MemoryEventSearchRequest,
    MemoryEventSearchResponse,
    UserProfileRead,
)
from app.schemas.memory_preference import MemoryPreferenceRead, MemoryPreferenceUpsert
from app.services import conversation_memory_service, memory_preference_service, memory_service, patient_service

router = APIRouter(tags=["Memory"])


def _build_retrieval_label(retrieval_sources: list[str]) -> str:
    sources = set(retrieval_sources)
    if {"keyword", "vector"}.issubset(sources):
        return "hybrid"
    if "keyword" in sources:
        return "keyword"
    if "vector" in sources:
        return "vector"
    return "recent"


@router.get(
    "/memory/preferences",
    response_model=MemoryPreferenceRead,
    summary="查询长期记忆偏好配置",
)
def get_memory_preference(
    patient_id: Optional[int] = Query(default=None),
    patient_code: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> MemoryPreferenceRead:
    if patient_id is None and patient_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id or patient_code is required",
        )

    memory_preference = None
    if patient_id is not None:
        memory_preference = memory_preference_service.get_memory_preference_by_patient_id(
            db, patient_id
        )
    elif patient_code is not None:
        memory_preference = memory_preference_service.get_memory_preference_by_patient_code(
            db, patient_code
        )

    if memory_preference is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="memory preference not found",
        )
    return memory_preference


@router.put(
    "/memory/preferences",
    response_model=MemoryPreferenceRead,
    summary="创建或更新长期记忆偏好配置",
)
def upsert_memory_preference(
    payload: MemoryPreferenceUpsert,
    db: Session = Depends(get_db),
) -> MemoryPreferenceRead:
    patient = patient_service.get_patient_by_id(db, payload.patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )
    return memory_preference_service.upsert_memory_preference(db, payload)


@router.post(
    "/memory/conversations",
    response_model=ConversationMemoryRead,
    summary="写入短期记忆对话",
)
def create_conversation_memory(
    payload: ConversationMemoryCreate,
    db: Session = Depends(get_db),
) -> ConversationMemoryRead:
    patient = patient_service.get_patient_by_id(db, payload.patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )
    return conversation_memory_service.create_conversation_memory(db, payload)


@router.get(
    "/memory/conversations",
    response_model=list[ConversationMemoryRead],
    summary="查询短期记忆对话",
)
def list_conversation_memories(
    patient_id: int,
    session_id: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=10),
    db: Session = Depends(get_db),
) -> list[ConversationMemoryRead]:
    patient = patient_service.get_patient_by_id(db, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )
    return conversation_memory_service.list_conversation_memories(
        db,
        patient_id=patient_id,
        session_id=session_id,
        limit=limit,
    )


@router.post(
    "/memory/extract/business",
    response_model=BusinessMemoryExtractResponse,
    summary="从业务数据提取长期记忆关键事件",
)
def extract_business_memory(
    payload: BusinessMemoryExtractRequest,
    db: Session = Depends(get_db),
) -> BusinessMemoryExtractResponse:
    patient = memory_service.get_patient(db, payload.patient_id, payload.patient_code)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )

    memory_events = memory_service.refresh_business_memory(
        db=db,
        patient=patient,
    )
    return BusinessMemoryExtractResponse(
        patient_id=patient.id,
        event_count=len(memory_events),
        memory_events=memory_events,
    )


@router.post(
    "/memory/extract/conversation",
    response_model=ConversationMemoryExtractResponse,
    summary="从短期对话提取长期记忆画像与对话事件",
)
def extract_conversation_memory(
    payload: ConversationMemoryExtractRequest,
    db: Session = Depends(get_db),
) -> ConversationMemoryExtractResponse:
    patient = patient_service.get_patient_by_id(db, payload.patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )

    conversation_texts = memory_service.get_conversation_texts_for_extraction(
        db=db,
        patient_id=patient.id,
        limit=payload.recent_limit,
    )

    memory_events, user_profile = memory_service.refresh_conversation_memory(
        db=db,
        patient=patient,
        conversation_texts=conversation_texts,
    )
    return ConversationMemoryExtractResponse(
        patient_id=patient.id,
        event_count=len(memory_events),
        profile_updated=True,
        memory_events=memory_events,
        user_profile=user_profile,
    )


@router.get(
    "/memory/events",
    response_model=list[MemoryEventRead],
    summary="查询长期记忆中的关键事件",
)
def list_memory_events(
    patient_id: int,
    db: Session = Depends(get_db),
) -> list[MemoryEventRead]:
    patient = patient_service.get_patient_by_id(db, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )
    return memory_service.list_memory_events(db, patient_id)


@router.post(
    "/memory/search/events",
    response_model=MemoryEventSearchResponse,
    summary="混合检索长期记忆关键事件",
)
def search_memory_events(
    payload: MemoryEventSearchRequest,
    db: Session = Depends(get_db),
) -> MemoryEventSearchResponse:
    patient = memory_service.get_patient(db, payload.patient_id, payload.patient_code)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )

    results = memory_service.search_memory_events(
        db=db,
        patient_id=patient.id,
        query=payload.query,
        top_n=payload.top_n,
    )
    return MemoryEventSearchResponse(
        patient_id=patient.id,
        query=payload.query,
        top_n=payload.top_n,
        results=[
            MemoryEventSearchItem(
                **MemoryEventRead.model_validate(item["event"]).model_dump(),
                retrieval_score=item["retrieval_score"],
                retrieval_sources=item["retrieval_sources"],
                retrieval_label=_build_retrieval_label(item["retrieval_sources"]),
                matched_by_keyword="keyword" in item["retrieval_sources"],
                matched_by_vector="vector" in item["retrieval_sources"],
                keyword_score=item.get("keyword_score", 0.0),
                vector_score=item.get("vector_score", 0.0),
            )
            for item in results
        ],
    )


@router.get(
    "/memory/profile",
    response_model=UserProfileRead,
    summary="查询长期记忆中的用户画像",
)
def get_user_profile(
    patient_id: int,
    db: Session = Depends(get_db),
) -> UserProfileRead:
    patient = patient_service.get_patient_by_id(db, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="patient not found",
        )
    user_profile = memory_service.get_user_profile(db, patient_id)
    if user_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user profile not found",
        )
    return user_profile


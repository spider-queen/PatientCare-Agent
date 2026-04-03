import json
import logging
import re
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from openai import BadRequestError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm.qwen_client import QwenClient
from app.llm.qwen_mcp_agent import QwenMCPAgent
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse
from app.schemas.memory import ConversationMemoryCreate
from app.services import (
    conversation_memory_service,
    mcp_tool_service,
    memory_service,
    patient_service,
)

router = APIRouter(tags=["Agent"])
logger = logging.getLogger("uvicorn.error")
SHORT_TERM_ROUND_TRIGGER = 5
MESSAGES_PER_ROUND = 2
SHORT_TERM_TRIGGER_MESSAGE_COUNT = SHORT_TERM_ROUND_TRIGGER * MESSAGES_PER_ROUND


def _extract_patient_code_from_query(query: str) -> Optional[str]:
    match = re.search(r"P\d{4,}", query, flags=re.IGNORECASE)
    if match is None:
        return None
    return match.group(0).upper()


def _extract_phone_from_query(query: str) -> Optional[str]:
    match = re.search(r"1\d{10}", query)
    if match is None:
        return None
    return match.group(0)


def _build_user_multimodal_payload(payload: AgentQueryRequest) -> Optional[str]:
    if not payload.images:
        return None
    image_items = []
    for image in payload.images:
        image_items.append(
            {
                "mime_type": image.mime_type,
                "image_url": image.image_url,
                "has_base64": bool(image.image_base64),
            }
        )
    return json.dumps({"images": image_items}, ensure_ascii=False)


def _resolve_patient_from_agent_result(
    db: Session,
    query: str,
    result: dict,
):
    for tool_output in result.get("tool_outputs", []):
        tool_name = tool_output.get("tool_name")
        tool_result = tool_output.get("result", {})

        if tool_name == "verify_patient_identity" and tool_result.get("verified"):
            patient_data = tool_result.get("patient", {})
            patient_id = patient_data.get("id")
            if patient_id is not None:
                patient = patient_service.get_patient_by_id(db, patient_id)
                if patient is not None:
                    return patient
            patient_code = patient_data.get("patient_code")
            if patient_code:
                patient = patient_service.get_patient_by_code(db, patient_code)
                if patient is not None:
                    return patient

        patient_data = tool_result.get("patient")
        if isinstance(patient_data, dict):
            patient_id = patient_data.get("id")
            if patient_id is not None:
                patient = patient_service.get_patient_by_id(db, patient_id)
                if patient is not None:
                    return patient
            patient_code = patient_data.get("patient_code")
            if patient_code:
                patient = patient_service.get_patient_by_code(db, patient_code)
                if patient is not None:
                    return patient

    patient_code = _extract_patient_code_from_query(query)
    if patient_code is not None:
        patient = patient_service.get_patient_by_code(db, patient_code)
        if patient is not None:
            return patient

    phone = _extract_phone_from_query(query)
    if phone is not None:
        return patient_service.get_patient_by_phone(db, phone)
    return None


def _build_memory_context(db: Session, patient, query: str) -> dict:
    short_term_memories = conversation_memory_service.list_recent_conversation_memories(
        db,
        patient_id=patient.id,
        limit=6,
    )
    user_profile = memory_service.get_user_profile(db, patient.id)
    relevant_events = memory_service.get_relevant_memory_events(
        db,
        patient_id=patient.id,
        query=query,
        limit=5,
    )
    return {
        "short_term_memories": [
            {
                "role": memory.role,
                "content": memory.content,
                "multimodal_payload": memory.multimodal_payload,
            }
            for memory in short_term_memories
        ],
        "user_profile": (
            {
                "profile_summary": user_profile.profile_summary,
                "stable_preferences": user_profile.stable_preferences,
                "preferred_topics": user_profile.preferred_topics,
            }
            if user_profile is not None
            else None
        ),
        "relevant_events": [
            {
                "event_time": event.event_time.isoformat(),
                "title": event.title,
                "summary": event.summary,
            }
            for event in relevant_events
        ],
    }


def _build_current_patient_context(patient) -> Optional[dict]:
    if patient is None:
        return None
    return {
        "patient_code": patient.patient_code,
        "phone": patient.phone,
        "id_number": patient.id_number,
        "full_name": patient.full_name,
    }


def _build_bootstrap_tool_outputs(db: Session, patient) -> list[dict]:
    if patient is None or not patient.patient_code:
        return []

    verification_arguments = {"patient_code": patient.patient_code}
    if patient.phone:
        verification_arguments["phone"] = patient.phone
    elif patient.id_number:
        verification_arguments["id_number"] = patient.id_number
    else:
        return []

    verification_result = mcp_tool_service.verify_patient(db, **verification_arguments)
    return [
        {
            "tool_name": "verify_patient_identity",
            "arguments": verification_arguments,
            "result": verification_result,
        }
    ]


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/agent/query",
    response_model=AgentQueryResponse,
    summary="调用 Qwen + 工具查询患者信息",
    description=(
        "主问答接口。把用户的问题发送给 Agent，由 Agent 结合历史短期记忆、长期用户画像、"
        "长期关键事件、内部工具和可选图片一起生成答案。"
    ),
)
def agent_query(
    payload: AgentQueryRequest,
    db: Session = Depends(get_db),
) -> AgentQueryResponse:
    try:
        llm_client = QwenClient()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    agent = QwenMCPAgent(db=db, llm_client=llm_client)
    try:
        pre_resolved_patient = _resolve_patient_from_agent_result(
            db,
            payload.query,
            {"tool_outputs": []},
        )
        memory_context = None
        bootstrap_tool_outputs = []
        if pre_resolved_patient is not None:
            memory_context = _build_memory_context(db, pre_resolved_patient, payload.query)
            bootstrap_tool_outputs = _build_bootstrap_tool_outputs(db, pre_resolved_patient)
        result = agent.run(
            payload.query,
            images=[image.model_dump() for image in payload.images],
            debug_planner=payload.debug_planner,
            memory_context=memory_context,
            current_patient_context=_build_current_patient_context(pre_resolved_patient),
            bootstrap_tool_outputs=bootstrap_tool_outputs,
        )
    except BadRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    patient = _resolve_patient_from_agent_result(db, payload.query, result)
    if patient is not None:
        memory_session_id = f"agent-{uuid4().hex}"
        conversation_memory_service.create_conversation_memory(
            db,
            ConversationMemoryCreate(
                patient_id=patient.id,
                session_id=memory_session_id,
                role="user",
                content=payload.query,
                multimodal_payload=_build_user_multimodal_payload(payload),
            ),
        )
        conversation_memory_service.create_conversation_memory(
            db,
            ConversationMemoryCreate(
                patient_id=patient.id,
                session_id=memory_session_id,
                role="assistant",
                content=result["answer"],
                multimodal_payload=None,
            ),
        )
        short_term_count = conversation_memory_service.count_conversation_memories(
            db,
            patient_id=patient.id,
        )
        if (
            short_term_count >= SHORT_TERM_TRIGGER_MESSAGE_COUNT
            and short_term_count % SHORT_TERM_TRIGGER_MESSAGE_COUNT == 0
        ):
            conversation_texts = memory_service.get_conversation_texts_for_extraction(
                db=db,
                patient_id=patient.id,
                limit=SHORT_TERM_TRIGGER_MESSAGE_COUNT,
            )
            memory_events, user_profile = memory_service.refresh_conversation_memory(
                db=db,
                patient=patient,
                conversation_texts=conversation_texts,
            )
            logger.info(
                "Auto extracted long-term conversation memory for patient_id=%s short_term_count=%s event_count=%s profile_updated=%s",
                patient.id,
                short_term_count,
                len(memory_events),
                user_profile is not None,
            )
    return AgentQueryResponse(**result)

import json
import logging
import re
from datetime import datetime
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from openai import BadRequestError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.llm.qwen_client import QwenClient
from app.llm.query_intents import QueryIntent, detect_query_intent
from app.llm.qwen_mcp_agent import QwenMCPAgent
from app.schemas.agent import AgentAccessContext, AgentQueryRequest, AgentQueryResponse
from app.schemas.memory import ConversationMemoryCreate
from app.services import (
    agent_metrics_service,
    conversation_memory_service,
    evidence_cache_service,
    mcp_tool_service,
    memory_refresh_service,
    memory_service,
    patient_service,
)


router = APIRouter(tags=["Agent"])
logger = logging.getLogger("uvicorn.error")
SHORT_TERM_ROUND_TRIGGER = 5
MESSAGES_PER_ROUND = 2
SHORT_TERM_TRIGGER_MESSAGE_COUNT = SHORT_TERM_ROUND_TRIGGER * MESSAGES_PER_ROUND
ACCESS_CONTEXT_REQUIRED_DETAIL = "active clinician follow-up context required"


def _truthy_header(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_agent_access_context(
    x_agent_demo_context: str | None = Header(default=None, alias="X-Agent-Demo-Context"),
    x_agent_actor_role: str | None = Header(default=None, alias="X-Agent-Actor-Role"),
    x_agent_access_purpose: str | None = Header(default=None, alias="X-Agent-Access-Purpose"),
    x_agent_operator_id: str | None = Header(default=None, alias="X-Agent-Operator-Id"),
    x_agent_tenant_id: str | None = Header(default=None, alias="X-Agent-Tenant-Id"),
) -> AgentAccessContext | None:
    if not _truthy_header(x_agent_demo_context):
        return None

    return AgentAccessContext(
        actor_role=x_agent_actor_role or "clinician",
        access_purpose=x_agent_access_purpose or "follow_up_care",
        operator_id=x_agent_operator_id or "demo-operator",
        tenant_id=x_agent_tenant_id or "demo-tenant",
        is_demo_context=True,
    )


def _extract_patient_code_from_query(query: str) -> str | None:
    match = re.search(r"P\d{4,}", query, flags=re.IGNORECASE)
    if match is None:
        return None
    return match.group(0).upper()


def _build_user_multimodal_payload(payload: AgentQueryRequest) -> str | None:
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

    return None


def _resolve_patient_from_request(db: Session, payload: AgentQueryRequest):
    if payload.patient_code:
        patient = patient_service.get_patient_by_code(db, payload.patient_code.upper())
        if patient is not None:
            return patient
    return _resolve_patient_from_agent_result(db, payload.query, {"tool_outputs": []})


def _build_memory_context(
    db: Session,
    patient,
    query: str,
    *,
    include_relevant_events: bool = True,
) -> tuple[dict, dict]:
    short_term_memories = conversation_memory_service.list_recent_conversation_memories(
        db,
        patient_id=patient.id,
        limit=6,
    )
    user_profile = memory_service.get_user_profile(db, patient.id)
    if include_relevant_events:
        memory_search_results = memory_service.get_relevant_memory_search_results(
            db=db,
            patient_id=patient.id,
            query=query,
            limit=5,
        )
    else:
        memory_search_results = []
    retrieval_sources = sorted(
        {
            source
            for item in memory_search_results
            for source in item.get("retrieval_sources", [])
        }
    )
    used_fallback = bool(memory_search_results) and all(
        item.get("retrieval_sources") == ["recent"] for item in memory_search_results
    )
    context = {
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
                "event_time": item["event"].event_time.isoformat(),
                "title": item["event"].title,
                "summary": item["event"].summary,
            }
            for item in memory_search_results
        ],
    }
    debug = {
        "retrieval_sources": retrieval_sources,
        "used_fallback": used_fallback,
        "result_count": len(memory_search_results),
        "include_relevant_events": include_relevant_events,
    }
    return context, debug


def _build_current_patient_context(
    patient,
    access_context: AgentAccessContext | None,
    payload: AgentQueryRequest,
) -> dict | None:
    if patient is None:
        return None
    if access_context is None and payload.identity_verification is None:
        return None
    context = {
        "patient_id": patient.id,
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
    }
    if access_context is not None:
        context["actor_role"] = access_context.actor_role
        context["access_purpose"] = access_context.access_purpose
        context["operator_id"] = access_context.operator_id
        context["tenant_id"] = access_context.tenant_id
        context["is_demo_context"] = access_context.is_demo_context
    if payload.identity_verification is not None:
        if payload.identity_verification.phone:
            context["phone"] = payload.identity_verification.phone
        if payload.identity_verification.id_number:
            context["id_number"] = payload.identity_verification.id_number
    return context


def _build_bootstrap_tool_outputs(
    db: Session,
    patient,
    payload: AgentQueryRequest,
) -> list[dict]:
    if patient is None or not patient.patient_code:
        return []

    if payload.identity_verification is None:
        return []

    verification_arguments = {"patient_code": patient.patient_code}
    if payload.identity_verification.phone:
        verification_arguments["phone"] = payload.identity_verification.phone
    if payload.identity_verification.id_number:
        verification_arguments["id_number"] = payload.identity_verification.id_number
    if "phone" not in verification_arguments and "id_number" not in verification_arguments:
        return []

    verification_result = mcp_tool_service.verify_patient(db, **verification_arguments)
    return [
        {
            "tool_name": "verify_patient_identity",
            "arguments": mcp_tool_service.sanitize_agent_payload(verification_arguments),
            "result": verification_result,
        }
    ]


def _should_schedule_memory_refresh(short_term_count: int) -> bool:
    return (
        short_term_count >= SHORT_TERM_TRIGGER_MESSAGE_COUNT
        and short_term_count % SHORT_TERM_TRIGGER_MESSAGE_COUNT == 0
    )


def _format_visit_time(value: str | None) -> str:
    if not value:
        return "未知时间"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def _format_optional(value) -> str:
    return str(value) if value else "未记录"


def _build_latest_visit_route_answer(patient, visit_result: dict) -> str:
    if not visit_result.get("found"):
        return f"未查询到患者 {patient.full_name} 的就诊记录，当前证据不足，无法总结最近一次就诊。"

    visit_records = visit_result.get("visit_records", [])
    if not visit_records:
        return f"患者 {patient.full_name} 暂无可用的就诊记录，当前证据不足。"

    visit = visit_records[0]
    lines = [
        f"患者 {patient.full_name} 最近一次就诊摘要如下：",
        f"1. 就诊时间：{_format_visit_time(visit.get('visit_time'))}",
        f"2. 就诊科室：{visit.get('department') or '未记录'}，就诊类型：{visit.get('visit_type') or '未记录'}",
        f"3. 接诊医生：{visit.get('physician_name') or '未记录'}，就诊编号：{visit.get('visit_code') or '未记录'}",
        f"4. 本次摘要：{visit.get('summary') or '未记录'}",
    ]
    if visit.get("notes"):
        lines.append(f"5. 补充备注：{visit['notes']}")
    lines.append("以上内容基于当前医护随访工作台的结构化就诊记录。")
    return "\n".join(lines)


def _build_patient_profile_route_answer(patient, profile_result: dict) -> str:
    if not profile_result.get("found"):
        return f"未查询到患者 {patient.full_name} 的基本信息，当前证据不足。"

    profile = profile_result.get("patient", {})
    return "\n".join(
        [
            f"患者 {profile.get('full_name') or patient.full_name} 基本信息如下：",
            f"1. 性别：{_format_optional(profile.get('gender'))}",
            f"2. 出生年份：{_format_optional(profile.get('birth_year'))}",
            f"3. 联系方式：{_format_optional(profile.get('phone_masked'))}",
            "联系方式和证件号请以患者卡片中的结构化字段为准，自然语言摘要不展开完整敏感信息。",
        ]
    )


def _build_medical_case_route_answer(patient, case_result: dict) -> str:
    if not case_result.get("found"):
        return f"未查询到患者 {patient.full_name} 的病历信息，当前证据不足。"

    medical_cases = case_result.get("medical_cases", [])
    if not medical_cases:
        return f"患者 {patient.full_name} 暂无可用病历记录，当前证据不足。"

    lines = [f"患者 {patient.full_name} 最近病历摘要如下："]
    for index, item in enumerate(medical_cases[:3], start=1):
        lines.extend(
            [
                f"{index}. 病历编号：{_format_optional(item.get('case_code'))}",
                f"   诊断：{_format_optional(item.get('diagnosis'))}",
                f"   主诉：{_format_optional(item.get('chief_complaint'))}",
                f"   治疗计划：{_format_optional(item.get('treatment_plan'))}",
                f"   记录时间：{_format_optional(item.get('recorded_at'))}",
            ]
        )
    lines.append("以上内容基于医护随访工作台的结构化病历记录，仅用于随访辅助总结。")
    return "\n".join(lines)


def _build_follow_up_plan_answer(patient, plan_result: dict) -> str:
    records = plan_result.get("records", [])
    if not records:
        return f"患者 {patient.full_name} 暂无待展示的随访计划。"

    lines = [f"患者 {patient.full_name} 的随访计划如下："]
    for index, item in enumerate(records[:5], start=1):
        lines.extend(
            [
                f"{index}. 目标：{_format_optional(item.get('goal'))}",
                f"   计划时间：{_format_optional(item.get('scheduled_time'))}",
                f"   科室/医生：{_format_optional(item.get('department'))} / {_format_optional(item.get('doctor_name'))}",
                f"   状态：{_format_optional(item.get('status'))}",
            ]
        )
        if item.get("notes"):
            lines.append(f"   备注：{item['notes']}")
    lines.append("请医护人员结合最新病情变化确认是否需要调整随访安排。")
    return "\n".join(lines)


def _build_medication_reminder_answer(patient, reminder_result: dict) -> str:
    records = reminder_result.get("records", [])
    if not records:
        return f"患者 {patient.full_name} 暂无结构化用药提醒记录。"

    lines = [f"患者 {patient.full_name} 的用药提醒如下："]
    for index, item in enumerate(records[:5], start=1):
        lines.extend(
            [
                f"{index}. 药品：{_format_optional(item.get('medication_name'))}",
                f"   剂量/频次：{_format_optional(item.get('dosage'))} / {_format_optional(item.get('frequency'))}",
                f"   起止时间：{_format_optional(item.get('start_time'))} 至 {_format_optional(item.get('end_time'))}",
            ]
        )
        if item.get("notes"):
            lines.append(f"   备注：{item['notes']}")
    lines.append("涉及停药、加减量或换药时，请以医生正式医嘱为准。")
    return "\n".join(lines)


def _has_clinician_follow_up_access(
    access_context: AgentAccessContext | None,
    patient,
) -> bool:
    return (
        patient is not None
        and access_context is not None
        and access_context.actor_role == "clinician"
        and access_context.access_purpose == "follow_up_care"
    )


def _tool_for_adaptive_intent(intent_name: str) -> tuple[str, dict] | None:
    if intent_name == "latest_visit":
        return "get_patient_visit_records", {"limit": 1}
    if intent_name == "patient_profile":
        return "get_patient_profile", {}
    if intent_name == "medical_case":
        return "get_patient_medical_cases", {}
    if intent_name == "follow_up_plan":
        return "get_follow_up_plans", {}
    if intent_name == "medication_reminder":
        return "get_medication_reminders", {}
    return None


def _build_tool_direct_answer(patient, intent_name: str, tool_result: dict) -> str:
    if intent_name == "latest_visit":
        return _build_latest_visit_route_answer(patient, tool_result)
    if intent_name == "patient_profile":
        return _build_patient_profile_route_answer(patient, tool_result)
    if intent_name == "medical_case":
        return _build_medical_case_route_answer(patient, tool_result)
    if intent_name == "follow_up_plan":
        return _build_follow_up_plan_answer(patient, tool_result)
    if intent_name == "medication_reminder":
        return _build_medication_reminder_answer(patient, tool_result)
    return "当前问题需要进入完整 Agent Tool Loop 处理。"


def _source_version_for_tool(
    db: Session,
    *,
    tool_name: str,
    tool_arguments: dict,
) -> str:
    return mcp_tool_service.get_patient_evidence_source_version(
        db,
        tool_name=tool_name,
        patient_id=tool_arguments.get("patient_id"),
        patient_code=tool_arguments.get("patient_code"),
        limit=tool_arguments.get("limit"),
        status=tool_arguments.get("status"),
    )


def _execute_structured_tool(db: Session, tool_name: str, tool_arguments: dict) -> dict:
    if tool_name == "get_patient_visit_records":
        return mcp_tool_service.get_patient_visit_records(db, **tool_arguments)
    if tool_name == "get_patient_profile":
        return mcp_tool_service.get_patient_profile(db, **tool_arguments)
    if tool_name == "get_patient_medical_cases":
        return mcp_tool_service.get_patient_medical_cases(db, **tool_arguments)
    if tool_name == "get_follow_up_plans":
        return mcp_tool_service.get_follow_up_plans(db, **tool_arguments)
    if tool_name == "get_medication_reminders":
        return mcp_tool_service.get_medication_reminders(db, **tool_arguments)
    return {"found": False, "error": f"unsupported adaptive route tool: {tool_name}"}


def _route_runtime_metrics(
    *,
    route_type: str,
    route_reason: str,
    intent: QueryIntent,
    cache_hit: bool,
    fallback_reason: str | None = None,
    latency_saved_ms: int = 0,
    cache_match_strategy: str | None = None,
    cache_similarity_score: float | None = None,
) -> dict:
    return {
        "execution_mode": route_type,
        "route_type": route_type,
        "route_reason": route_reason,
        "intent_confidence": intent.confidence,
        "cache_hit": cache_hit,
        "latency_saved_ms": latency_saved_ms,
        "fallback_reason": fallback_reason,
        "cache_match_strategy": cache_match_strategy,
        "cache_similarity_score": cache_similarity_score,
        "force_full_agent": False,
        "planner_candidate_count": 0,
        "fallback_count": 0 if fallback_reason is None else 1,
    }


def _build_adaptive_trace(
    *,
    run_id: str,
    route_type: str,
    route_reason: str,
    intent: QueryIntent,
    cache_hit: bool,
    tool_outputs: list[dict],
    fallback_reason: str | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "adaptive_evidence_routing": True,
        "route_type": route_type,
        "route_reason": route_reason,
        "intent": intent.name,
        "intent_confidence": intent.confidence,
        "cache_hit": cache_hit,
        "fallback_reason": fallback_reason,
        "planner": {
            "candidate_count": 0,
            "temperatures": [],
            "candidates": [],
            "merged_plan": None,
            "filtered_unknown_tools": [],
            "fallback_reasons": [route_reason],
        },
        "tool_sequence": [
            {
                "tool_name": item["tool_name"],
                "status": "cache" if cache_hit else "ok",
                "duration_ms": 0,
                "arguments": item["arguments"],
                "result_summary": item["result"],
            }
            for item in tool_outputs
        ],
    }


def _try_adaptive_evidence_route(
    db: Session,
    *,
    intent: QueryIntent,
    patient,
    bootstrap_tool_outputs: list[dict],
    payload: AgentQueryRequest,
    access_context: AgentAccessContext | None,
    run_id: str,
) -> dict | None:
    if payload.force_full_agent:
        return None
    if not intent.use_adaptive_routing or patient is None:
        return None
    if intent.confidence < 0.68:
        return None
    if not _has_clinician_follow_up_access(access_context, patient):
        return None
    tool_match = _tool_for_adaptive_intent(intent.name)
    if tool_match is None:
        return None

    tool_name, intent_tool_arguments = tool_match
    tool_arguments = {
        "patient_id": patient.id,
        "patient_code": patient.patient_code,
        **intent_tool_arguments,
    }
    source_version = _source_version_for_tool(
        db,
        tool_name=tool_name,
        tool_arguments=tool_arguments,
    )

    def resolve_cache_source_version(entry) -> str:
        return _source_version_for_tool(
            db,
            tool_name=entry.tool_name,
            tool_arguments=evidence_cache_service.load_entry_tool_arguments(entry),
        )

    cache_lookup = evidence_cache_service.find_fresh_cache_entry(
        db,
        patient_id=patient.id,
        actor_role=access_context.actor_role,
        access_purpose=access_context.access_purpose,
        intent=intent.name,
        query=payload.query,
        source_version_resolver=resolve_cache_source_version,
    )
    cache_entry = cache_lookup.entry
    cache_miss_reason = cache_lookup.miss_reason
    if cache_entry is not None:
        cached_arguments = evidence_cache_service.load_entry_tool_arguments(cache_entry)
        cached_result = evidence_cache_service.load_entry_evidence(cache_entry)
        tool_outputs = list(bootstrap_tool_outputs) + [
            {
                "tool_name": cache_entry.tool_name,
                "arguments": cached_arguments,
                "result": cached_result,
            }
        ]
        route_reason = f"{intent.route_reason}; fresh semantic evidence cache hit"
        execution_trace = (
            _build_adaptive_trace(
                run_id=run_id,
                route_type="semantic_cache",
                route_reason=route_reason,
                intent=intent,
                cache_hit=True,
                tool_outputs=tool_outputs,
            )
            if payload.debug_planner
            else None
        )
        return {
            "answer": _build_tool_direct_answer(patient, intent.name, cached_result),
            "tool_outputs": tool_outputs,
            "run_id": run_id,
            "route_type": "semantic_cache",
            "route_reason": route_reason,
            "intent_confidence": intent.confidence,
            "cache_hit": True,
            "runtime_metrics": _route_runtime_metrics(
                route_type="semantic_cache",
                route_reason=route_reason,
                intent=intent,
                cache_hit=True,
                latency_saved_ms=1200,
                cache_match_strategy=cache_lookup.match_strategy,
                cache_similarity_score=cache_lookup.similarity_score,
            ),
            "execution_trace": execution_trace,
            "planner_debug": execution_trace,
        }

    tool_outputs = list(bootstrap_tool_outputs)
    tool_result = _execute_structured_tool(db, tool_name, tool_arguments)
    tool_outputs.append(
        {
            "tool_name": tool_name,
            "arguments": tool_arguments,
            "result": tool_result,
        }
    )
    evidence_cache_service.create_cache_entry(
        db,
        patient_id=patient.id,
        actor_role=access_context.actor_role,
        access_purpose=access_context.access_purpose,
        intent=intent.name,
        query=payload.query,
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        evidence=tool_result,
        source_version=tool_result.get("source_version") or source_version,
    )
    route_reason = f"{intent.route_reason}; structured tool direct route"
    if cache_miss_reason:
        route_reason = f"{route_reason}; cache_miss={cache_miss_reason}"
    execution_trace = (
        _build_adaptive_trace(
            run_id=run_id,
            route_type="tool_direct",
            route_reason=route_reason,
            intent=intent,
            cache_hit=False,
            tool_outputs=tool_outputs,
            fallback_reason=cache_miss_reason,
        )
        if payload.debug_planner
        else None
    )
    logger.info(
        "agent_adaptive_route_completed %s",
        json.dumps(
            {
                "run_id": run_id,
                "intent": intent.name,
                "patient_code": patient.patient_code,
                "route_type": "tool_direct",
                "cache_miss_reason": cache_miss_reason,
            },
            ensure_ascii=False,
        ),
    )
    return {
        "answer": _build_tool_direct_answer(patient, intent.name, tool_result),
        "tool_outputs": tool_outputs,
        "run_id": run_id,
        "route_type": "tool_direct",
        "route_reason": route_reason,
        "intent_confidence": intent.confidence,
        "cache_hit": False,
        "runtime_metrics": _route_runtime_metrics(
            route_type="tool_direct",
            route_reason=route_reason,
            intent=intent,
            cache_hit=False,
            fallback_reason=cache_miss_reason,
            latency_saved_ms=800,
            cache_match_strategy=cache_lookup.match_strategy,
            cache_similarity_score=cache_lookup.similarity_score,
        ),
        "execution_trace": execution_trace,
        "planner_debug": execution_trace,
    }


def _has_verified_identity(tool_outputs: list[dict]) -> bool:
    for tool_output in tool_outputs:
        if tool_output.get("tool_name") != "verify_patient_identity":
            continue
        result = tool_output.get("result", {})
        if isinstance(result, dict) and result.get("verified"):
            return True
    return False


def _count_tool_outcomes(tool_outputs: list[dict]) -> tuple[int, int]:
    blocked_count = 0
    error_count = 0
    for tool_output in tool_outputs:
        result = tool_output.get("result", {})
        if not isinstance(result, dict):
            continue
        if result.get("allowed") is False:
            blocked_count += 1
            continue
        if result.get("error"):
            error_count += 1
    return error_count, blocked_count


def _smalltalk_answer(query: str) -> str:
    if "谢" in query or "thank" in query.lower():
        return "不客气。当前工作台可协助医护人员查询患者资料、诊后随访计划、用药提醒和随访风险提示。"
    return "当前工作台面向医生、护士和随访专员，可协助整理患者就诊/病历摘要、随访安排、用药提醒，并对高风险症状或用药调整问题进行保守提示。"


def _out_of_domain_answer() -> str:
    return (
        "这个问题超出了当前助手的服务边界。我主要支持患者服务、诊后随访、病历查询、"
        "用药提醒和健康咨询相关场景；你可以换成这些方向的问题继续。"
    )


def _high_risk_answer(risk_result: dict) -> str:
    terms = "、".join(risk_result.get("trigger_terms", [])) or "高风险表达"
    action = risk_result.get("recommended_action") or "建议尽快联系医生或线下医疗机构。"
    return (
        f"风险提醒：问题描述中出现了“{terms}”，这类情况不适合由助手直接给出诊断、处方或停药建议。\n\n"
        f"建议：{action}\n\n"
        "工作台可以继续协助医护人员整理既往就诊记录、随访计划或用药提醒，但紧急症状请优先处理线下医疗安全。"
    )


def _clinician_access_required_answer() -> str:
    return (
        "请先在医护工作台选择患者，再查询病历、就诊记录、随访计划或用药提醒。"
        "本次请求未进入私有患者工具链路。"
    )


def _extract_evidence(tool_outputs: list[dict]) -> list[dict]:
    evidence: list[dict] = []
    for tool_output in tool_outputs:
        result = tool_output.get("result", {})
        if not isinstance(result, dict):
            continue
        for item in result.get("evidence", []) or []:
            if isinstance(item, dict):
                evidence.append({"tool_name": tool_output.get("tool_name"), **item})
        if result.get("found") is not None and not result.get("evidence"):
            evidence.append(
                {
                    "tool_name": tool_output.get("tool_name"),
                    "found": result.get("found"),
                    "count": result.get("count"),
                }
            )
    return evidence


def _extract_risk(result: dict) -> tuple[str | None, str | None]:
    if result.get("risk_level"):
        return result.get("risk_level"), result.get("recommended_action")
    for tool_output in result.get("tool_outputs", []):
        tool_result = tool_output.get("result", {})
        if isinstance(tool_result, dict) and tool_result.get("risk_level"):
            return tool_result.get("risk_level"), tool_result.get("recommended_action")
    return None, None


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/agent/query",
    response_model=AgentQueryResponse,
    summary="Call the patient-support agent.",
    description=(
        "The request is processed by the Agent with patient context, memory context, "
        "tool execution, and optional images."
    ),
)
def agent_query(
    payload: AgentQueryRequest,
    background_tasks: BackgroundTasks,
    access_context: AgentAccessContext | None = Depends(resolve_agent_access_context),
    db: Session = Depends(get_db),
) -> AgentQueryResponse:
    started_at = perf_counter()
    run_id = f"agent-{uuid4().hex}"
    intent = detect_query_intent(payload.query, has_images=bool(payload.images))
    stage_timings_ms = {
        "patient_resolution_ms": 0,
        "memory_context_ms": 0,
        "agent_execution_ms": 0,
        "persistence_ms": 0,
    }
    result: dict | None = None
    patient = None
    pre_resolved_patient = None
    memory_debug = None
    memory_refresh_scheduled = False
    metric_recorded = False

    def record_metric(status_value: str, error_detail: str | None = None) -> None:
        nonlocal metric_recorded
        if metric_recorded:
            return

        runtime_metrics = (result or {}).get("runtime_metrics", {})
        tool_outputs = (result or {}).get("tool_outputs", [])
        tool_error_count, tool_blocked_count = _count_tool_outcomes(tool_outputs)
        total_duration_ms = int((perf_counter() - started_at) * 1000)
        patient_for_metric = patient or pre_resolved_patient

        agent_metrics_service.create_agent_run_metric(
            db,
            run_id=run_id,
            patient_code=(
                patient_for_metric.patient_code
                if patient_for_metric is not None
                else _extract_patient_code_from_query(payload.query)
            ),
            intent=intent.name,
            status=status_value,
            execution_mode=runtime_metrics.get("execution_mode", "agent"),
            route_type=runtime_metrics.get("route_type", runtime_metrics.get("execution_mode")),
            route_reason=runtime_metrics.get("route_reason"),
            actor_role=access_context.actor_role if access_context is not None else None,
            access_purpose=(
                access_context.access_purpose if access_context is not None else None
            ),
            operator_id=access_context.operator_id if access_context is not None else None,
            tenant_id=access_context.tenant_id if access_context is not None else None,
            is_demo_context=bool(access_context and access_context.is_demo_context),
            cache_match_strategy=runtime_metrics.get("cache_match_strategy"),
            cache_similarity_score=(
                int(round(float(runtime_metrics["cache_similarity_score"]) * 100))
                if runtime_metrics.get("cache_similarity_score") is not None
                else None
            ),
            intent_confidence=int(round(float(runtime_metrics.get("intent_confidence", 0)) * 100)),
            cache_hit=bool(runtime_metrics.get("cache_hit")),
            latency_saved_ms=int(runtime_metrics.get("latency_saved_ms", 0) or 0),
            fallback_reason=runtime_metrics.get("fallback_reason"),
            has_images=bool(payload.images),
            fast_path=runtime_metrics.get("route_type") in {"semantic_cache", "tool_direct"},
            identity_verified=_has_verified_identity(tool_outputs),
            risk_level=(result or {}).get("risk_level"),
            recommended_action=(result or {}).get("recommended_action"),
            used_relevant_events=bool(memory_debug and memory_debug.get("include_relevant_events")),
            used_memory_fallback=bool(memory_debug and memory_debug.get("used_fallback")),
            memory_refresh_scheduled=memory_refresh_scheduled,
            planner_candidate_count=runtime_metrics.get("planner_candidate_count", 0),
            tool_count=len(tool_outputs),
            tool_error_count=tool_error_count,
            tool_blocked_count=tool_blocked_count,
            fallback_count=runtime_metrics.get("fallback_count", 0),
            total_duration_ms=total_duration_ms,
            patient_resolution_ms=stage_timings_ms["patient_resolution_ms"],
            memory_context_ms=stage_timings_ms["memory_context_ms"],
            agent_execution_ms=stage_timings_ms["agent_execution_ms"],
            persistence_ms=stage_timings_ms["persistence_ms"],
            error_detail=(error_detail[:1000] if error_detail else None),
        )
        metric_recorded = True

    if intent.bypass_agent:
        result = {
            "answer": _smalltalk_answer(payload.query)
            if intent.name == "smalltalk"
            else _out_of_domain_answer(),
            "tool_outputs": [],
            "run_id": run_id,
            "intent": intent.domain,
            "intent_confidence": intent.confidence,
            "route_type": "template",
            "route_reason": intent.route_reason,
            "cache_hit": False,
            "evidence": [],
            "risk_level": None,
            "recommended_action": None,
            "runtime_metrics": {
                "execution_mode": "template",
                "route_type": "template",
                "route_reason": intent.route_reason,
                "intent_confidence": intent.confidence,
                "cache_hit": False,
                "latency_saved_ms": 500,
                "fallback_reason": None,
                "intent": intent.name,
                "intent_domain": intent.domain,
                "force_full_agent": payload.force_full_agent,
                "stage_timings_ms": stage_timings_ms,
                "total_duration_ms": int((perf_counter() - started_at) * 1000),
            },
        }
        record_metric("success")
        return AgentQueryResponse(**result)

    patient_resolution_started_at = perf_counter()
    pre_resolved_patient = _resolve_patient_from_request(db, payload)
    stage_timings_ms["patient_resolution_ms"] = int(
        (perf_counter() - patient_resolution_started_at) * 1000
    )

    risk_result = mcp_tool_service.assess_follow_up_risk(payload.query)
    if risk_result.get("risk_level") in {"high", "urgent"}:
        mcp_tool_service.create_risk_event(
            db,
            run_id=run_id,
            patient_id=pre_resolved_patient.id if pre_resolved_patient is not None else None,
            risk_result=risk_result,
        )
        tool_outputs = [
            {
                "tool_name": "assess_follow_up_risk",
                "arguments": {"query": payload.query},
                "result": risk_result,
            }
        ]
        result = {
            "answer": _high_risk_answer(risk_result),
            "tool_outputs": tool_outputs,
            "run_id": run_id,
            "intent": intent.domain,
            "intent_confidence": max(intent.confidence, 0.95),
            "route_type": "risk_guard",
            "route_reason": "risk_guard_matched_before_cache_or_tools",
            "cache_hit": False,
            "evidence": _extract_evidence(tool_outputs),
            "risk_level": risk_result.get("risk_level"),
            "recommended_action": risk_result.get("recommended_action"),
            "runtime_metrics": {
                "execution_mode": "risk_guard",
                "route_type": "risk_guard",
                "route_reason": "risk_guard_matched_before_cache_or_tools",
                "intent_confidence": max(intent.confidence, 0.95),
                "cache_hit": False,
                "latency_saved_ms": 1000,
                "fallback_reason": None,
                "intent": intent.name,
                "intent_domain": intent.domain,
                "force_full_agent": payload.force_full_agent,
                "stage_timings_ms": stage_timings_ms,
                "total_duration_ms": int((perf_counter() - started_at) * 1000),
            },
        }
        record_metric("success")
        return AgentQueryResponse(**result)

    if _tool_for_adaptive_intent(intent.name) is not None and not _has_clinician_follow_up_access(
        access_context,
        pre_resolved_patient,
    ):
        tool_outputs = [
            {
                "tool_name": "clinician_access_check",
                "arguments": {
                    "patient_code": payload.patient_code,
                    "server_context_present": access_context is not None,
                    "actor_role": (
                        access_context.actor_role if access_context is not None else None
                    ),
                    "access_purpose": (
                        access_context.access_purpose if access_context is not None else None
                    ),
                },
                "result": {
                    "allowed": False,
                    "error": "active clinician follow-up patient context required",
                },
            }
        ]
        result = {
            "answer": _clinician_access_required_answer(),
            "tool_outputs": tool_outputs,
            "run_id": run_id,
            "intent": intent.domain,
            "intent_confidence": intent.confidence,
            "route_type": "template",
            "route_reason": "clinician_access_check_failed",
            "cache_hit": False,
            "evidence": [],
            "risk_level": None,
            "recommended_action": None,
            "runtime_metrics": {
                "execution_mode": "template",
                "route_type": "template",
                "route_reason": "clinician_access_check_failed",
                "intent_confidence": intent.confidence,
                "cache_hit": False,
                "latency_saved_ms": 500,
                "fallback_reason": "missing_or_invalid_clinician_access_context",
                "intent": intent.name,
                "intent_domain": intent.domain,
                "force_full_agent": payload.force_full_agent,
                "stage_timings_ms": stage_timings_ms,
                "total_duration_ms": int((perf_counter() - started_at) * 1000),
            },
        }
        record_metric("access_denied")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_CONTEXT_REQUIRED_DETAIL,
        )

    memory_context = None
    bootstrap_tool_outputs: list[dict] = []
    if pre_resolved_patient is not None:
        bootstrap_tool_outputs = _build_bootstrap_tool_outputs(
            db,
            pre_resolved_patient,
            payload,
        )
        agent_execution_started_at = perf_counter()
        adaptive_route_result = _try_adaptive_evidence_route(
            db,
            intent=intent,
            patient=pre_resolved_patient,
            bootstrap_tool_outputs=bootstrap_tool_outputs,
            payload=payload,
            access_context=access_context,
            run_id=run_id,
        )
        if adaptive_route_result is not None:
            result = adaptive_route_result
            patient = pre_resolved_patient
            stage_timings_ms["agent_execution_ms"] = int(
                (perf_counter() - agent_execution_started_at) * 1000
            )
            memory_debug = {
                "intent": intent.name,
                "adaptive_route": True,
                "include_relevant_events": False,
            }
        else:
            memory_started_at = perf_counter()
            memory_context, memory_debug = _build_memory_context(
                db,
                pre_resolved_patient,
                payload.query,
                include_relevant_events=intent.include_relevant_events,
            )
            stage_timings_ms["memory_context_ms"] = int(
                (perf_counter() - memory_started_at) * 1000
            )
            patient = None
    else:
        patient = None

    if patient is None:
        try:
            llm_client = QwenClient()
        except ValueError as exc:
            record_metric("config_error", str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            )
        agent = QwenMCPAgent(db=db, llm_client=llm_client)
        agent_execution_started_at = perf_counter()
        try:
            result = agent.run(
                user_query=payload.query,
                images=[image.model_dump() for image in payload.images],
                debug_planner=payload.debug_planner,
                memory_context=memory_context,
                current_patient_context=_build_current_patient_context(
                    pre_resolved_patient,
                    access_context,
                    payload,
                ),
                bootstrap_tool_outputs=bootstrap_tool_outputs,
                run_id=run_id,
            )
        except BadRequestError as exc:
            record_metric("bad_request", str(exc))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        stage_timings_ms["agent_execution_ms"] = int(
            (perf_counter() - agent_execution_started_at) * 1000
        )

        patient = _resolve_patient_from_agent_result(db, payload.query, result)
    persistence_started_at = perf_counter()
    if patient is not None:
        memory_session_id = f"{run_id}-{uuid4().hex[:8]}"
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
        if _should_schedule_memory_refresh(short_term_count):
            trigger = memory_refresh_service.MemoryRefreshTrigger.create(
                patient_id=patient.id,
                recent_limit=SHORT_TERM_TRIGGER_MESSAGE_COUNT,
                short_term_count=short_term_count,
                run_id=run_id,
            )
            background_tasks.add_task(
                memory_refresh_service.refresh_conversation_memory_for_trigger,
                trigger,
            )
            memory_refresh_scheduled = True
            logger.info(
                "agent_memory_refresh_scheduled %s",
                json.dumps(
                    {
                        "run_id": run_id,
                        "patient_id": patient.id,
                        "patient_code": patient.patient_code,
                        "short_term_count": short_term_count,
                    },
                    ensure_ascii=False,
                ),
            )
    stage_timings_ms["persistence_ms"] = int((perf_counter() - persistence_started_at) * 1000)

    result["run_id"] = run_id
    result["memory_refresh_scheduled"] = memory_refresh_scheduled
    runtime_metrics = result.get("runtime_metrics", {})
    runtime_metrics.setdefault("route_type", "agent_loop")
    runtime_metrics.setdefault("route_reason", intent.route_reason)
    runtime_metrics.setdefault("intent_confidence", intent.confidence)
    runtime_metrics.setdefault("cache_hit", False)
    runtime_metrics.setdefault("latency_saved_ms", 0)
    runtime_metrics.setdefault("cache_match_strategy", None)
    runtime_metrics.setdefault("cache_similarity_score", None)
    if runtime_metrics["route_type"] == "agent_loop":
        runtime_metrics.setdefault("fallback_reason", intent.route_reason)
    runtime_metrics["intent"] = intent.name
    runtime_metrics["intent_domain"] = intent.domain
    runtime_metrics["force_full_agent"] = payload.force_full_agent
    runtime_metrics["stage_timings_ms"] = stage_timings_ms
    runtime_metrics["total_duration_ms"] = int((perf_counter() - started_at) * 1000)
    result["runtime_metrics"] = runtime_metrics
    result["intent"] = intent.domain
    result["intent_confidence"] = runtime_metrics.get("intent_confidence", intent.confidence)
    result["route_type"] = runtime_metrics.get("route_type", "agent_loop")
    result["route_reason"] = runtime_metrics.get("route_reason", intent.route_reason)
    result["cache_hit"] = bool(runtime_metrics.get("cache_hit"))
    result["evidence"] = _extract_evidence(result.get("tool_outputs", []))
    risk_level, recommended_action = _extract_risk(result)
    result["risk_level"] = risk_level
    result["recommended_action"] = recommended_action
    if risk_level in {"high", "urgent"}:
        matching_risk_result = None
        for tool_output in result.get("tool_outputs", []):
            tool_result = tool_output.get("result", {})
            if isinstance(tool_result, dict) and tool_result.get("risk_level") == risk_level:
                matching_risk_result = tool_result
                break
        if matching_risk_result is not None:
            mcp_tool_service.create_risk_event(
                db,
                run_id=run_id,
                patient_id=patient.id if patient is not None else None,
                risk_result=matching_risk_result,
            )
    if payload.debug_planner and result.get("execution_trace"):
        execution_trace = result["execution_trace"]
        execution_trace["memory"] = memory_debug
        execution_trace["memory_refresh_scheduled"] = memory_refresh_scheduled
        execution_trace["resolved_patient_code"] = patient.patient_code if patient is not None else None
        execution_trace["runtime"] = runtime_metrics
        result["planner_debug"] = execution_trace

    result["tool_outputs"] = mcp_tool_service.sanitize_tool_outputs(
        result.get("tool_outputs", [])
    )
    result["evidence"] = mcp_tool_service.sanitize_agent_payload(result.get("evidence", []))
    if result.get("execution_trace"):
        result["execution_trace"] = mcp_tool_service.sanitize_agent_payload(
            result["execution_trace"]
        )
    if result.get("planner_debug"):
        result["planner_debug"] = mcp_tool_service.sanitize_agent_payload(
            result["planner_debug"]
        )

    record_metric("success")
    logger.info(
        "agent_query_completed %s",
        json.dumps(
            {
                "run_id": run_id,
                "debug_planner": payload.debug_planner,
                "resolved_patient": patient.patient_code if patient is not None else None,
                "memory_refresh_scheduled": memory_refresh_scheduled,
                "tool_count": len(result.get("tool_outputs", [])),
                "memory_debug": memory_debug,
                "intent": intent.name,
                "runtime_metrics": runtime_metrics,
            },
            ensure_ascii=False,
        ),
    )
    return AgentQueryResponse(**result)

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re


LATEST_VISIT_KEYWORDS = (
    "recent visit",
    "latest visit",
    "最近一次",
    "最新一次",
    "最近",
    "最新",
    "就诊",
    "复诊",
)
ADAPTIVE_LATEST_VISIT_KEYWORDS = (
    "最近一次就诊",
    "最新一次就诊",
    "最近一次复诊",
    "最新一次复诊",
    "上次复诊",
    "上次复查",
    "latest visit",
    "recent visit",
)
PATIENT_PROFILE_KEYWORDS = (
    "patient profile",
    "patient info",
    "patient information",
    "basic information",
    "患者信息",
    "基本信息",
    "个人信息",
)
ADAPTIVE_PATIENT_PROFILE_KEYWORDS = (
    "患者基本信息",
    "患者信息",
    "基本信息",
    "个人信息",
    "patient profile",
    "patient information",
    "basic information",
)
MEDICAL_CASE_KEYWORDS = (
    "medical case",
    "diagnosis",
    "case summary",
    "病历",
    "病例",
    "诊断",
)
ADAPTIVE_MEDICAL_CASE_KEYWORDS = (
    "病历摘要",
    "病例摘要",
    "诊断摘要",
    "最近病历",
    "最近病例",
    "medical case",
    "case summary",
    "diagnosis",
)
COMPLEX_QUERY_MARKERS = (
    "结合",
    "图片",
    "图像",
    "是否",
    "有关",
    "判断",
    "分析",
    "对比",
    "科",
)

FOLLOW_UP_PLAN_KEYWORDS = (
    "follow-up plan",
    "随访计划",
    "随访安排",
    "复查计划",
    "复诊计划",
    "下一次随访",
)
MEDICATION_REMINDER_KEYWORDS = (
    "medication reminder",
    "用药提醒",
    "服药提醒",
    "吃药提醒",
    "用药安排",
)


@dataclass(frozen=True)
class QueryIntent:
    name: str
    domain: str = "patient_record_query"
    confidence: float = 0.5
    route_reason: str = "low_confidence_agent_loop"
    use_adaptive_routing: bool = False
    include_relevant_events: bool = True
    bypass_agent: bool = False

    @property
    def use_fast_path(self) -> bool:
        """Backward-compatible alias while the codebase finishes the rename."""
        return self.use_adaptive_routing


GENERAL_INTENT = QueryIntent(
    name="general",
    domain="health_general",
    confidence=0.45,
    route_reason="no_high_confidence_followup_intent",
)
SMALLTALK_INTENT = QueryIntent(
    name="smalltalk",
    domain="smalltalk",
    confidence=0.96,
    route_reason="deterministic_guard_smalltalk",
    use_adaptive_routing=False,
    include_relevant_events=False,
    bypass_agent=True,
)
OUT_OF_DOMAIN_INTENT = QueryIntent(
    name="out_of_domain",
    domain="out_of_domain",
    confidence=0.96,
    route_reason="deterministic_guard_out_of_domain",
    use_adaptive_routing=False,
    include_relevant_events=False,
    bypass_agent=True,
)
FOLLOWUP_INTENT = QueryIntent(
    name="medical_followup",
    domain="medical_followup",
    confidence=0.68,
    route_reason="rule_followup_requires_agent_loop",
    use_adaptive_routing=False,
    include_relevant_events=True,
)
LATEST_VISIT_INTENT = QueryIntent(
    name="latest_visit",
    domain="patient_record_query",
    confidence=0.9,
    route_reason="rule_latest_visit",
    use_adaptive_routing=True,
    include_relevant_events=False,
)
PATIENT_PROFILE_INTENT = QueryIntent(
    name="patient_profile",
    domain="patient_record_query",
    confidence=0.9,
    route_reason="rule_patient_profile",
    use_adaptive_routing=True,
    include_relevant_events=False,
)
MEDICAL_CASE_INTENT = QueryIntent(
    name="medical_case",
    domain="patient_record_query",
    confidence=0.9,
    route_reason="rule_medical_case",
    use_adaptive_routing=True,
    include_relevant_events=False,
)
FOLLOW_UP_PLAN_INTENT = QueryIntent(
    name="follow_up_plan",
    domain="medical_followup",
    confidence=0.9,
    route_reason="rule_follow_up_plan",
    use_adaptive_routing=True,
    include_relevant_events=False,
)
MEDICATION_REMINDER_INTENT = QueryIntent(
    name="medication_reminder",
    domain="medical_followup",
    confidence=0.9,
    route_reason="rule_medication_reminder",
    use_adaptive_routing=True,
    include_relevant_events=False,
)

SMALLTALK_KEYWORDS = (
    "你好",
    "您好",
    "谢谢",
    "感谢",
    "你能做什么",
    "怎么用",
    "如何使用",
    "help",
    "hello",
    "hi",
)
OUT_OF_DOMAIN_KEYWORDS = (
    "天气",
    "股票",
    "基金",
    "旅游",
    "机票",
    "酒店",
    "写代码",
    "编程",
    "论文",
    "翻译",
    "做饭",
    "菜谱",
    "电影",
    "小说",
)
FOLLOWUP_KEYWORDS = (
    "随访",
    "复查",
    "复诊计划",
    "用药提醒",
    "服药提醒",
    "吃药",
    "停药",
    "改药",
    "胸痛",
    "呼吸困难",
    "过敏",
)

INTENT_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "latest_visit": (
        "总结最近一次复诊重点",
        "看一下上次复查说了什么",
        "最近一次就诊记录摘要",
        "上一次心内科复诊重点",
    ),
    "medical_case": (
        "整理病历摘要",
        "总结患者最近病历",
        "查看诊断和治疗计划",
    ),
    "follow_up_plan": (
        "看看下一步随访安排",
        "列出复查计划",
        "患者接下来什么时候复诊",
    ),
    "medication_reminder": (
        "梳理用药提醒",
        "看一下服药安排",
        "整理吃药注意事项",
    ),
    "patient_profile": (
        "查询患者基本信息",
        "看一下患者概览",
        "患者资料摘要",
    ),
}

INTENT_TEMPLATE: dict[str, QueryIntent] = {
    "latest_visit": LATEST_VISIT_INTENT,
    "medical_case": MEDICAL_CASE_INTENT,
    "follow_up_plan": FOLLOW_UP_PLAN_INTENT,
    "medication_reminder": MEDICATION_REMINDER_INTENT,
    "patient_profile": PATIENT_PROFILE_INTENT,
}


def detect_query_intent(
    query: str,
    *,
    has_images: bool,
) -> QueryIntent:
    if has_images:
        return QueryIntent(
            name="image_review",
            domain="medical_followup",
            confidence=0.72,
            route_reason="image_request_requires_full_agent_loop",
            use_adaptive_routing=False,
            include_relevant_events=True,
        )

    lowered = query.lower()
    compact_query = query.strip().lower()
    if compact_query and any(keyword in compact_query for keyword in SMALLTALK_KEYWORDS):
        return SMALLTALK_INTENT
    if any(keyword in compact_query for keyword in OUT_OF_DOMAIN_KEYWORDS):
        return OUT_OF_DOMAIN_INTENT
    if any(keyword in lowered for keyword in FOLLOW_UP_PLAN_KEYWORDS):
        return _build_intent(
            name="follow_up_plan",
            domain="medical_followup",
            adaptive_keywords=FOLLOW_UP_PLAN_KEYWORDS,
            query=query,
            lowered_query=lowered,
        )
    if any(keyword in lowered for keyword in MEDICATION_REMINDER_KEYWORDS):
        return _build_intent(
            name="medication_reminder",
            domain="medical_followup",
            adaptive_keywords=MEDICATION_REMINDER_KEYWORDS,
            query=query,
            lowered_query=lowered,
        )
    if any(keyword in lowered for keyword in LATEST_VISIT_KEYWORDS):
        return _build_intent(
            name="latest_visit",
            domain="patient_record_query",
            adaptive_keywords=ADAPTIVE_LATEST_VISIT_KEYWORDS,
            query=query,
            lowered_query=lowered,
        )
    if any(keyword in lowered for keyword in PATIENT_PROFILE_KEYWORDS):
        return _build_intent(
            name="patient_profile",
            domain="patient_record_query",
            adaptive_keywords=ADAPTIVE_PATIENT_PROFILE_KEYWORDS,
            query=query,
            lowered_query=lowered,
        )
    if any(keyword in lowered for keyword in MEDICAL_CASE_KEYWORDS):
        return _build_intent(
            name="medical_case",
            domain="patient_record_query",
            adaptive_keywords=ADAPTIVE_MEDICAL_CASE_KEYWORDS,
            query=query,
            lowered_query=lowered,
        )
    if any(keyword in compact_query for keyword in FOLLOWUP_KEYWORDS):
        return FOLLOWUP_INTENT
    semantic_intent = _semantic_intent_match(query)
    if semantic_intent is not None:
        return semantic_intent
    return GENERAL_INTENT


def _build_intent(
    *,
    name: str,
    domain: str,
    adaptive_keywords: tuple[str, ...],
    query: str,
    lowered_query: str,
) -> QueryIntent:
    use_adaptive_routing = any(
        keyword in lowered_query for keyword in adaptive_keywords
    ) and not any(marker in query for marker in COMPLEX_QUERY_MARKERS)
    return QueryIntent(
        name=name,
        domain=domain,
        confidence=0.92 if use_adaptive_routing else 0.78,
        route_reason=(
            f"rule_{name}_adaptive"
            if use_adaptive_routing
            else f"rule_{name}_complex_agent_loop"
        ),
        use_adaptive_routing=use_adaptive_routing,
        include_relevant_events=False,
    )


def _semantic_intent_match(query: str) -> QueryIntent | None:
    normalized_query = _normalize_for_similarity(query)
    if not normalized_query:
        return None

    best_intent_name = ""
    best_score = 0.0
    for intent_name, prototypes in INTENT_PROTOTYPES.items():
        for prototype in prototypes:
            score = SequenceMatcher(
                None,
                normalized_query,
                _normalize_for_similarity(prototype),
            ).ratio()
            if score > best_score:
                best_score = score
                best_intent_name = intent_name

    if best_score < 0.58 or best_intent_name not in INTENT_TEMPLATE:
        return None

    template = INTENT_TEMPLATE[best_intent_name]
    use_adaptive = best_score >= 0.68
    return QueryIntent(
        name=template.name,
        domain=template.domain,
        confidence=round(min(best_score, 0.86), 2),
        route_reason=(
            f"semantic_prototype_match:{best_intent_name}"
            if use_adaptive
            else f"semantic_low_confidence_llm_classifier_fallback:{best_intent_name}"
        ),
        use_adaptive_routing=use_adaptive,
        include_relevant_events=not use_adaptive,
    )


def _normalize_for_similarity(value: str) -> str:
    normalized = re.sub(r"P\d{4,}", "", value.upper())
    normalized = re.sub(r"[\s，。！？、,.!?：:；;（）()【】\[\]“”\"']", "", normalized)
    return normalized.lower()

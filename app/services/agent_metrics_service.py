from __future__ import annotations

from math import ceil
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentRunMetric


def create_agent_run_metric(db: Session, **payload) -> AgentRunMetric:
    metric = AgentRunMetric(**payload)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def list_recent_agent_run_metrics(db: Session, limit: int = 50) -> list[AgentRunMetric]:
    stmt = (
        select(AgentRunMetric)
        .order_by(AgentRunMetric.created_at.desc(), AgentRunMetric.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def build_agent_ops_overview(
    metrics: list[AgentRunMetric],
    *,
    recent_limit: int = 5,
) -> dict:
    window_size = len(metrics)
    successful_runs = [metric for metric in metrics if metric.status == "success"]
    successful_durations = [
        metric.total_duration_ms
        for metric in successful_runs
        if metric.total_duration_ms is not None
    ]
    total_tool_calls = sum(metric.tool_count for metric in metrics)
    total_blocked_tools = sum(metric.tool_blocked_count for metric in metrics)
    successful_tool_calls = sum(
        max(metric.tool_count - metric.tool_error_count - metric.tool_blocked_count, 0)
        for metric in metrics
    )
    fast_path_durations = [
        metric.total_duration_ms for metric in successful_runs if metric.fast_path
    ]
    full_agent_durations = [
        metric.total_duration_ms
        for metric in successful_runs
        if metric.execution_mode == "agent"
    ]
    risk_escalation_count = sum(
        1 for metric in metrics if getattr(metric, "risk_level", None) in {"high", "urgent"}
    )
    adaptive_route_count = sum(
        1
        for metric in metrics
        if getattr(metric, "route_type", None) in {"semantic_cache", "tool_direct"}
        or getattr(metric, "fast_path", False)
    )
    semantic_cache_count = sum(
        1 for metric in metrics if getattr(metric, "route_type", None) == "semantic_cache"
    )
    agent_loop_count = sum(
        1
        for metric in metrics
        if getattr(metric, "route_type", None) == "agent_loop"
        or getattr(metric, "execution_mode", None) == "agent"
    )
    cache_invalid_count = sum(
        1
        for metric in metrics
        if "evidence_source_version_changed"
        in str(getattr(metric, "fallback_reason", "") or "")
    )
    low_confidence_count = sum(
        1 for metric in metrics if int(getattr(metric, "intent_confidence", 0) or 0) < 68
    )
    risk_guard_count = sum(
        1 for metric in metrics if getattr(metric, "route_type", None) == "risk_guard"
    )

    summary = {
        "window_size": window_size,
        "success_rate": _safe_rate(len(successful_runs), window_size),
        "avg_total_duration_ms": _safe_average(successful_durations),
        "p50_total_duration_ms": _percentile(successful_durations, 50),
        "p95_total_duration_ms": _percentile(successful_durations, 95),
        "fast_path_hit_rate": _safe_rate(adaptive_route_count, window_size),
        "high_frequency_acceleration_rate": _safe_rate(adaptive_route_count, window_size),
        "adaptive_route_hit_rate": _safe_rate(adaptive_route_count, window_size),
        "semantic_cache_hit_rate": _safe_rate(semantic_cache_count, window_size),
        "evidence_cache_invalid_rate": _safe_rate(cache_invalid_count, window_size),
        "embedding_cache_hit_rate": _safe_rate(
            sum(
                1
                for metric in metrics
                if getattr(metric, "cache_match_strategy", None) == "embedding"
                and getattr(metric, "cache_hit", False)
            ),
            window_size,
        ),
        "string_cache_fallback_rate": _safe_rate(
            sum(
                1
                for metric in metrics
                if getattr(metric, "cache_match_strategy", None) == "string_fallback"
            ),
            window_size,
        ),
        "agent_loop_fallback_rate": _safe_rate(agent_loop_count, window_size),
        "avg_latency_saved_ms": _safe_average(
            getattr(metric, "latency_saved_ms", 0) for metric in metrics
        ),
        "low_confidence_intent_rate": _safe_rate(low_confidence_count, window_size),
        "risk_guard_block_count": risk_guard_count,
        "identity_verification_rate": _safe_rate(
            sum(1 for metric in metrics if metric.identity_verified),
            window_size,
        ),
        "memory_fallback_rate": _safe_rate(
            sum(1 for metric in metrics if metric.used_memory_fallback),
            window_size,
        ),
        "memory_refresh_rate": _safe_rate(
            sum(1 for metric in metrics if metric.memory_refresh_scheduled),
            window_size,
        ),
        "tool_success_rate": _safe_rate(successful_tool_calls, total_tool_calls),
        "privacy_block_rate": _safe_rate(total_blocked_tools, total_tool_calls),
        "risk_escalation_count": risk_escalation_count,
        "risk_escalation_rate": _safe_rate(risk_escalation_count, window_size),
        "smalltalk_rate": _safe_rate(
            sum(1 for metric in metrics if metric.intent == "smalltalk"),
            window_size,
        ),
        "out_of_domain_rate": _safe_rate(
            sum(1 for metric in metrics if metric.intent == "out_of_domain"),
            window_size,
        ),
        "fast_path_avg_duration_ms": _safe_average(fast_path_durations),
        "full_agent_avg_duration_ms": _safe_average(full_agent_durations),
        "avg_tool_count": _safe_average(metric.tool_count for metric in metrics),
        "stage_breakdown_avg_ms": {
            "patient_resolution_ms": _safe_average(
                metric.patient_resolution_ms for metric in successful_runs
            ),
            "memory_context_ms": _safe_average(
                metric.memory_context_ms for metric in successful_runs
            ),
            "agent_execution_ms": _safe_average(
                metric.agent_execution_ms for metric in successful_runs
            ),
            "persistence_ms": _safe_average(metric.persistence_ms for metric in successful_runs),
        },
    }

    return {
        "summary": summary,
        "recent_runs": [
            {
                "run_id": metric.run_id,
                "patient_code": metric.patient_code,
                "intent": metric.intent,
                "status": metric.status,
                "execution_mode": metric.execution_mode,
                "route_type": getattr(metric, "route_type", None),
                "route_reason": getattr(metric, "route_reason", None),
                "intent_confidence": round(
                    int(getattr(metric, "intent_confidence", 0) or 0) / 100,
                    2,
                ),
                "cache_hit": bool(getattr(metric, "cache_hit", False)),
                "cache_match_strategy": getattr(metric, "cache_match_strategy", None),
                "cache_similarity_score": (
                    round(int(getattr(metric, "cache_similarity_score", 0) or 0) / 100, 2)
                    if getattr(metric, "cache_similarity_score", None) is not None
                    else None
                ),
                "latency_saved_ms": int(getattr(metric, "latency_saved_ms", 0) or 0),
                "fast_path": metric.fast_path,
                "identity_verified": metric.identity_verified,
                "used_memory_fallback": metric.used_memory_fallback,
                "tool_count": metric.tool_count,
                "tool_blocked_count": metric.tool_blocked_count,
                "risk_level": getattr(metric, "risk_level", None),
                "total_duration_ms": metric.total_duration_ms,
                "created_at": metric.created_at,
            }
            for metric in metrics[:recent_limit]
        ],
    }


def get_agent_ops_overview(
    db: Session,
    *,
    limit: int = 50,
    recent_limit: int = 5,
) -> dict:
    metrics = list_recent_agent_run_metrics(db, limit=limit)
    return build_agent_ops_overview(metrics, recent_limit=recent_limit)


def _safe_average(values: Iterable[int]) -> int:
    materialized = [int(value) for value in values]
    if not materialized:
        return 0
    return round(sum(materialized) / len(materialized))


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, ceil((percentile / 100) * len(ordered)))
    return ordered[rank - 1]

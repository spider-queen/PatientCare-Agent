from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes import agent as agent_route
from app.main import app
from app.services import agent_metrics_service


DEMO_ACCESS_HEADERS = {
    "X-Agent-Demo-Context": "true",
    "X-Agent-Actor-Role": "clinician",
    "X-Agent-Access-Purpose": "follow_up_care",
    "X-Agent-Operator-Id": "demo-clinician",
    "X-Agent-Tenant-Id": "demo-tenant",
}


def test_build_agent_ops_overview_aggregates_metrics():
    metrics = [
        SimpleNamespace(
            run_id="run-3",
            patient_code="P0001",
            intent="latest_visit",
            status="success",
            execution_mode="tool_direct",
            route_type="tool_direct",
            route_reason="rule_latest_visit_adaptive; structured tool direct route",
            cache_match_strategy="embedding",
            cache_similarity_score=0,
            intent_confidence=92,
            cache_hit=False,
            latency_saved_ms=800,
            fallback_reason=None,
            has_images=False,
            fast_path=True,
            identity_verified=True,
            used_relevant_events=False,
            used_memory_fallback=False,
            memory_refresh_scheduled=False,
            planner_candidate_count=0,
            tool_count=2,
            tool_error_count=0,
            tool_blocked_count=0,
            fallback_count=1,
            total_duration_ms=420,
            patient_resolution_ms=20,
            memory_context_ms=0,
            agent_execution_ms=300,
            persistence_ms=30,
            error_detail=None,
            created_at=datetime(2026, 4, 22, 10, 3, 0),
        ),
        SimpleNamespace(
            run_id="run-2",
            patient_code="P0001",
            intent="latest_visit",
            status="success",
            execution_mode="agent",
            route_type="agent_loop",
            route_reason="low_confidence_agent_loop",
            cache_match_strategy=None,
            cache_similarity_score=None,
            intent_confidence=45,
            cache_hit=False,
            latency_saved_ms=0,
            fallback_reason="low_confidence_agent_loop",
            has_images=False,
            fast_path=False,
            identity_verified=True,
            used_relevant_events=False,
            used_memory_fallback=True,
            memory_refresh_scheduled=True,
            planner_candidate_count=1,
            tool_count=3,
            tool_error_count=1,
            tool_blocked_count=0,
            fallback_count=2,
            total_duration_ms=980,
            patient_resolution_ms=35,
            memory_context_ms=40,
            agent_execution_ms=780,
            persistence_ms=45,
            error_detail=None,
            created_at=datetime(2026, 4, 22, 10, 2, 0),
        ),
    ]

    overview = agent_metrics_service.build_agent_ops_overview(metrics, recent_limit=2)

    assert overview["summary"]["window_size"] == 2
    assert overview["summary"]["p50_total_duration_ms"] == 420
    assert overview["summary"]["p95_total_duration_ms"] == 980
    assert overview["summary"]["fast_path_hit_rate"] == 50.0
    assert overview["summary"]["high_frequency_acceleration_rate"] == 50.0
    assert overview["summary"]["adaptive_route_hit_rate"] == 50.0
    assert overview["summary"]["agent_loop_fallback_rate"] == 50.0
    assert overview["summary"]["avg_latency_saved_ms"] == 400
    assert overview["summary"]["tool_success_rate"] == 80.0
    assert overview["summary"]["privacy_block_rate"] == 0.0
    assert overview["summary"]["risk_escalation_count"] == 0
    assert overview["summary"]["smalltalk_rate"] == 0.0
    assert overview["summary"]["memory_fallback_rate"] == 50.0
    assert overview["summary"]["stage_breakdown_avg_ms"]["agent_execution_ms"] == 540
    assert overview["recent_runs"][0]["run_id"] == "run-3"


def test_agent_query_records_runtime_metric(monkeypatch):
    captured_metrics = []

    class FakeQwenClient:
        def __init__(self):
            pass

    class FakeAgent:
        def __init__(self, db, llm_client):
            pass

        def run(self, **kwargs):
            raise AssertionError("fast path should bypass full agent.run")

    monkeypatch.setattr(agent_route, "QwenClient", FakeQwenClient)
    monkeypatch.setattr(agent_route, "QwenMCPAgent", FakeAgent)
    monkeypatch.setattr(
        agent_route.conversation_memory_service,
        "create_conversation_memory",
        lambda db, payload: None,
    )
    monkeypatch.setattr(
        agent_route.conversation_memory_service,
        "count_conversation_memories",
        lambda db, patient_id: 2,
    )
    monkeypatch.setattr(
        agent_route.agent_metrics_service,
        "create_agent_run_metric",
        lambda db, **payload: captured_metrics.append(payload),
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结最近一次就诊记录",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
        )

    assert response.status_code == 200
    assert len(captured_metrics) == 1
    metric = captured_metrics[0]
    assert metric["intent"] == "latest_visit"
    assert metric["fast_path"] is True
    assert metric["route_type"] in {"tool_direct", "semantic_cache"}
    assert metric["execution_mode"] in {"tool_direct", "semantic_cache"}
    assert metric["cache_match_strategy"] in {"embedding", "string_fallback", None}
    assert metric["cache_similarity_score"] >= 0.0
    assert metric["planner_candidate_count"] == 0
    assert metric["tool_count"] == 1
    assert metric["identity_verified"] is False
    assert metric["intent_confidence"] >= 68
    assert metric["total_duration_ms"] >= 0

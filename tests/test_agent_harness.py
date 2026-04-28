import json
from datetime import datetime
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.routes import agent as agent_route
from app.db.models import SemanticEvidenceCache
from app.db.session import SessionLocal
from app.llm.agent_state import AgentRunState
from app.llm.query_intents import detect_query_intent
from app.llm.qwen_mcp_agent import QwenMCPAgent
from app.main import app


DEMO_ACCESS_HEADERS = {
    "X-Agent-Demo-Context": "true",
    "X-Agent-Actor-Role": "clinician",
    "X-Agent-Access-Purpose": "follow_up_care",
    "X-Agent-Operator-Id": "demo-clinician",
    "X-Agent-Tenant-Id": "demo-tenant",
}


class MockLLM:
    def __init__(
        self,
        *,
        planner_contents: list[str],
        tool_responses: list[dict],
        final_content: str = "final answer",
    ) -> None:
        self.planner_contents = list(planner_contents)
        self.tool_responses = list(tool_responses)
        self.final_content = final_content

    def complete(self, messages, temperature=0):
        system_prompt = messages[0]["content"]
        if "planning layer" in system_prompt:
            return {"content": self.planner_contents.pop(0)}
        return {"content": self.final_content}

    def complete_with_tools(self, messages, tools, tool_choice="auto", temperature=0):
        return self.tool_responses.pop(0)


def _tool_call_response(name: str, arguments: dict, tool_call_id: str = "tool-1") -> dict:
    return {
        "content": "",
        "assistant_message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            ],
        },
        "tool_calls": [{"id": tool_call_id, "name": name, "arguments": arguments}],
        "raw_response": {},
    }


def _final_model_response(content: str = "draft answer") -> dict:
    return {
        "content": content,
        "assistant_message": {"role": "assistant", "content": content, "tool_calls": []},
        "tool_calls": [],
        "raw_response": {},
    }


def _build_run_state(**overrides) -> AgentRunState:
    execution_plan = {
        "objective": "Answer the patient question.",
        "need_identity_verification": True,
        "image_reasoning": False,
        "tool_sequence": ["verify_patient_identity", "get_patient_visit_records"],
        "steps": ["Verify identity", "Fetch the latest visit"],
        "final_answer_focus": ["Direct answer"],
    }
    current_patient_context = {
        "patient_id": 1,
        "patient_code": "P0001",
        "phone": "13800000001",
        "id_number": "310101198803121234",
    }
    current_patient_context.update(overrides.pop("current_patient_context", {}))
    state = AgentRunState.from_execution_plan(
        run_id="run-test",
        execution_plan=execution_plan,
        current_patient_context=current_patient_context,
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def _clear_evidence_cache(patient_code: str, intent: str) -> None:
    db = SessionLocal()
    try:
        patient = agent_route.patient_service.get_patient_by_code(db, patient_code)
        if patient is None:
            return
        (
            db.query(SemanticEvidenceCache)
            .filter(SemanticEvidenceCache.patient_id == patient.id)
            .filter(SemanticEvidenceCache.intent == intent)
            .delete()
        )
        db.commit()
    finally:
        db.close()


def test_parse_plan_candidate_falls_back_for_invalid_json():
    agent = QwenMCPAgent(db=Mock(), llm_client=Mock())

    plan, fallback_reasons = agent._parse_plan_candidate("not valid json")

    assert "planner_candidate_invalid_json" in fallback_reasons
    assert plan["objective"] == "Complete the patient request safely with tool-backed evidence."


def test_merge_plan_candidates_filters_unknown_tools():
    agent = QwenMCPAgent(db=Mock(), llm_client=Mock())

    merged_plan, merge_debug = agent._merge_plan_candidates(
        candidates=[
            {
                "objective": "Fetch patient data",
                "need_identity_verification": True,
                "image_reasoning": False,
                "tool_sequence": ["verify_patient_identity", "unknown_tool"],
                "steps": ["step a"],
                "final_answer_focus": ["focus a"],
            }
        ],
        has_images=False,
    )

    assert merged_plan["tool_sequence"] == ["verify_patient_identity"]
    assert merge_debug["filtered_unknown_tools"] == ["unknown_tool"]


def test_patient_context_message_prevents_missing_identity_prompt():
    agent = QwenMCPAgent(db=Mock(), llm_client=Mock())

    messages = agent._build_patient_context_messages(
        {
            "patient_id": 1,
            "patient_code": "P0001",
            "phone": "13800000001",
            "id_number": "310101198803121234",
            "full_name": "Test User",
        }
    )

    assert len(messages) == 1
    assert "Do not reply that identity information is missing" in messages[0]["content"]


def test_recent_visit_query_injects_limit_one():
    agent = QwenMCPAgent(db=Mock(), llm_client=Mock())
    agent.tools["get_patient_visit_records"] = lambda **kwargs: kwargs
    state = _build_run_state(identity_verified=True)

    tool_output = agent._execute_tool_call(
        tool_name="get_patient_visit_records",
        arguments={},
        user_query="请总结患者 P0001 最近一次就诊情况",
        run_state=state,
    )

    assert tool_output["arguments"]["patient_id"] == 1
    assert tool_output["arguments"]["patient_code"] == "P0001"
    assert tool_output["arguments"]["limit"] == 1


def test_private_tool_blocked_before_clinician_access_context():
    agent = QwenMCPAgent(db=Mock(), llm_client=Mock())
    agent.tools["get_patient_visit_records"] = lambda **kwargs: {"found": True}
    state = _build_run_state(identity_verified=False)

    tool_output = agent._execute_tool_call(
        tool_name="get_patient_visit_records",
        arguments={"patient_code": "P0001"},
        user_query="请查看患者 P0001 最近一次就诊",
        run_state=state,
    )

    assert tool_output["result"]["allowed"] is False
    assert tool_output["result"]["error"] == (
        "clinician follow-up context or identity verification required before accessing private patient data"
    )
    assert "private_tool_blocked_before_clinician_access" in state.fallback_reasons


def test_agent_run_returns_execution_trace_and_run_id():
    llm = MockLLM(
        planner_contents=["not-json"],
        tool_responses=[_final_model_response("draft answer")],
        final_content="final answer",
    )
    agent = QwenMCPAgent(db=Mock(), llm_client=llm)

    result = agent.run(
        user_query="普通咨询",
        debug_planner=True,
        run_id="run-123",
    )

    assert result["run_id"] == "run-123"
    assert result["answer"] == "final answer"
    assert result["execution_trace"]["run_id"] == "run-123"
    assert result["execution_trace"]["planner"]["candidate_count"] == 1
    assert "planner_candidate_invalid_json" in result["execution_trace"]["planner"][
        "fallback_reasons"
    ]


def test_detect_query_intent_for_latest_visit_uses_adaptive_routing():
    intent = detect_query_intent("请总结患者 P0001 最近一次就诊记录", has_images=False)

    assert intent.name == "latest_visit"
    assert intent.use_adaptive_routing is True
    assert intent.include_relevant_events is False


def test_detect_query_intent_for_constrained_visit_query_disables_adaptive_routing():
    intent = detect_query_intent("请总结 P0001 最近一次消化内科复诊的重点", has_images=False)

    assert intent.name == "latest_visit"
    assert intent.use_adaptive_routing is False
    assert intent.include_relevant_events is False


def test_agent_query_adaptive_tool_direct_skips_full_agent(monkeypatch):
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
    payload = response.json()
    assert payload["run_id"].startswith("agent-")
    assert payload["route_type"] in {"tool_direct", "semantic_cache"}
    assert payload["execution_trace"]["adaptive_evidence_routing"] is True
    assert payload["execution_trace"]["intent"] == "latest_visit"
    assert payload["intent_confidence"] >= 0.68
    assert payload["tool_outputs"][-1]["arguments"]["limit"] == 1


def test_build_memory_context_skips_relevant_event_search_when_disabled(monkeypatch):
    patient = Mock(id=1)
    monkeypatch.setattr(
        agent_route.conversation_memory_service,
        "list_recent_conversation_memories",
        lambda db, patient_id, limit: [],
    )
    monkeypatch.setattr(agent_route.memory_service, "get_user_profile", lambda db, patient_id: None)

    def fail_if_called(**kwargs):
        raise AssertionError("relevant event search should be skipped")

    monkeypatch.setattr(
        agent_route.memory_service,
        "get_relevant_memory_search_results",
        fail_if_called,
    )

    context, debug = agent_route._build_memory_context(
        db=Mock(),
        patient=patient,
        query="请查询患者 P0001 基本信息",
        include_relevant_events=False,
    )

    assert context["relevant_events"] == []
    assert debug["include_relevant_events"] is False
    assert debug["result_count"] == 0


def test_agent_query_schedules_background_memory_refresh(monkeypatch):
    captured_triggers = []

    class FakeQwenClient:
        def __init__(self):
            pass

    class FakeAgent:
        def __init__(self, db, llm_client):
            pass

        def run(self, **kwargs):
            run_id = kwargs["run_id"]
            return {
                "answer": "ok",
                "tool_outputs": [
                    {
                        "tool_name": "verify_patient_identity",
                        "arguments": {"patient_code": "P0001", "phone": "13800000001"},
                        "result": {
                            "verified": True,
                            "patient": {"id": 1, "patient_code": "P0001"},
                        },
                    }
                ],
                "run_id": run_id,
                "execution_trace": {
                    "run_id": run_id,
                    "planner": {"fallback_reasons": []},
                    "state": {},
                    "tool_sequence": [],
                },
                "planner_debug": {},
            }

    monkeypatch.setattr(agent_route, "QwenClient", FakeQwenClient)
    monkeypatch.setattr(agent_route, "QwenMCPAgent", FakeAgent)
    monkeypatch.setattr(
        agent_route,
        "_build_memory_context",
        lambda db, patient, query, include_relevant_events=True: ({}, {}),
    )
    monkeypatch.setattr(
        agent_route.conversation_memory_service,
        "create_conversation_memory",
        lambda db, payload: None,
    )
    monkeypatch.setattr(
        agent_route.conversation_memory_service,
        "count_conversation_memories",
        lambda db, patient_id: agent_route.SHORT_TERM_TRIGGER_MESSAGE_COUNT,
    )
    monkeypatch.setattr(
        agent_route.memory_refresh_service,
        "refresh_conversation_memory_for_trigger",
        lambda trigger: captured_triggers.append(trigger),
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结患者 P0001 最近一次就诊",
            "images": [],
            "debug_planner": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["memory_refresh_scheduled"] is True
    assert payload["run_id"].startswith("agent-")
    assert captured_triggers
    assert captured_triggers[0].patient_id == 1


def test_detect_query_intent_for_patient_profile_uses_acceleration():
    intent = detect_query_intent("请查询患者 P0001 的基本信息", has_images=False)

    assert intent.name == "patient_profile"
    assert intent.use_adaptive_routing is True
    assert intent.include_relevant_events is False


def test_detect_query_intent_for_medical_case_uses_acceleration():
    intent = detect_query_intent("请总结患者 P0001 的病历摘要", has_images=False)

    assert intent.name == "medical_case"
    assert intent.use_adaptive_routing is True
    assert intent.include_relevant_events is False


def test_agent_query_patient_profile_adaptive_route_skips_full_agent(monkeypatch):
    class FakeQwenClient:
        def __init__(self):
            pass

    class FakeAgent:
        def __init__(self, db, llm_client):
            pass

        def run(self, **kwargs):
            raise AssertionError("high-frequency acceleration should bypass full agent.run")

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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请查询患者基本信息",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route_type"] in {"tool_direct", "semantic_cache"}
    assert payload["execution_trace"]["intent"] == "patient_profile"
    assert payload["tool_outputs"][-1]["tool_name"] == "get_patient_profile"


def test_agent_query_medical_case_adaptive_route_skips_full_agent(monkeypatch):
    class FakeQwenClient:
        def __init__(self):
            pass

    class FakeAgent:
        def __init__(self, db, llm_client):
            pass

        def run(self, **kwargs):
            raise AssertionError("high-frequency acceleration should bypass full agent.run")

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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结患者的病历摘要",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route_type"] in {"tool_direct", "semantic_cache"}
    assert payload["execution_trace"]["intent"] == "medical_case"
    assert payload["tool_outputs"][-1]["tool_name"] == "get_patient_medical_cases"


def test_agent_query_force_full_agent_bypasses_adaptive_route(monkeypatch):
    captured_runs = []

    class FakeQwenClient:
        def __init__(self):
            pass

    class FakeAgent:
        def __init__(self, db, llm_client):
            pass

        def run(self, **kwargs):
            captured_runs.append(kwargs)
            run_id = kwargs["run_id"]
            return {
                "answer": "forced full agent",
                "tool_outputs": [
                    {
                        "tool_name": "verify_patient_identity",
                        "arguments": {"patient_code": "P0001", "phone": "13800000001"},
                        "result": {
                            "verified": True,
                            "patient": {"id": 1, "patient_code": "P0001"},
                        },
                    },
                    {
                        "tool_name": "get_patient_visit_records",
                        "arguments": {"patient_id": 1, "patient_code": "P0001", "limit": 1},
                        "result": {
                            "found": True,
                            "patient": {"id": 1, "patient_code": "P0001"},
                            "visit_records": [],
                        },
                    },
                ],
                "run_id": run_id,
                "runtime_metrics": {
                    "execution_mode": "agent",
                    "planner_candidate_count": 1,
                    "fallback_count": 0,
                },
                "execution_trace": {
                    "run_id": run_id,
                    "planner": {"fallback_reasons": []},
                    "state": {},
                    "tool_sequence": [],
                },
                "planner_debug": {},
            }

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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结患者 P0001 最近一次就诊记录",
            "images": [],
            "debug_planner": True,
            "force_full_agent": True,
            "identity_verification": {"phone": "13800000001"},
        },
    )

    assert response.status_code == 200
    assert len(captured_runs) == 1
    assert captured_runs[0]["run_id"].startswith("agent-")
    payload = response.json()
    assert payload["answer"] == "forced full agent"
    assert payload["execution_trace"]["runtime"]["execution_mode"] == "agent"
    assert payload["execution_trace"]["runtime"]["force_full_agent"] is True


def test_agent_query_without_identity_verification_uses_clinician_adaptive_route(monkeypatch):
    captured_runs = []

    class FakeQwenClient:
        def __init__(self):
            pass

    class FakeAgent:
        def __init__(self, db, llm_client):
            pass

        def run(self, **kwargs):
            captured_runs.append(kwargs)
            return {
                "answer": "identity required",
                "tool_outputs": [
                    {
                        "tool_name": "get_patient_visit_records",
                        "arguments": {"patient_code": "P0001"},
                        "result": {
                            "allowed": False,
                            "error": "identity verification required before accessing private patient data",
                        },
                    }
                ],
                "run_id": kwargs["run_id"],
                "runtime_metrics": {"execution_mode": "agent"},
                "execution_trace": None,
                "planner_debug": None,
            }

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
        lambda db, **payload: None,
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
    assert captured_runs == []
    payload = response.json()
    assert payload["route_type"] in {"tool_direct", "semantic_cache"}
    assert payload["tool_outputs"][0]["tool_name"] == "get_patient_visit_records"


def test_agent_query_blocks_private_tool_when_patient_not_selected(monkeypatch):
    class FailQwenClient:
        def __init__(self):
            raise AssertionError("access check should block before LLM initialization")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
    monkeypatch.setattr(
        agent_route.agent_metrics_service,
        "create_agent_run_metric",
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        json={
            "query": "请总结最近一次就诊记录",
            "images": [],
            "debug_planner": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "active clinician follow-up context required"


def test_agent_query_ignores_forged_body_access_context(monkeypatch):
    class FailQwenClient:
        def __init__(self):
            raise AssertionError("forged body context should be rejected before LLM initialization")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
    monkeypatch.setattr(
        agent_route.agent_metrics_service,
        "create_agent_run_metric",
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        json={
            "query": "请总结最近一次就诊记录",
            "patient_code": "P0001",
            "actor_role": "clinician",
            "access_purpose": "follow_up_care",
            "images": [],
            "debug_planner": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "active clinician follow-up context required"


def test_agent_query_reuses_fresh_semantic_evidence_cache(monkeypatch):
    _clear_evidence_cache("P0001", "latest_visit")

    class FailQwenClient:
        def __init__(self):
            raise AssertionError("adaptive evidence route should bypass the LLM")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    first_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结最近一次就诊记录",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )
    second_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结最近一次就诊记录。",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["route_type"] == "tool_direct"
    assert second_response.status_code == 200
    assert second_response.json()["route_type"] == "semantic_cache"
    assert second_response.json()["cache_hit"] is True


def test_agent_query_reuses_embedding_cache_for_synonym_follow_up_plan(monkeypatch):
    _clear_evidence_cache("P0001", "follow_up_plan")

    class FailQwenClient:
        def __init__(self):
            raise AssertionError("adaptive evidence route should bypass the LLM")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    first_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请查看随访安排",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )
    second_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "下一次随访是哪天",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["route_type"] == "tool_direct"
    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["route_type"] == "semantic_cache"
    assert payload["cache_hit"] is True
    assert payload["runtime_metrics"]["cache_match_strategy"] == "embedding"
    assert payload["runtime_metrics"]["cache_similarity_score"] >= 0.78


def test_agent_query_cache_does_not_cross_patients(monkeypatch):
    _clear_evidence_cache("P0001", "follow_up_plan")
    _clear_evidence_cache("P0002", "follow_up_plan")

    class FailQwenClient:
        def __init__(self):
            raise AssertionError("adaptive evidence route should bypass the LLM")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    first_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请查看随访安排",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": False,
        },
    )
    second_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "下一次随访是哪天",
            "patient_code": "P0002",
            "images": [],
            "debug_planner": False,
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["route_type"] == "tool_direct"
    assert second_response.status_code == 200
    assert second_response.json()["route_type"] == "tool_direct"
    assert second_response.json()["cache_hit"] is False


def test_agent_query_cache_invalidates_when_source_version_changes(monkeypatch):
    _clear_evidence_cache("P0001", "latest_visit")

    class FailQwenClient:
        def __init__(self):
            raise AssertionError("adaptive evidence route should bypass the LLM")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    first_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结最近一次就诊记录",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )
    assert first_response.status_code == 200
    assert first_response.json()["route_type"] == "tool_direct"

    monkeypatch.setattr(
        agent_route,
        "_source_version_for_tool",
        lambda db, tool_name, tool_arguments: "changed-source-version",
    )

    second_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结最近一次就诊记录。",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )

    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["route_type"] == "tool_direct"
    assert payload["cache_hit"] is False
    assert "cache_miss=evidence_source_version_changed" in payload["route_reason"]


def test_agent_query_cache_uses_string_fallback_when_embedding_unavailable(monkeypatch):
    _clear_evidence_cache("P0001", "latest_visit")

    class FailQwenClient:
        def __init__(self):
            raise AssertionError("adaptive evidence route should bypass the LLM")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
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
        lambda db, **payload: None,
    )
    monkeypatch.setattr(
        agent_route.evidence_cache_service,
        "embed_query",
        lambda query: (_ for _ in ()).throw(RuntimeError("embedding unavailable")),
    )

    client = TestClient(app)
    first_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结最近一次就诊记录",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )
    second_response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结最近一次就诊记录。",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["route_type"] == "semantic_cache"
    assert payload["runtime_metrics"]["cache_match_strategy"] == "string_fallback"
    assert payload["runtime_metrics"]["cache_similarity_score"] >= 0.68


def test_agent_query_with_explicit_identity_verification_keeps_bootstrap_evidence(monkeypatch):
    class FakeQwenClient:
        def __init__(self):
            pass

    class FakeAgent:
        def __init__(self, db, llm_client):
            pass

        def run(self, **kwargs):
            raise AssertionError("verified fast path should bypass full agent.run")

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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请总结患者 P0001 最近一次就诊记录",
            "images": [],
            "debug_planner": True,
            "identity_verification": {"phone": "13800000001"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route_type"] in {"tool_direct", "semantic_cache"}
    assert payload["tool_outputs"][0]["tool_name"] == "verify_patient_identity"


def test_agent_query_patient_profile_redacts_sensitive_fields(monkeypatch):
    _clear_evidence_cache("P0001", "patient_profile")

    class FailQwenClient:
        def __init__(self):
            raise AssertionError("adaptive evidence route should bypass the LLM")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请查询患者基本信息",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": True,
        },
    )

    assert response.status_code == 200
    response_text = json.dumps(response.json(), ensure_ascii=False)
    assert "13800000001" not in response_text
    assert "310101198803121234" not in response_text
    assert "emergency_contact_phone" not in response_text
    assert "phone_masked" in response_text
    assert "id_number_masked" in response_text


def test_evidence_cache_stores_redacted_patient_profile(monkeypatch):
    _clear_evidence_cache("P0001", "patient_profile")

    class FailQwenClient:
        def __init__(self):
            raise AssertionError("adaptive evidence route should bypass the LLM")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
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
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        headers=DEMO_ACCESS_HEADERS,
        json={
            "query": "请查询患者基本信息",
            "patient_code": "P0001",
            "images": [],
            "debug_planner": False,
        },
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        patient = agent_route.patient_service.get_patient_by_code(db, "P0001")
        entry = (
            db.query(SemanticEvidenceCache)
            .filter(SemanticEvidenceCache.patient_id == patient.id)
            .filter(SemanticEvidenceCache.intent == "patient_profile")
            .order_by(SemanticEvidenceCache.id.desc())
            .first()
        )
        assert entry is not None
        assert "13800000001" not in entry.evidence
        assert "310101198803121234" not in entry.evidence
        assert "emergency_contact_phone" not in entry.evidence
    finally:
        db.close()


def test_smalltalk_uses_template_without_llm(monkeypatch):
    class FailQwenClient:
        def __init__(self):
            raise AssertionError("smalltalk should not initialize the LLM client")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
    monkeypatch.setattr(
        agent_route.agent_metrics_service,
        "create_agent_run_metric",
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        json={"query": "你好，你能做什么？", "images": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "smalltalk"
    assert payload["tool_outputs"] == []
    assert payload["runtime_metrics"]["execution_mode"] == "template"


def test_out_of_domain_uses_boundary_template_without_llm(monkeypatch):
    class FailQwenClient:
        def __init__(self):
            raise AssertionError("out-of-domain should not initialize the LLM client")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
    monkeypatch.setattr(
        agent_route.agent_metrics_service,
        "create_agent_run_metric",
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        json={"query": "帮我规划一下杭州旅游和酒店", "images": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "out_of_domain"
    assert "超出了当前助手的服务边界" in payload["answer"]
    assert payload["tool_outputs"] == []


def test_high_risk_follow_up_query_returns_conservative_guard(monkeypatch):
    class FailQwenClient:
        def __init__(self):
            raise AssertionError("high-risk guard should not initialize the LLM client")

    monkeypatch.setattr(agent_route, "QwenClient", FailQwenClient)
    monkeypatch.setattr(
        agent_route.agent_metrics_service,
        "create_agent_run_metric",
        lambda db, **payload: None,
    )
    monkeypatch.setattr(
        agent_route.mcp_tool_service,
        "create_risk_event",
        lambda db, **payload: None,
    )

    client = TestClient(app)
    response = client.post(
        "/api/agent/query",
        json={"query": "患者 P0001 复诊后胸痛并且想自行停药", "images": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] == "urgent"
    assert payload["recommended_action"]
    assert payload["tool_outputs"][0]["tool_name"] == "assess_follow_up_risk"
    assert "不适合由助手直接给出诊断" in payload["answer"]

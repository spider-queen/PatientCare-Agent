from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.llm.agent_state import AgentRunState
from app.llm.domain_skills import DomainSkillBundle, DomainSkillLoader
from app.llm.qwen_client import QwenClient
from app.services import mcp_tool_service


logger = logging.getLogger("uvicorn.error")
ToolHandler = Callable[..., dict[str, Any]]

MAX_TOOL_STEPS = 6
PLAN_TEMPERATURES = [0.1]
RECENT_VISIT_KEYWORDS = (
    "recent visit",
    "latest visit",
    "最近一次",
    "最近",
    "最新一次",
    "最新",
    "最近就诊",
)

BASE_SYSTEM_PROMPT = """
You are a clinician-facing post-discharge follow-up agent harness.

Working rules:
1. Base answers on tool results, patient context, images, and memory context only.
2. Do not invent visit records, diagnoses, or patient history.
3. For clinician workspace requests, private patient tools are allowed only when the server provides active patient context, actor_role=clinician, and access_purpose=follow_up_care. Identity verification is reserved for patient-facing flows.
4. Plan first, use only the necessary tools, then produce a concise evidence-based answer for medical staff.
5. Never expose internal chain-of-thought. Return conclusions, evidence, and needed caveats only.
""".strip()

PLANNER_PROMPT = """
You are the planning layer for a medical support agent.
Return valid JSON only.

Schema:
{
  "objective": "one sentence objective",
  "need_identity_verification": true,
  "image_reasoning": false,
  "tool_sequence": ["verify_patient_identity", "get_patient_visit_records"],
  "steps": ["step 1", "step 2"],
  "final_answer_focus": ["focus 1", "focus 2"]
}

Rules:
- Only use tools from this set:
  ["verify_patient_identity", "get_patient_profile", "get_patient_medical_cases", "get_patient_visit_records", "get_follow_up_plans", "get_medication_reminders", "assess_follow_up_risk"]
- If the request is about the latest or most recent visit, include `get_patient_visit_records`.
- If the request is about follow-up arrangements, include `get_follow_up_plans`.
- If the request is about medication reminders, include `get_medication_reminders`.
- If the request mentions chest pain, breathing difficulty, severe allergy, stopping medication, or changing medication, include `assess_follow_up_risk`.
- Do not add `verify_patient_identity` when active clinician follow-up context is already supplied by the server.
- Keep the plan minimal and executable.
""".strip()

FINALIZER_PROMPT = """
You are the final answer composer for a medical support agent.

Requirements:
1. Use only the provided tool results, images, and memory context.
2. If neither clinician follow-up access nor identity verification is present, do not reveal private patient data.
3. If evidence is insufficient, say so clearly.
4. Write for doctors, nurses, or follow-up specialists. Do not address the patient directly as "you".
5. Respond with the answer only. Do not reveal internal reasoning.
""".strip()


class QwenMCPAgent:
    def __init__(self, db: Session, llm_client: QwenClient) -> None:
        self.db = db
        self.llm_client = llm_client
        self.tools = self._build_tool_registry()
        self.skill_loader = DomainSkillLoader()

    def run(
        self,
        user_query: str,
        images: list[dict[str, Any]] | None = None,
        debug_planner: bool = False,
        memory_context: dict[str, Any] | None = None,
        current_patient_context: dict[str, Any] | None = None,
        bootstrap_tool_outputs: list[dict[str, Any]] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_run_id = run_id or f"agent-{uuid4().hex}"
        execution_plan, planner_debug = self._build_execution_plan(
            user_query=user_query,
            has_images=bool(images),
        )

        run_state = AgentRunState.from_execution_plan(
            run_id=resolved_run_id,
            execution_plan=execution_plan,
            current_patient_context=current_patient_context,
        )
        for reason in planner_debug.get("fallback_reasons", []):
            run_state.add_fallback(reason)
        if planner_debug.get("filtered_unknown_tools"):
            run_state.add_fallback("planner_unknown_tools_filtered")

        skill_bundles = self.skill_loader.select_for_request(
            user_query=user_query,
            has_images=bool(images),
            memory_context=memory_context,
            current_patient_context=current_patient_context,
        )
        for bundle in skill_bundles:
            run_state.mark_skill_loaded(bundle.name)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": BASE_SYSTEM_PROMPT},
            *self._build_skill_messages(skill_bundles),
            *self._build_patient_context_messages(current_patient_context),
            *self._build_bootstrap_tool_messages(bootstrap_tool_outputs),
            *self._build_memory_messages(memory_context),
            {"role": "system", "content": self._format_execution_state(execution_plan, run_state)},
            {"role": "user", "content": self._build_user_content(user_query, images or [])},
        ]

        tool_outputs = list(bootstrap_tool_outputs or [])
        for item in bootstrap_tool_outputs or []:
            run_state.mark_bootstrap_tool(item)

        tool_steps = 0
        while tool_steps < MAX_TOOL_STEPS:
            run_state.set_reasoning()
            response = self.llm_client.complete_with_tools(
                messages=messages,
                tools=self._tool_specs(),
                temperature=0,
            )

            if response["tool_calls"]:
                messages.append(response["assistant_message"])
                for tool_call in response["tool_calls"]:
                    tool_output = self._execute_tool_call(
                        tool_name=tool_call["name"],
                        arguments=tool_call["arguments"],
                        user_query=user_query,
                        run_state=run_state,
                    )
                    tool_outputs.append(tool_output)
                    tool_steps += 1
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": tool_call["name"],
                            "content": json.dumps(tool_output["result"], ensure_ascii=False),
                        }
                    )
                continue

            answer = self._finalize_answer(
                user_query=user_query,
                execution_plan=execution_plan,
                draft_answer=response["content"] or "",
                tool_outputs=tool_outputs,
                has_images=bool(images),
                run_state=run_state,
            )
            execution_trace = (
                self._build_execution_trace(
                    planner_debug=planner_debug,
                    run_state=run_state,
                    execution_plan=execution_plan,
                )
                if debug_planner
                else None
            )
            self._log_run_summary(run_state, tool_outputs, execution_trace)
            return {
                "answer": answer,
                "tool_outputs": tool_outputs,
                "run_id": resolved_run_id,
                "runtime_metrics": {
                    "execution_mode": "agent",
                    "planner_candidate_count": planner_debug.get("candidate_count", 0),
                    "fallback_count": len(run_state.fallback_reasons),
                    "loaded_skill_count": len(run_state.loaded_skills),
                },
                "execution_trace": execution_trace,
                "planner_debug": execution_trace,
            }

        run_state.add_fallback("max_tool_steps_reached")
        run_state.set_finalizing()
        answer = self._finalize_answer(
            user_query=user_query,
            execution_plan=execution_plan,
            draft_answer="",
            tool_outputs=tool_outputs,
            has_images=bool(images),
            run_state=run_state,
        )
        execution_trace = (
            self._build_execution_trace(
                planner_debug=planner_debug,
                run_state=run_state,
                execution_plan=execution_plan,
            )
            if debug_planner
            else None
        )
        self._log_run_summary(run_state, tool_outputs, execution_trace)
        return {
            "answer": answer,
            "tool_outputs": tool_outputs,
            "run_id": resolved_run_id,
            "runtime_metrics": {
                "execution_mode": "agent",
                "planner_candidate_count": planner_debug.get("candidate_count", 0),
                "fallback_count": len(run_state.fallback_reasons),
                "loaded_skill_count": len(run_state.loaded_skills),
            },
            "execution_trace": execution_trace,
            "planner_debug": execution_trace,
        }

    def _build_execution_plan(
        self,
        user_query: str,
        has_images: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        raw_candidates: list[dict[str, Any]] = []
        fallback_reasons: list[str] = []
        planner_user_prompt = json.dumps(
            {"user_query": user_query, "has_images": has_images},
            ensure_ascii=False,
        )

        for temperature in PLAN_TEMPERATURES:
            response = self.llm_client.complete(
                messages=[
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": planner_user_prompt},
                ],
                temperature=temperature,
            )
            parsed_candidate, candidate_fallbacks = self._parse_plan_candidate(response["content"])
            candidates.append(parsed_candidate)
            fallback_reasons.extend(candidate_fallbacks)
            raw_candidates.append(
                {
                    "temperature": temperature,
                    "raw_content": response["content"],
                    "parsed_plan": parsed_candidate,
                    "fallback_reasons": candidate_fallbacks,
                }
            )

        merged_plan, merge_debug = self._merge_plan_candidates(
            candidates=candidates,
            has_images=has_images,
        )
        fallback_reasons.extend(merge_debug["fallback_reasons"])
        return merged_plan, {
            "candidate_count": len(raw_candidates),
            "temperatures": PLAN_TEMPERATURES,
            "candidates": raw_candidates,
            "merged_plan": merged_plan,
            "filtered_unknown_tools": merge_debug["filtered_unknown_tools"],
            "fallback_reasons": fallback_reasons,
        }

    def _parse_plan_candidate(self, content: str) -> tuple[dict[str, Any], list[str]]:
        fallback_reasons: list[str] = []
        try:
            return json.loads(content), fallback_reasons
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    fallback_reasons.append("planner_candidate_wrapped_json")
                    return json.loads(content[start : end + 1]), fallback_reasons
                except json.JSONDecodeError:
                    pass
        fallback_reasons.append("planner_candidate_invalid_json")
        return self._default_execution_plan(), fallback_reasons

    def _merge_plan_candidates(
        self,
        *,
        candidates: list[dict[str, Any]],
        has_images: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        verification_votes = sum(
            1 for candidate in candidates if candidate.get("need_identity_verification")
        )
        image_votes = sum(1 for candidate in candidates if candidate.get("image_reasoning"))
        tool_scores: dict[str, int] = {}
        merged_steps: list[str] = []
        merged_focus: list[str] = []
        filtered_unknown_tools: list[str] = []

        for candidate in candidates:
            for tool_name in candidate.get("tool_sequence", []):
                if tool_name not in self.tools:
                    if tool_name not in filtered_unknown_tools:
                        filtered_unknown_tools.append(tool_name)
                    continue
                tool_scores[tool_name] = tool_scores.get(tool_name, 0) + 1
            for step in candidate.get("steps", []):
                if step not in merged_steps:
                    merged_steps.append(step)
            for focus in candidate.get("final_answer_focus", []):
                if focus not in merged_focus:
                    merged_focus.append(focus)

        ranked_tools = [
            tool_name
            for tool_name, _ in sorted(
                tool_scores.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        merged_plan = {
            "objective": candidates[0].get("objective", "Complete the patient request."),
            "need_identity_verification": verification_votes >= 2,
            "image_reasoning": has_images or image_votes >= 2,
            "tool_sequence": ranked_tools,
            "steps": merged_steps[:5] or self._default_execution_plan()["steps"],
            "final_answer_focus": merged_focus[:5]
            or self._default_execution_plan()["final_answer_focus"],
        }
        fallback_reasons = (
            ["planner_unknown_tools_filtered"] if filtered_unknown_tools else []
        )
        return merged_plan, {
            "filtered_unknown_tools": filtered_unknown_tools,
            "fallback_reasons": fallback_reasons,
        }

    def _default_execution_plan(self) -> dict[str, Any]:
        return {
            "objective": "Complete the patient request safely with tool-backed evidence.",
            "need_identity_verification": False,
            "image_reasoning": False,
            "tool_sequence": [],
            "steps": ["Analyze the request", "Use tools only when needed", "Summarize the evidence"],
            "final_answer_focus": ["Answer directly", "State evidence or limitations"],
        }

    def _execute_tool_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        user_query: str,
        run_state: AgentRunState,
    ) -> dict[str, Any]:
        normalized_arguments = self._normalize_tool_arguments(
            tool_name=tool_name,
            arguments=arguments,
            user_query=user_query,
            run_state=run_state,
        )
        safe_arguments = mcp_tool_service.sanitize_agent_payload(normalized_arguments)

        handler = self.tools.get(tool_name)
        if handler is None:
            result = {"error": f"unknown tool: {tool_name}"}
            run_state.add_fallback(f"unknown_tool:{tool_name}")
            run_state.record_tool(
                tool_name=tool_name,
                arguments=safe_arguments,
                result=result,
                duration_ms=0,
                status="error",
            )
            return {
                "tool_name": tool_name,
                "arguments": safe_arguments,
                "result": result,
            }

        if (
            run_state.private_access_required(tool_name)
            and not run_state.identity_verified
            and not run_state.clinician_follow_up_access_allowed()
        ):
            result = {
                "allowed": False,
                "error": (
                    "clinician follow-up context or identity verification required "
                    "before accessing private patient data"
                ),
            }
            run_state.add_fallback("private_tool_blocked_before_clinician_access")
            run_state.add_evidence_gap(
                "Private patient data was requested before access context was complete."
            )
            run_state.record_tool(
                tool_name=tool_name,
                arguments=safe_arguments,
                result=result,
                duration_ms=0,
                status="blocked",
            )
            return {
                "tool_name": tool_name,
                "arguments": safe_arguments,
                "result": result,
            }

        started_at = perf_counter()
        try:
            result = handler(**normalized_arguments)
            status = "ok"
        except Exception as exc:
            logger.exception(
                "agent_tool_failed run_id=%s tool_name=%s arguments=%s",
                run_state.run_id,
                tool_name,
                json.dumps(safe_arguments, ensure_ascii=False),
            )
            result = {
                "error": "tool execution failed",
                "detail": str(exc),
                "tool_name": tool_name,
            }
            status = "error"
        duration_ms = int((perf_counter() - started_at) * 1000)
        run_state.record_tool(
            tool_name=tool_name,
            arguments=safe_arguments,
            result=result,
            duration_ms=duration_ms,
            status=status,
        )
        return {
            "tool_name": tool_name,
            "arguments": safe_arguments,
            "result": result,
        }

    def _normalize_tool_arguments(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        user_query: str,
        run_state: AgentRunState,
    ) -> dict[str, Any]:
        normalized = run_state.apply_context_defaults(tool_name, arguments)
        if (
            tool_name == "get_patient_visit_records"
            and "limit" not in normalized
            and self._is_recent_visit_query(user_query)
        ):
            normalized["limit"] = 1
        if tool_name == "assess_follow_up_risk" and not normalized.get("query"):
            normalized["query"] = user_query
        return normalized

    def _is_recent_visit_query(self, user_query: str) -> bool:
        lowered = user_query.lower()
        return any(keyword in lowered for keyword in RECENT_VISIT_KEYWORDS)

    def _finalize_answer(
        self,
        *,
        user_query: str,
        execution_plan: dict[str, Any],
        draft_answer: str,
        tool_outputs: list[dict[str, Any]],
        has_images: bool,
        run_state: AgentRunState,
    ) -> str:
        run_state.set_finalizing()
        response = self.llm_client.complete(
            messages=[
                {"role": "system", "content": FINALIZER_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_query": user_query,
                            "has_images": has_images,
                            "execution_plan": execution_plan,
                            "draft_answer": draft_answer,
                            "tool_outputs": tool_outputs,
                            "run_state": run_state.snapshot(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0,
        )
        return response["content"] or draft_answer

    def _build_skill_messages(
        self,
        skill_bundles: list[DomainSkillBundle],
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for bundle in skill_bundles:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"<skill name=\"{bundle.name}\" description=\"{bundle.description}\">\n"
                        f"{bundle.content}\n"
                        "</skill>"
                    ),
                }
            )
        return messages

    def _build_memory_messages(
        self,
        memory_context: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        if not memory_context:
            return []

        memory_lines: list[str] = []
        short_term_memories = memory_context.get("short_term_memories", [])
        if short_term_memories:
            formatted = []
            for item in short_term_memories:
                role = item.get("role", "unknown")
                content = item.get("content", "")
                multimodal_payload = item.get("multimodal_payload")
                suffix = f" [multimodal: {multimodal_payload}]" if multimodal_payload else ""
                formatted.append(f"{role}: {content}{suffix}")
            memory_lines.append("Short-term conversation memory:\n" + "\n".join(formatted))

        user_profile = memory_context.get("user_profile")
        if user_profile:
            memory_lines.append(
                "Long-term user profile:\n"
                f"- profile_summary: {user_profile.get('profile_summary') or 'none'}\n"
                f"- stable_preferences: {user_profile.get('stable_preferences') or 'none'}\n"
                f"- preferred_topics: {user_profile.get('preferred_topics') or 'none'}"
            )

        relevant_events = memory_context.get("relevant_events", [])
        if relevant_events:
            formatted_events = []
            for event in relevant_events:
                formatted_events.append(
                    f"{event.get('event_time')}: {event.get('title')} - {event.get('summary') or ''}"
                )
            memory_lines.append("Relevant memory events:\n" + "\n".join(formatted_events))

        if not memory_lines:
            return []
        return [{"role": "system", "content": "\n\n".join(memory_lines)}]

    def _build_patient_context_messages(
        self,
        current_patient_context: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        if not current_patient_context:
            return []

        lines = ["The server already resolved the active clinician workspace context."]
        for key in ("patient_id", "full_name", "patient_code", "actor_role", "access_purpose"):
            value = current_patient_context.get(key)
            if value:
                lines.append(f"- {key}: {value}")
        lines.append(
            "For actor_role=clinician and access_purpose=follow_up_care, use structured patient tools directly when needed."
        )
        lines.append(
            "Do not reply that identity information is missing when server-side clinician context is present."
        )
        return [{"role": "system", "content": "\n".join(lines)}]

    def _build_bootstrap_tool_messages(
        self,
        bootstrap_tool_outputs: list[dict[str, Any]] | None,
    ) -> list[dict[str, str]]:
        if not bootstrap_tool_outputs:
            return []

        lines = [
            "The server already executed these tools before the model turn.",
            "Treat them as trusted evidence and continue from them.",
            json.dumps(bootstrap_tool_outputs, ensure_ascii=False),
        ]
        return [{"role": "system", "content": "\n".join(lines)}]

    def _format_execution_state(
        self,
        execution_plan: dict[str, Any],
        run_state: AgentRunState,
    ) -> str:
        return (
            "Execution state:\n"
            f"- objective: {execution_plan.get('objective')}\n"
            f"- need_identity_verification: {execution_plan.get('need_identity_verification')}\n"
            f"- image_reasoning: {execution_plan.get('image_reasoning')}\n"
            f"- planned_tools: {', '.join(execution_plan.get('tool_sequence', [])) or 'none'}\n"
            f"- current_step: {run_state.current_step}\n"
            f"- loaded_skills: {', '.join(run_state.loaded_skills) or 'none'}"
        )

    def _build_execution_trace(
        self,
        *,
        planner_debug: dict[str, Any],
        run_state: AgentRunState,
        execution_plan: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "run_id": run_state.run_id,
            "state": run_state.snapshot(),
            "planner": {
                "candidate_count": planner_debug.get("candidate_count"),
                "temperatures": planner_debug.get("temperatures"),
                "candidates": planner_debug.get("candidates"),
                "merged_plan": planner_debug.get("merged_plan", execution_plan),
                "filtered_unknown_tools": planner_debug.get("filtered_unknown_tools", []),
                "fallback_reasons": planner_debug.get("fallback_reasons", []),
            },
            "tool_sequence": [
                {
                    "tool_name": item["tool_name"],
                    "status": item["status"],
                    "duration_ms": item["duration_ms"],
                    "arguments": item["arguments"],
                    "result_summary": item["result_summary"],
                }
                for item in run_state.tool_trace
            ],
        }

    def _log_run_summary(
        self,
        run_state: AgentRunState,
        tool_outputs: list[dict[str, Any]],
        execution_trace: dict[str, Any] | None,
    ) -> None:
        logger.info(
            "agent_run_summary %s",
            json.dumps(
                {
                    "run_id": run_state.run_id,
                    "objective": run_state.objective,
                    "planned_tools": run_state.planned_tools,
                    "completed_tools": run_state.completed_tools,
                    "identity_verified": run_state.identity_verified,
                    "fallback_reasons": run_state.fallback_reasons,
                    "tool_output_count": len(tool_outputs),
                    "execution_trace_available": execution_trace is not None,
                },
                ensure_ascii=False,
            ),
        )

    def _build_user_content(
        self,
        user_query: str,
        images: list[dict[str, Any]],
    ) -> Any:
        if not images:
            return user_query

        content: list[dict[str, Any]] = [{"type": "text", "text": user_query}]
        for image in images:
            image_url = image.get("image_url")
            image_base64 = image.get("image_base64")
            mime_type = image.get("mime_type", "image/png")
            if image_url and not image_base64:
                image_base64, mime_type = self._try_load_local_image(image_url, mime_type)
            if image_base64:
                image_url = f"data:{mime_type};base64,{image_base64}"
            if image_url:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    }
                )
        return content

    def _try_load_local_image(
        self,
        image_url: str,
        mime_type: str,
    ) -> tuple[str | None, str]:
        image_path = Path(image_url).expanduser()
        if not image_path.is_file():
            return None, mime_type

        detected_mime_type, _ = mimetypes.guess_type(image_path.name)
        with image_path.open("rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded, detected_mime_type or mime_type

    def _build_tool_registry(self) -> dict[str, ToolHandler]:
        return {
            "verify_patient_identity": lambda **kwargs: mcp_tool_service.verify_patient(
                self.db, **kwargs
            ),
            "get_patient_profile": lambda **kwargs: mcp_tool_service.get_patient_profile(
                self.db, **kwargs
            ),
            "get_patient_medical_cases": lambda **kwargs: mcp_tool_service.get_patient_medical_cases(
                self.db, **kwargs
            ),
            "get_patient_visit_records": lambda **kwargs: mcp_tool_service.get_patient_visit_records(
                self.db, **kwargs
            ),
            "get_follow_up_plans": lambda **kwargs: mcp_tool_service.get_follow_up_plans(
                self.db, **kwargs
            ),
            "get_medication_reminders": lambda **kwargs: mcp_tool_service.get_medication_reminders(
                self.db, **kwargs
            ),
            "assess_follow_up_risk": lambda **kwargs: mcp_tool_service.assess_follow_up_risk(
                **kwargs
            ),
        }

    def _tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "verify_patient_identity",
                    "description": "Verify patient identity with patient_code plus phone or id_number.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_code": {"type": "string"},
                            "phone": {"type": "string"},
                            "id_number": {"type": "string"},
                        },
                        "required": ["patient_code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_patient_profile",
                    "description": "Get the basic patient profile.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "integer"},
                            "patient_code": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_patient_medical_cases",
                    "description": "Get the patient's medical cases.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "integer"},
                            "patient_code": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_patient_visit_records",
                    "description": "Get the patient's visit records.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "integer"},
                            "patient_code": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_follow_up_plans",
                    "description": "Get structured follow-up plans for a verified patient.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "integer"},
                            "patient_code": {"type": "string"},
                            "status": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_medication_reminders",
                    "description": "Get medication reminders for a verified patient.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "integer"},
                            "patient_code": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "assess_follow_up_risk",
                    "description": "Assess follow-up risk from the user query using conservative rules.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                        "required": ["query"],
                    },
                },
            },
        ]

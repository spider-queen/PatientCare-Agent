from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PRIVATE_DATA_TOOLS = {
    "get_patient_profile",
    "get_patient_medical_cases",
    "get_patient_visit_records",
    "get_follow_up_plans",
    "get_medication_reminders",
}


@dataclass
class AgentRunState:
    run_id: str
    objective: str
    planned_tools: list[str]
    need_identity_verification: bool
    image_reasoning: bool
    active_patient_id: int | None = None
    active_patient_code: str | None = None
    active_patient_phone: str | None = None
    active_patient_id_number: str | None = None
    actor_role: str | None = None
    access_purpose: str | None = None
    current_step: str = "planning"
    completed_tools: list[str] = field(default_factory=list)
    identity_verified: bool = False
    evidence_gaps: list[str] = field(default_factory=list)
    loaded_skills: list[str] = field(default_factory=list)
    fallback_reasons: list[str] = field(default_factory=list)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_execution_plan(
        cls,
        *,
        run_id: str,
        execution_plan: dict[str, Any],
        current_patient_context: dict[str, Any] | None = None,
    ) -> "AgentRunState":
        context = current_patient_context or {}
        state = cls(
            run_id=run_id,
            objective=execution_plan.get("objective", "Complete the patient request."),
            planned_tools=list(execution_plan.get("tool_sequence", [])),
            need_identity_verification=bool(
                execution_plan.get("need_identity_verification", False)
            ),
            image_reasoning=bool(execution_plan.get("image_reasoning", False)),
            active_patient_id=context.get("patient_id"),
            active_patient_code=context.get("patient_code"),
            active_patient_phone=context.get("phone"),
            active_patient_id_number=context.get("id_number"),
            actor_role=context.get("actor_role"),
            access_purpose=context.get("access_purpose"),
        )
        state._sync_current_step()
        return state

    def mark_skill_loaded(self, name: str) -> None:
        if name not in self.loaded_skills:
            self.loaded_skills.append(name)

    def mark_bootstrap_tool(self, item: dict[str, Any]) -> None:
        tool_name = item.get("tool_name", "")
        result = item.get("result", {})
        arguments = item.get("arguments", {})
        if tool_name and tool_name not in self.completed_tools:
            self.completed_tools.append(tool_name)
        self._update_from_tool_result(tool_name, result)
        self.tool_trace.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "status": "bootstrap",
                "duration_ms": 0,
                "result_summary": self._summarize_result(result),
            }
        )
        self._sync_current_step()

    def add_fallback(self, reason: str) -> None:
        if reason not in self.fallback_reasons:
            self.fallback_reasons.append(reason)

    def add_evidence_gap(self, message: str) -> None:
        if message and message not in self.evidence_gaps:
            self.evidence_gaps.append(message)

    def set_reasoning(self) -> None:
        self.current_step = "reasoning"

    def set_finalizing(self) -> None:
        self.current_step = "finalizing"

    def private_access_required(self, tool_name: str) -> bool:
        return tool_name in PRIVATE_DATA_TOOLS

    def clinician_follow_up_access_allowed(self) -> bool:
        return (
            bool(self.active_patient_id or self.active_patient_code)
            and self.actor_role == "clinician"
            and self.access_purpose == "follow_up_care"
        )

    def apply_context_defaults(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(arguments)
        if tool_name == "verify_patient_identity":
            if not normalized.get("patient_code") and self.active_patient_code:
                normalized["patient_code"] = self.active_patient_code
            if not normalized.get("phone") and not normalized.get("id_number"):
                if self.active_patient_phone:
                    normalized["phone"] = self.active_patient_phone
                elif self.active_patient_id_number:
                    normalized["id_number"] = self.active_patient_id_number
            return normalized

        if not normalized.get("patient_id") and self.active_patient_id is not None:
            normalized["patient_id"] = self.active_patient_id
        if not normalized.get("patient_code") and self.active_patient_code:
            normalized["patient_code"] = self.active_patient_code
        return normalized

    def record_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int,
        status: str,
    ) -> None:
        if status == "ok" and tool_name not in self.completed_tools:
            self.completed_tools.append(tool_name)
        self.tool_trace.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "status": status,
                "duration_ms": duration_ms,
                "result_summary": self._summarize_result(result),
            }
        )
        self._update_from_tool_result(tool_name, result)
        self._sync_current_step()

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "objective": self.objective,
            "current_step": self.current_step,
            "planned_tools": self.planned_tools,
            "completed_tools": self.completed_tools,
            "identity_verified": self.identity_verified,
            "active_patient_id": self.active_patient_id,
            "active_patient_code": self.active_patient_code,
            "actor_role": self.actor_role,
            "access_purpose": self.access_purpose,
            "evidence_gaps": self.evidence_gaps,
            "loaded_skills": self.loaded_skills,
            "fallback_reasons": self.fallback_reasons,
            "tool_trace": self.tool_trace,
        }

    def _sync_current_step(self) -> None:
        for tool_name in self.planned_tools:
            if tool_name not in self.completed_tools:
                self.current_step = f"awaiting:{tool_name}"
                return
        self.current_step = "finalizing"

    def _update_from_tool_result(self, tool_name: str, result: dict[str, Any]) -> None:
        if tool_name == "verify_patient_identity":
            if result.get("verified"):
                self.identity_verified = True
                patient = result.get("patient", {})
                if self.active_patient_id is None and patient.get("id") is not None:
                    self.active_patient_id = int(patient["id"])
                if not self.active_patient_code and patient.get("patient_code"):
                    self.active_patient_code = str(patient["patient_code"])
            else:
                self.add_evidence_gap(
                    result.get("reason", "Identity verification failed or is incomplete.")
                )

        if result.get("found") is False:
            self.add_evidence_gap(result.get("reason", f"{tool_name} returned no data."))
        if result.get("count") == 0:
            self.add_evidence_gap(f"{tool_name} returned no matching records.")
        if result.get("error"):
            self.add_evidence_gap(str(result["error"]))

    def _summarize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        for key in ("verified", "found", "count", "reason", "error", "allowed"):
            if key in result:
                summary[key] = result[key]
        patient = result.get("patient")
        if isinstance(patient, dict):
            summary["patient_code"] = patient.get("patient_code")
        return summary

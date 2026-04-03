# 作者：小红书@人间清醒的李某人

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.llm.qwen_client import QwenClient
from app.services import mcp_tool_service


ToolHandler = Callable[..., Dict[str, Any]]


SYSTEM_PROMPT = """
你是医院患者智能辅助 Agent。
你可以调用内部工具完成身份验证、病例查询、就诊记录调取。
涉及患者隐私数据时，优先完成身份验证。
回答必须基于工具结果，不要编造病例或就诊信息。
当用户要求“最近一次”“最新一次”就诊记录时，使用 get_patient_visit_records，并传入 limit=1。
不要臆造不存在的工具名称。
采用“先规划、再行动、最后校验”的工作方式：
1. 先根据问题形成简短内部计划。
2. 每一步只执行当前最必要的工具。
3. 工具结果不足时继续补查，足够时停止。
4. 最终答案只保留结论和证据，不暴露冗长内部思维。
如果提供了“短期记忆、用户画像、关键事件”上下文，回答前优先参考这些信息，并在与用户当前问题相关时加以利用。
""".strip()

PLANNER_PROMPT = """
你是 Agent 的内部 Planner，需要为当前问题生成简洁计划。
要求结合以下策略：
1. CoT：先拆分目标、约束、所需证据。
2. ReAct：明确下一步最合适的动作和工具顺序。
3. Self-Consistency：你会被多次采样，输出要稳定、可执行、短。

仅输出 JSON，不要输出 markdown，不要解释：
{
  "objective": "一句话目标",
  "need_identity_verification": true,
  "image_reasoning": false,
  "tool_sequence": ["verify_patient_identity", "get_patient_visit_records"],
  "steps": ["步骤1", "步骤2"],
  "final_answer_focus": ["回答应覆盖的重点1", "重点2"]
}
""".strip()

FINALIZER_PROMPT = """
你是最终答案整理器。
请基于用户问题、执行计划和工具结果给出最终回答。
要求：
1. 只能使用已有工具结果和已知图片内容。
2. 如果证据不足，明确指出不足。
3. 直接给结论、依据和必要提醒，不暴露内部思维链。
""".strip()

MAX_TOOL_STEPS = 6
PLAN_TEMPERATURES = [0.1, 0.4, 0.7]


class QwenMCPAgent:
    def __init__(self, db: Session, llm_client: QwenClient) -> None:
        self.db = db
        self.llm_client = llm_client
        self.tools = self._build_tool_registry()

    def run(
        self,
        user_query: str,
        images: Optional[List[Dict[str, Any]]] = None,
        debug_planner: bool = False,
        memory_context: Optional[Dict[str, Any]] = None,
        current_patient_context: Optional[Dict[str, Any]] = None,
        bootstrap_tool_outputs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        execution_plan, planner_debug = self._build_execution_plan(
            user_query=user_query,
            has_images=bool(images),
        )
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self._build_patient_context_messages(current_patient_context),
            *self._build_bootstrap_tool_messages(bootstrap_tool_outputs),
            *self._build_memory_messages(memory_context),
            {
                "role": "system",
                "content": self._format_execution_plan(execution_plan),
            },
            {"role": "user", "content": self._build_user_content(user_query, images or [])},
        ]
        tool_outputs = list(bootstrap_tool_outputs or [])
        tool_steps = 0

        while tool_steps < MAX_TOOL_STEPS:
            response = self.llm_client.complete_with_tools(
                messages=messages,
                tools=self._tool_specs(),
                temperature=0,
            )

            if response["tool_calls"]:
                messages.append(response["assistant_message"])

                for tool_call in response["tool_calls"]:
                    handler = self.tools.get(tool_call["name"])
                    if handler is None:
                        continue
                    result = handler(**tool_call["arguments"])
                    tool_outputs.append(
                        {
                            "tool_name": tool_call["name"],
                            "arguments": tool_call["arguments"],
                            "result": result,
                        }
                    )
                    tool_steps += 1
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": tool_call["name"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                continue

            answer = self._finalize_answer(
                user_query=user_query,
                execution_plan=execution_plan,
                draft_answer=response["content"] or "",
                tool_outputs=tool_outputs,
                has_images=bool(images),
            )
            return {
                "answer": answer,
                "tool_outputs": tool_outputs,
                "planner_debug": (
                    self._build_runtime_planner_debug(
                        planner_debug=planner_debug,
                        execution_plan=execution_plan,
                        tool_outputs=tool_outputs,
                    )
                    if debug_planner
                    else None
                ),
            }

        return {
            "answer": self._finalize_answer(
                user_query=user_query,
                execution_plan=execution_plan,
                draft_answer="",
                tool_outputs=tool_outputs,
                has_images=bool(images),
            ),
            "tool_outputs": tool_outputs,
            "planner_debug": (
                self._build_runtime_planner_debug(
                    planner_debug=planner_debug,
                    execution_plan=execution_plan,
                    tool_outputs=tool_outputs,
                )
                if debug_planner
                else None
            ),
        }

    def _build_execution_plan(
        self, user_query: str, has_images: bool
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        raw_candidates: List[Dict[str, Any]] = []
        planner_user_prompt = (
            f"用户问题：{user_query}\n"
            f"是否包含图片：{'是' if has_images else '否'}\n"
            "请输出最小可执行计划。"
        )
        for temperature in PLAN_TEMPERATURES:
            response = self.llm_client.complete(
                messages=[
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": planner_user_prompt},
                ],
                temperature=temperature,
            )
            parsed_candidate = self._parse_plan_candidate(response["content"])
            raw_candidates.append(
                {
                    "temperature": temperature,
                    "raw_content": response["content"],
                    "parsed_plan": parsed_candidate,
                }
            )
            candidates.append(parsed_candidate)
        merged_plan = self._merge_plan_candidates(candidates, has_images=has_images)
        return merged_plan, {
            "planner_prompt": PLANNER_PROMPT,
            "temperatures": PLAN_TEMPERATURES,
            "candidates": raw_candidates,
            "merged_plan": merged_plan,
        }

    def _parse_plan_candidate(self, content: str) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    pass
        return {
            "objective": "基于用户问题规划查询与回答",
            "need_identity_verification": False,
            "image_reasoning": False,
            "tool_sequence": [],
            "steps": ["解析问题", "按需调用工具", "整理结论"],
            "final_answer_focus": ["直接回答问题", "标注依据和限制"],
        }

    def _merge_plan_candidates(
        self,
        candidates: List[Dict[str, Any]],
        has_images: bool,
    ) -> Dict[str, Any]:
        verification_votes = sum(
            1 for candidate in candidates if candidate.get("need_identity_verification")
        )
        image_votes = sum(1 for candidate in candidates if candidate.get("image_reasoning"))
        tool_scores: Dict[str, int] = {}
        merged_steps: List[str] = []
        merged_focus: List[str] = []

        for candidate in candidates:
            for tool_name in candidate.get("tool_sequence", []):
                if tool_name not in self.tools:
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
        return {
            "objective": candidates[0].get("objective", "完成患者问题回答"),
            "need_identity_verification": verification_votes >= 2,
            "image_reasoning": has_images or image_votes >= 2,
            "tool_sequence": ranked_tools,
            "steps": merged_steps[:5] or ["解析问题", "按需调用工具", "整理结论"],
            "final_answer_focus": merged_focus[:5] or ["直接回答问题", "说明依据与限制"],
        }

    def _format_execution_plan(self, execution_plan: Dict[str, Any]) -> str:
        return (
            "内部执行计划（已做多候选一致性筛选）：\n"
            f"- 目标：{execution_plan['objective']}\n"
            f"- 是否优先验权：{'是' if execution_plan['need_identity_verification'] else '否'}\n"
            f"- 是否结合图片：{'是' if execution_plan['image_reasoning'] else '否'}\n"
            f"- 推荐工具顺序：{', '.join(execution_plan['tool_sequence']) or '按需决定'}\n"
            f"- 关键步骤：{'；'.join(execution_plan['steps'])}\n"
            f"- 回答重点：{'；'.join(execution_plan['final_answer_focus'])}"
        )

    def _finalize_answer(
        self,
        user_query: str,
        execution_plan: Dict[str, Any],
        draft_answer: str,
        tool_outputs: List[Dict[str, Any]],
        has_images: bool,
    ) -> str:
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
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0,
        )
        return response["content"] or draft_answer

    def _build_memory_messages(
        self,
        memory_context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        if not memory_context:
            return []

        memory_lines: List[str] = []
        short_term_memories = memory_context.get("short_term_memories", [])
        if short_term_memories:
            formatted_memories = []
            for item in short_term_memories:
                role = item.get("role", "unknown")
                content = item.get("content", "")
                multimodal_payload = item.get("multimodal_payload")
                suffix = f" [多模态摘要: {multimodal_payload}]" if multimodal_payload else ""
                formatted_memories.append(f"{role}: {content}{suffix}")
            memory_lines.append("短期记忆：\n" + "\n".join(formatted_memories))

        user_profile = memory_context.get("user_profile")
        if user_profile:
            profile_summary = user_profile.get("profile_summary")
            stable_preferences = user_profile.get("stable_preferences")
            preferred_topics = user_profile.get("preferred_topics")
            memory_lines.append(
                "长期用户画像：\n"
                f"- 用户画像摘要：{profile_summary or '无'}\n"
                f"- 稳定偏好：{stable_preferences or '无'}\n"
                f"- 关注主题：{preferred_topics or '无'}"
            )

        relevant_events = memory_context.get("relevant_events", [])
        if relevant_events:
            formatted_events = []
            for event in relevant_events:
                formatted_events.append(
                    f"{event.get('event_time')}: {event.get('title')} - {event.get('summary') or ''}"
                )
            memory_lines.append("相关关键事件：\n" + "\n".join(formatted_events))

        if not memory_lines:
            return []
        return [{"role": "system", "content": "\n\n".join(memory_lines)}]

    def _build_patient_context_messages(
        self,
        current_patient_context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        if not current_patient_context:
            return []

        patient_code = current_patient_context.get("patient_code")
        phone = current_patient_context.get("phone")
        id_number = current_patient_context.get("id_number")
        full_name = current_patient_context.get("full_name")

        lines = [
            "The server has already resolved the active patient context for this request.",
        ]
        if full_name:
            lines.append(f"- full_name: {full_name}")
        if patient_code:
            lines.append(f"- patient_code: {patient_code}")
        if phone:
            lines.append(f"- phone: {phone}")
        if id_number:
            lines.append(f"- id_number: {id_number}")
        lines.append(
            "If the request needs private patient data, first call verify_patient_identity with the resolved patient_code and phone/id_number above, then continue the medical query."
        )
        lines.append(
            "Do not reply that the user failed to provide identity information when this server-side patient context is present."
        )
        return [{"role": "system", "content": "\n".join(lines)}]

    def _build_bootstrap_tool_messages(
        self,
        bootstrap_tool_outputs: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, str]]:
        if not bootstrap_tool_outputs:
            return []

        lines = [
            "The server already executed these tools before the model turn.",
            "Treat the following tool results as trusted context and continue the task from them.",
            json.dumps(bootstrap_tool_outputs, ensure_ascii=False),
        ]
        return [{"role": "system", "content": "\n".join(lines)}]

    def _build_runtime_planner_debug(
        self,
        planner_debug: Dict[str, Any],
        execution_plan: Dict[str, Any],
        tool_outputs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            **planner_debug,
            "execution_plan_prompt": self._format_execution_plan(execution_plan),
            "executed_tools": [
                {
                    "tool_name": item["tool_name"],
                    "arguments": item["arguments"],
                }
                for item in tool_outputs
            ],
        }

    def _build_user_content(
        self,
        user_query: str,
        images: List[Dict[str, Any]],
    ) -> Any:
        if not images:
            return user_query

        content: List[Dict[str, Any]] = [{"type": "text", "text": user_query}]
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
                        "image_url": {
                            "url": image_url,
                        },
                    }
                )
        return content

    def _try_load_local_image(
        self,
        image_url: str,
        mime_type: str,
    ) -> tuple[Optional[str], str]:
        image_path = Path(image_url).expanduser()
        if not image_path.is_file():
            return None, mime_type

        detected_mime_type, _ = mimetypes.guess_type(image_path.name)
        with image_path.open("rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded, detected_mime_type or mime_type

    def _build_tool_registry(self) -> Dict[str, ToolHandler]:
        return {
            "verify_patient_identity": lambda **kwargs: mcp_tool_service.verify_patient(
                self.db, **kwargs
            ),
            "get_patient_profile": lambda **kwargs: mcp_tool_service.get_patient_profile(
                self.db, **kwargs
            ),
            "get_patient_medical_cases": (
                lambda **kwargs: mcp_tool_service.get_patient_medical_cases(
                    self.db, **kwargs
                )
            ),
            "get_patient_visit_records": (
                lambda **kwargs: mcp_tool_service.get_patient_visit_records(
                    self.db, **kwargs
                )
            ),
        }

    def _tool_specs(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "verify_patient_identity",
                    "description": "校验患者身份，可通过 patient_code 搭配 phone 或 id_number 验证。",
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
                    "description": "获取患者基础身份信息。",
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
                    "description": "查询患者病例信息。",
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
                    "description": "查询患者就诊记录。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {"type": "integer"},
                            "patient_code": {"type": "string"},
                            "limit": {
                                "type": "integer",
                                "description": "返回记录条数。查最近一次时传 1。",
                            },
                        },
                    },
                },
            },
        ]

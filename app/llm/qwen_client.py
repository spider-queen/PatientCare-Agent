
import json
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.5-plus"


class QwenClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("QWEN_API_KEY")
        if not resolved_api_key:
            raise ValueError("QWEN_API_KEY is not configured")

        self.model = model or os.getenv("QWEN_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(
            api_key=resolved_api_key,
            base_url=base_url or os.getenv("QWEN_BASE_URL", DEFAULT_BASE_URL),
        )

    def complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0,
    ) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
        )
        message = response.choices[0].message
        return {
            "content": message.content,
            "assistant_message": {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in (message.tool_calls or [])
                ],
            },
            "tool_calls": [
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": json.loads(call.function.arguments),
                }
                for call in (message.tool_calls or [])
            ],
            "raw_response": response.model_dump(),
        }

    def complete(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0,
    ) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        message = response.choices[0].message
        return {
            "content": message.content or "",
            "raw_response": response.model_dump(),
        }

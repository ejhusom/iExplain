from __future__ import annotations

import json
from typing import Any

from iexplain.config import ModelConfig
from iexplain.runtime.llm import LLMBackend
from iexplain.runtime.models import ToolCallRecord
from iexplain.runtime.tools import ToolSpec


class ToolAwareAgent:
    def __init__(self, backend: LLMBackend, model_config: ModelConfig):
        self.backend = backend
        self.model_config = model_config

    def run(
        self,
        *,
        system_prompt: str,
        task: str,
        tools: dict[str, ToolSpec],
        max_turns: int,
    ) -> tuple[str, list[dict[str, Any]], list[ToolCallRecord]]:
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        events: list[dict[str, Any]] = [{"type": "user_task", "content": task}]
        tool_records: list[ToolCallRecord] = []
        tool_schemas = [tool.schema() for tool in tools.values()]

        for turn in range(1, max_turns + 1):
            response = self.backend.complete(
                system_prompt=system_prompt,
                messages=messages,
                tools=tool_schemas,
                model_config=self.model_config,
            )
            events.append(
                {
                    "type": "assistant",
                    "turn": turn,
                    "content": response.content,
                    "tool_calls": [call.name for call in response.tool_calls],
                    "usage": response.usage,
                }
            )
            if not response.tool_calls:
                return response.content, events, tool_records

            assistant_message = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": call.id or f"tool_call_{turn}_{index}",
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": call.arguments if isinstance(call.arguments, str) else json.dumps(call.arguments),
                        },
                    }
                    for index, call in enumerate(response.tool_calls, start=1)
                ],
            }
            messages.append(assistant_message)

            for index, call in enumerate(response.tool_calls, start=1):
                tool = tools[call.name]
                result = tool.call(call.arguments)
                arguments = call.arguments
                parsed_args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
                record = ToolCallRecord(name=call.name, arguments=parsed_args, result=result)
                tool_records.append(record)
                events.append({"type": "tool_call", "turn": turn, "name": call.name, "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id or f"tool_call_{turn}_{index}",
                        "name": call.name,
                        "content": json.dumps(result, ensure_ascii=True),
                    }
                )

        raise RuntimeError(f"Agent exceeded max_turns={max_turns}")

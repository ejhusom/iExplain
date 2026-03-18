from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from iexplain.runtime.llm import LLMResponse, ToolCall


@dataclass
class FakeStep:
    content: str = ""
    tool_calls: list[ToolCall] | None = None


class SequenceBackend:
    def __init__(self, steps: list[FakeStep] | Callable[..., LLMResponse]):
        self.steps = steps
        self.index = 0

    def complete(self, *, system_prompt, messages, tools, model_config):
        if callable(self.steps):
            return self.steps(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                model_config=model_config,
            )
        step = self.steps[self.index]
        self.index += 1
        return LLMResponse(
            content=step.content,
            tool_calls=step.tool_calls or [],
            usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )

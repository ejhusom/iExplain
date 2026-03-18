from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from litellm import completion

from iexplain.config import ModelConfig


@dataclass
class ToolCall:
    id: str | None
    name: str
    arguments: str | dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall]
    usage: dict[str, int]


class LLMBackend(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model_config: ModelConfig,
    ) -> LLMResponse: ...


class LiteLLMBackend:
    def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model_config: ModelConfig,
    ) -> LLMResponse:
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        kwargs: dict[str, Any] = {
            "model": self._resolve_model_name(model_config.provider, model_config.model),
            "messages": all_messages,
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
            "timeout": model_config.timeout_seconds,
            "drop_params": True,
        }
        api_key = self._resolve_api_key(model_config.provider)
        if api_key:
            kwargs["api_key"] = api_key
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = completion(**kwargs)
        choice = response.choices[0]
        message = choice.message
        tool_calls = []
        for item in getattr(message, "tool_calls", []) or []:
            tool_calls.append(
                ToolCall(
                    id=getattr(item, "id", None),
                    name=item.function.name,
                    arguments=item.function.arguments,
                )
            )
        usage = {
            "input_tokens": getattr(response.usage, "prompt_tokens", 0) if getattr(response, "usage", None) else 0,
            "output_tokens": getattr(response.usage, "completion_tokens", 0) if getattr(response, "usage", None) else 0,
            "total_tokens": getattr(response.usage, "total_tokens", 0) if getattr(response, "usage", None) else 0,
        }
        return LLMResponse(
            content=getattr(message, "content", "") or "",
            tool_calls=tool_calls,
            usage=usage,
        )

    @staticmethod
    def _resolve_api_key(provider: str) -> str | None:
        if provider == "openai":
            return os.getenv("OPENAI_API_KEY")
        if provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY")
        return None

    @staticmethod
    def _resolve_model_name(provider: str, model: str) -> str:
        if provider == "ollama" and not model.startswith("ollama/") and not model.startswith("ollama_chat/"):
            return f"ollama_chat/{model}"
        return model

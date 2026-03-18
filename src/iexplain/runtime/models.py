from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionMode(StrEnum):
    pipeline = "pipeline"
    agent = "agent"
    planner = "planner"


class ArtifactInput(BaseModel):
    name: str = Field(
        min_length=1,
        description="Artifact filename relative to the temporary workspace created for the run.",
        examples=["session.log"],
    )
    content: str | None = Field(
        default=None,
        description="Inline text content to write to the workspace before the run starts.",
        examples=["081111 061856 34 INFO dfs.FSNamesystem: BLOCK* NameSystem.allocateBlock: /tmp/x blk_1"],
    )
    source_path: str | None = Field(
        default=None,
        description="Server-local filesystem path to copy into the workspace. This is resolved on the API server, not uploaded by the client.",
        examples=["/var/data/logs/session.log"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "session.log",
                "content": "081111 061856 34 INFO dfs.FSNamesystem: BLOCK* NameSystem.allocateBlock: /tmp/x blk_1",
            }
        }
    )


class RunOverrides(BaseModel):
    mode: ExecutionMode | None = Field(
        default=None,
        description="Override the execution mode selected by the profile.",
    )
    pipeline: str | None = Field(
        default=None,
        description="Override the pipeline name when running in pipeline mode.",
    )
    tools: list[str] | None = Field(
        default=None,
        description="Replace the tool allowlist for this run.",
        examples=[["read_file", "search_text"]],
    )
    skills: list[str] | None = Field(
        default=None,
        description="Replace the active skills for this run.",
        examples=[["generic-log-analysis"]],
    )
    prompt_overrides: dict[str, str] | None = Field(
        default=None,
        description="Map prompt roles to prompt variants, for example `general_analyst: default`.",
        examples=[{"general_analyst": "default"}],
    )
    max_turns: int | None = Field(
        default=None,
        description="Maximum assistant turns allowed for each agent loop.",
        examples=[4],
    )
    max_delegations: int | None = Field(
        default=None,
        description="Maximum delegations allowed in planner mode.",
        examples=[2],
    )
    provider: str | None = Field(
        default=None,
        description="Override the model provider for this run.",
        examples=["openai"],
    )
    model: str | None = Field(
        default=None,
        description="Override the model name for this run.",
        examples=["gpt-4o-mini"],
    )
    temperature: float | None = Field(
        default=None,
        description="Override the model temperature for this run.",
        examples=[0.0],
    )
    max_tokens: int | None = Field(
        default=None,
        description="Override the model output token limit for this run.",
        examples=[4096],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "max_turns": 4,
                "prompt_overrides": {"general_analyst": "default"},
            }
        }
    )


class RunRequest(BaseModel):
    task: str = Field(
        min_length=1,
        description="Natural-language task the runtime should perform.",
        examples=["Explain what happened in session.log"],
    )
    profile: str = Field(
        default="default",
        description="Named runtime profile from the server configuration.",
        examples=["hdfs_eval"],
    )
    artifacts: list[ArtifactInput] = Field(
        default_factory=list,
        description="Artifacts copied into the temporary workspace for the run.",
    )
    overrides: RunOverrides = Field(
        default_factory=RunOverrides,
        description="Per-request runtime overrides applied on top of the selected profile.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque caller-supplied metadata preserved with the run and included in traces.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task": "Explain what happened in session.log",
                "profile": "hdfs_eval",
                "artifacts": [
                    {
                        "name": "session.log",
                        "content": "081111 061856 34 INFO dfs.FSNamesystem: BLOCK* NameSystem.allocateBlock: /tmp/x blk_1",
                    }
                ],
                "overrides": {"max_turns": 4},
                "metadata": {"ticket": "INC-42"},
            }
        }
    )


class ToolCallRecord(BaseModel):
    name: str = Field(description="Tool name invoked during the run.")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool arguments after JSON decoding.",
    )
    result: Any = Field(
        default=None,
        description="Tool result captured in the execution trace.",
    )


class RunResult(BaseModel):
    content: str = Field(description="Final assistant output for the run.")
    mode: ExecutionMode = Field(description="Resolved execution mode used for the run.")
    profile: str = Field(description="Resolved profile name used for the run.")
    prompt_variants: dict[str, str] = Field(
        default_factory=dict,
        description="Prompt variant chosen for each active role.",
    )
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="Structured record of tool calls captured during execution.",
    )
    events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Low-level execution events captured from the runtime.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata, including the synthesized trace payload.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "The log shows a block allocation request for /tmp/x with no obvious anomaly in the provided sample.",
                "mode": "agent",
                "profile": "default",
                "prompt_variants": {"general_analyst": "default"},
                "tool_calls": [],
                "events": [],
                "metadata": {"trace": {"request": {"task": "Explain what happened in session.log"}}},
            }
        }
    )

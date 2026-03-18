from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from iexplain.runtime.models import ArtifactInput, ExecutionMode, RunOverrides, RunRequest, RunResult


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class SubmitJobRequest(BaseModel):
    run: RunRequest = Field(description="The run request to execute asynchronously.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run": {
                    "task": "Explain what happened in session.log",
                    "profile": "hdfs_eval",
                    "artifacts": [
                        {
                            "name": "session.log",
                            "content": "081111 061856 34 INFO dfs.FSNamesystem: BLOCK* NameSystem.allocateBlock: /tmp/x blk_1",
                        }
                    ],
                }
            }
        }
    )


class JobAcceptedResponse(BaseModel):
    job_id: str = Field(description="Server-generated job identifier.")
    status: JobStatus = Field(description="Initial job state at submission time.")
    session_id: str | None = Field(
        default=None,
        description="Owning session identifier when the job was created from a session task.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job_123456789abc",
                "status": "pending",
                "session_id": "session_123456789abc",
            }
        }
    )


class JobSummaryResponse(BaseModel):
    job_id: str = Field(description="Server-generated job identifier.")
    session_id: str | None = Field(
        default=None,
        description="Owning session identifier when the job belongs to a session.",
    )
    status: JobStatus = Field(description="Current job lifecycle state.")
    created_at: datetime = Field(description="When the job record was created.")
    started_at: datetime | None = Field(default=None, description="When execution started.")
    completed_at: datetime | None = Field(default=None, description="When execution finished, whether successful or failed.")
    task: str = Field(description="Task text from the submitted run request.")
    profile: str = Field(description="Profile used for the run request.")
    error: str | None = Field(default=None, description="Failure message when the job ended in `failed` state.")
    has_result: bool = Field(description="Whether a completed result payload is currently available.")
    storage_path: str | None = Field(
        default=None,
        description="Server-local path to the persisted job record when persistence is enabled.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job_123456789abc",
                "session_id": None,
                "status": "completed",
                "created_at": "2026-03-18T08:15:00Z",
                "started_at": "2026-03-18T08:15:01Z",
                "completed_at": "2026-03-18T08:15:04Z",
                "task": "Explain what happened in session.log",
                "profile": "hdfs_eval",
                "error": None,
                "has_result": True,
                "storage_path": "/tmp/runs/jobs/job_123456789abc.json",
            }
        }
    )


class JobStateResponse(BaseModel):
    job_id: str = Field(description="Server-generated job identifier.")
    status: JobStatus = Field(description="Current job lifecycle state.")
    session_id: str | None = Field(
        default=None,
        description="Owning session identifier when the job belongs to a session.",
    )
    created_at: datetime = Field(description="When the job record was created.")
    started_at: datetime | None = Field(default=None, description="When execution started.")
    completed_at: datetime | None = Field(default=None, description="When execution finished, whether successful or failed.")
    error: str | None = Field(default=None, description="Failure message when the job ended in `failed` state.")
    result: RunResult | None = Field(
        default=None,
        description="Final run result when the job has completed successfully.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job_123456789abc",
                "status": "completed",
                "session_id": None,
                "created_at": "2026-03-18T08:15:00Z",
                "started_at": "2026-03-18T08:15:01Z",
                "completed_at": "2026-03-18T08:15:04Z",
                "error": None,
                "result": {
                    "content": "The log shows a block allocation request with no obvious anomaly in the provided sample.",
                    "mode": "agent",
                    "profile": "default",
                    "prompt_variants": {"general_analyst": "default"},
                    "tool_calls": [],
                    "events": [],
                    "metadata": {},
                },
            }
        }
    )


class SessionCreateRequest(BaseModel):
    name: str | None = Field(default=None, description="Optional human-friendly session name.")
    profile: str = Field(
        default="default",
        description="Default profile to use for tasks submitted through this session.",
        examples=["intent_demo"],
    )
    overrides: RunOverrides = Field(
        default_factory=RunOverrides,
        description="Default runtime overrides merged into each task submitted through the session.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque session metadata carried into future task metadata.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "freno-demo",
                "profile": "intent_demo",
                "metadata": {"source_tool": "freno-ui", "customer": "demo"},
                "overrides": {"max_turns": 4},
            }
        }
    )


class SessionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, description="Replace the session name.")
    profile: str | None = Field(
        default=None,
        description="Replace the session's default profile for future tasks.",
    )
    overrides: RunOverrides | None = Field(
        default=None,
        description="Partial override update merged into the existing session overrides.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Metadata keys to merge into the existing session metadata.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "profile": "hdfs_eval_zero_shot",
                "overrides": {"max_turns": 6},
                "metadata": {"team": "ops"},
            }
        }
    )


class SessionTaskRequest(BaseModel):
    task: str = Field(
        min_length=1,
        description="Task to execute within the session context.",
        examples=["Summarize what happened for intent Id392bc9f3ccb49f5989af6df730f940f"],
    )
    profile: str | None = Field(
        default=None,
        description="Optional per-task profile override. If omitted, the session default profile is used.",
    )
    artifacts: list[ArtifactInput] = Field(
        default_factory=list,
        description="Artifacts copied into the temporary workspace for this task.",
    )
    overrides: RunOverrides = Field(
        default_factory=RunOverrides,
        description="Per-task overrides merged on top of the session defaults.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque task metadata merged with the session metadata.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task": "Summarize what happened for intent Id392bc9f3ccb49f5989af6df730f940f",
                "metadata": {"ticket": "INC-42"},
                "overrides": {"max_turns": 2},
            }
        }
    )


class SessionResponse(BaseModel):
    session_id: str = Field(description="Server-generated session identifier.")
    name: str | None = Field(default=None, description="Optional human-friendly session name.")
    profile: str = Field(description="Default profile used for new tasks in this session.")
    overrides: RunOverrides = Field(
        default_factory=RunOverrides,
        description="Default runtime overrides applied to new session tasks.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque metadata stored with the session.",
    )
    created_at: datetime = Field(description="When the session was created.")
    updated_at: datetime = Field(description="When the session was last updated.")
    storage_path: str | None = Field(
        default=None,
        description="Server-local path to the persisted session record when persistence is enabled.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session_123456789abc",
                "name": "freno-demo",
                "profile": "intent_demo",
                "overrides": {"max_turns": 4},
                "metadata": {"source_tool": "freno-ui", "customer": "demo"},
                "created_at": "2026-03-18T08:10:00Z",
                "updated_at": "2026-03-18T08:10:00Z",
                "storage_path": "/tmp/runs/sessions/session_123456789abc.json",
            }
        }
    )


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Static service health indicator.")
    profiles: list[str] = Field(
        default_factory=list,
        description="Available runtime profiles from the current server configuration.",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Available skill identifiers discovered on the server.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "profiles": ["default", "intent_demo"],
                "skills": ["generic-log-analysis", "hdfs-anomaly-analysis"],
            }
        }
    )


class CatalogProfileResponse(BaseModel):
    mode: ExecutionMode = Field(description="Execution mode configured for the profile.")
    pipeline: str | None = Field(default=None, description="Pipeline used by the profile when mode is `pipeline`.")
    tools: list[str] = Field(default_factory=list, description="Allowed tools for the profile.")
    skills: list[str] = Field(default_factory=list, description="Active skills for the profile.")
    prompt_overrides: dict[str, str] = Field(
        default_factory=dict,
        description="Prompt role to prompt variant mapping configured for the profile.",
    )
    max_turns: int = Field(description="Maximum assistant turns allowed for the profile.")
    max_delegations: int = Field(description="Maximum delegations allowed in planner mode.")


class CatalogModelResponse(BaseModel):
    provider: str = Field(description="Default model provider configured for the service.")
    model: str = Field(description="Default model name configured for the service.")
    temperature: float = Field(description="Default temperature configured for the service.")
    max_tokens: int = Field(description="Default output token limit configured for the service.")
    timeout_seconds: int = Field(description="Model request timeout configured for the service.")


class CatalogApiConfigResponse(BaseModel):
    host: str = Field(description="Bind host configured for the API server.")
    port: int = Field(description="Bind port configured for the API server.")
    max_workers: int = Field(description="Maximum concurrent background job workers.")


class CatalogPathsResponse(BaseModel):
    prompts_dir: str = Field(description="Server-local prompts directory.")
    skills_dir: str = Field(description="Server-local skills directory.")
    runs_dir: str = Field(description="Server-local run storage directory.")
    workspace_root: str = Field(description="Server-local root used for temporary run workspaces.")


class CatalogConfigResponse(BaseModel):
    profiles: dict[str, CatalogProfileResponse] = Field(
        default_factory=dict,
        description="Named runtime profiles available on the server.",
    )
    model: CatalogModelResponse = Field(description="Default model configuration.")
    api: CatalogApiConfigResponse = Field(description="API server configuration.")
    paths: CatalogPathsResponse = Field(description="Resolved server-local filesystem paths.")


class CatalogSkillResponse(BaseModel):
    name: str = Field(description="Human-readable skill name.")
    path: str = Field(description="Server-local path to the skill file.")
    description: str = Field(description="Short skill summary.")
    metadata: dict[str, str] = Field(default_factory=dict, description="Skill metadata parsed from frontmatter.")


class CatalogResponse(BaseModel):
    config: CatalogConfigResponse = Field(description="Resolved server configuration and profile catalog.")
    prompts: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Available prompt variants grouped by prompt role.",
    )
    skills: dict[str, CatalogSkillResponse] = Field(
        default_factory=dict,
        description="Available skills keyed by skill identifier.",
    )
    pipelines: list[str] = Field(default_factory=list, description="Available pipeline identifiers.")
    tools: list[str] = Field(default_factory=list, description="Available tool identifiers.")


class InspectorContextResponse(BaseModel):
    profiles: list[str] = Field(default_factory=list, description="Available profiles shown in the inspector UI.")
    runs_dir: str = Field(description="Server-local directory containing evaluation runs.")
    jobs_dir: str = Field(description="Server-local directory containing persisted API jobs.")
    sessions_dir: str = Field(description="Server-local directory containing persisted API sessions.")


class InspectorRunSummaryResponse(BaseModel):
    run_id: str = Field(description="Run identifier.")
    directory: str = Field(description="Directory name on disk for the run.")
    path: str = Field(description="Server-local filesystem path to the run directory.")
    name: str = Field(description="Human-friendly run name.")
    suite: str | None = Field(default=None, description="Evaluation suite name when present.")
    profile: str | None = Field(default=None, description="Runtime profile used for the run.")
    pipeline: str | None = Field(default=None, description="Pipeline used for the run when present.")
    model: str | None = Field(default=None, description="Model name recorded for the run when present.")
    cases_total: int | None = Field(default=None, description="Total number of evaluated cases when present.")
    score: float | int | None = Field(default=None, description="Primary score extracted from the run summary.")
    assistant_turns: int | None = Field(default=None, description="Assistant turn count recorded for the run when present.")
    total_tokens: int | None = Field(default=None, description="Total token count recorded for the run when present.")
    matrix_context: dict[str, Any] | None = Field(default=None, description="Optional matrix metadata when the run came from a matrix evaluation.")
    updated_at: float = Field(description="Last modification time of the summary file as a Unix timestamp.")


class InspectorRunDetailResponse(BaseModel):
    summary: dict[str, Any] = Field(description="Raw summary.json payload for the run.")
    experiment: dict[str, Any] = Field(description="Raw experiment.json payload for the run when present.")
    results_preview: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Preview of up to the first 10 lines from results.jsonl.",
    )

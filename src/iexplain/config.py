from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from iexplain.runtime.models import ExecutionMode


class ModelConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_seconds: int = 60


class PathsConfig(BaseModel):
    prompts_dir: str = "prompts"
    skills_dir: str = "skills"
    runs_dir: str = "runs"
    workspace_root: str = "workspaces"


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    max_workers: int = 4


class ProfileConfig(BaseModel):
    mode: ExecutionMode = ExecutionMode.agent
    pipeline: str | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    prompt_overrides: dict[str, str] = Field(default_factory=dict)
    max_turns: int = 6
    max_delegations: int = 2

    @model_validator(mode="after")
    def validate_profile(self) -> "ProfileConfig":
        if self.mode == ExecutionMode.pipeline and not self.pipeline:
            raise ValueError("Pipeline profiles must define a pipeline name.")
        if self.max_turns < 1:
            raise ValueError("max_turns must be >= 1.")
        if self.max_delegations < 0:
            raise ValueError("max_delegations must be >= 0.")
        return self


class AppConfig(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> "AppConfig":
        config_path = Path(path).resolve()
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
        config = cls.model_validate(data)
        root = config_path.parent
        config.paths.prompts_dir = str((root.parent / config.paths.prompts_dir).resolve())
        config.paths.skills_dir = str((root.parent / config.paths.skills_dir).resolve())
        config.paths.runs_dir = str((root.parent / config.paths.runs_dir).resolve())
        config.paths.workspace_root = str((root.parent / config.paths.workspace_root).resolve())
        return config

    def ensure_directories(self) -> None:
        for path_value in (
            self.paths.prompts_dir,
            self.paths.skills_dir,
            self.paths.runs_dir,
            self.paths.workspace_root,
        ):
            Path(path_value).mkdir(parents=True, exist_ok=True)

    def get_profile(self, name: str) -> ProfileConfig:
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise KeyError(f"Unknown profile: {name}") from exc

    def catalog(self) -> dict[str, Any]:
        return {
            "profiles": {name: profile.model_dump() for name, profile in self.profiles.items()},
            "model": self.model.model_dump(),
            "api": self.api.model_dump(),
            "paths": self.paths.model_dump(),
        }

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from iexplain.config import AppConfig, ModelConfig, ProfileConfig
from iexplain.runtime.agent import ToolAwareAgent
from iexplain.runtime.catalog import PromptCatalog, SkillLibrary
from iexplain.runtime.llm import LLMBackend, LiteLLMBackend
from iexplain.runtime.models import ArtifactInput, ExecutionMode, RunRequest, RunResult
from iexplain.runtime.pipelines import PIPELINES, get_pipeline
from iexplain.runtime.tools import ToolContext, ToolSpec, build_tools, tool_catalog


class IExplainService:
    def __init__(
        self,
        config: AppConfig,
        *,
        backend: LLMBackend | None = None,
        prompt_catalog: PromptCatalog | None = None,
        skill_library: SkillLibrary | None = None,
    ) -> None:
        self.config = config
        self.config.ensure_directories()
        self.backend = backend or LiteLLMBackend()
        self.prompt_catalog = prompt_catalog or PromptCatalog(config.paths.prompts_dir)
        self.skill_library = skill_library or SkillLibrary(config.paths.skills_dir)

    def catalog(self) -> dict[str, Any]:
        return {
            "config": self.config.catalog(),
            "prompts": self.prompt_catalog.list_catalog(),
            "skills": self.skill_library.list_catalog(),
            "pipelines": sorted(PIPELINES),
            "tools": tool_catalog(),
        }

    def resolve_run_config(self, request: RunRequest) -> dict[str, Any]:
        profile = self._merge_profile(self.config.get_profile(request.profile), request)
        model_config = self._merge_model(self.config.model, request)
        return {
            "profile": request.profile,
            "mode": profile.mode.value,
            "pipeline": profile.pipeline,
            "tools": profile.tools,
            "skills": profile.skills,
            "prompt_overrides": profile.prompt_overrides,
            "max_turns": profile.max_turns,
            "max_delegations": profile.max_delegations,
            "model": model_config.model_dump(),
        }

    def run(self, request: RunRequest) -> RunResult:
        profile = self._merge_profile(self.config.get_profile(request.profile), request)
        model_config = self._merge_model(self.config.model, request)

        workspace_root = Path(self.config.paths.workspace_root)
        workspace_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=workspace_root, prefix="run-") as temp_dir:
            workspace = Path(temp_dir)
            artifact_manifest = self._materialize_artifacts(workspace, request.artifacts)
            if profile.mode == ExecutionMode.pipeline:
                return self._run_pipeline(request, profile, model_config, workspace, artifact_manifest)
            if profile.mode == ExecutionMode.agent:
                return self._run_agent(request, profile, model_config, workspace, artifact_manifest)
            return self._run_planner(request, profile, model_config, workspace, artifact_manifest)

    def _run_pipeline(
        self,
        request: RunRequest,
        profile: ProfileConfig,
        model_config: ModelConfig,
        workspace: Path,
        artifact_manifest: list[str],
    ) -> RunResult:
        pipeline = get_pipeline(profile.pipeline or "")
        stage_outputs: dict[str, str] = {}
        events: list[dict[str, Any]] = []
        tool_calls = []
        prompt_variants: dict[str, str] = {}

        for stage in pipeline:
            prompt_variants[stage.role] = self._prompt_variant_for(profile, stage.role)
            system_prompt = self._build_system_prompt(stage.role, profile)
            task_text = stage.task_template.format(
                task=request.task,
                artifacts="\n".join(f"- {item}" for item in artifact_manifest) or "- (none)",
                previous_output=next(reversed(stage_outputs.values()), ""),
                history=self._history_text(stage_outputs),
            )
            tools = build_tools(stage.tools, ToolContext(workspace))
            agent = ToolAwareAgent(self.backend, model_config)
            content, stage_events, stage_tools = agent.run(
                system_prompt=system_prompt,
                task=task_text,
                tools=tools,
                max_turns=profile.max_turns,
            )
            stage_outputs[stage.name] = content
            events.extend([{**event, "stage": stage.name, "role": stage.role} for event in stage_events])
            tool_calls.extend(stage_tools)

        return self._finalize_result(
            request=request,
            profile=request.profile,
            profile_config=profile,
            model_config=model_config,
            content=next(reversed(stage_outputs.values()), ""),
            mode=profile.mode,
            prompt_variants=prompt_variants,
            tool_calls=tool_calls,
            events=events,
            metadata={
                "workspace_files": artifact_manifest,
                "stage_outputs": stage_outputs,
                "request_metadata": request.metadata,
            },
        )

    def _run_agent(
        self,
        request: RunRequest,
        profile: ProfileConfig,
        model_config: ModelConfig,
        workspace: Path,
        artifact_manifest: list[str],
    ) -> RunResult:
        prompt_variants = {"general_analyst": self._prompt_variant_for(profile, "general_analyst")}
        system_prompt = self._build_system_prompt("general_analyst", profile)
        task_text = (
            f"{request.task}\n\n"
            f"Workspace artifacts:\n{self._artifact_listing_text(artifact_manifest)}"
        )
        tools = build_tools(profile.tools, ToolContext(workspace))
        agent = ToolAwareAgent(self.backend, model_config)
        content, events, tool_calls = agent.run(
            system_prompt=system_prompt,
            task=task_text,
            tools=tools,
            max_turns=profile.max_turns,
        )
        return self._finalize_result(
            request=request,
            profile=request.profile,
            profile_config=profile,
            model_config=model_config,
            content=content,
            mode=profile.mode,
            prompt_variants=prompt_variants,
            tool_calls=tool_calls,
            events=events,
            metadata={"workspace_files": artifact_manifest, "request_metadata": request.metadata},
        )

    def _run_planner(
        self,
        request: RunRequest,
        profile: ProfileConfig,
        model_config: ModelConfig,
        workspace: Path,
        artifact_manifest: list[str],
    ) -> RunResult:
        events: list[dict[str, Any]] = []
        delegation_state = {"remaining": profile.max_delegations}
        prompt_variants = {"planner": self._prompt_variant_for(profile, "planner")}

        def make_delegate_tool(role: str, tool_name: str, description: str) -> ToolSpec:
            def handler(subtask: str) -> dict[str, Any]:
                if delegation_state["remaining"] <= 0:
                    return {"error": "delegation limit reached"}
                delegation_state["remaining"] -= 1
                agent = ToolAwareAgent(self.backend, model_config)
                system_prompt = self._build_system_prompt(role, profile)
                content, nested_events, nested_tool_calls = agent.run(
                    system_prompt=system_prompt,
                    task=(
                        f"Planner subtask:\n{subtask}\n\n"
                        f"Workspace artifacts:\n{self._artifact_listing_text(artifact_manifest)}"
                    ),
                    tools=build_tools(profile.tools, ToolContext(workspace)),
                    max_turns=profile.max_turns,
                )
                events.extend([{**item, "delegated_role": role} for item in nested_events])
                return {
                    "content": content,
                    "remaining_delegations": delegation_state["remaining"],
                    "tool_calls": [record.model_dump() for record in nested_tool_calls],
                }

            return ToolSpec(
                name=tool_name,
                description=description,
                parameters={
                    "type": "object",
                    "properties": {
                        "subtask": {
                            "type": "string",
                            "description": "The delegated subtask.",
                        }
                    },
                    "required": ["subtask"],
                },
                handler=handler,
            )

        extra_tools = {
            "delegate_log_analysis": make_delegate_tool(
                "role_log_analyst",
                "delegate_log_analysis",
                "Delegate a narrow analysis subtask to a log analyst role.",
            ),
            "delegate_report_writing": make_delegate_tool(
                "role_report_writer",
                "delegate_report_writing",
                "Delegate a writing or synthesis subtask to a report writer role.",
            ),
        }
        tools = build_tools(profile.tools, ToolContext(workspace), extra_tools=extra_tools)
        agent = ToolAwareAgent(self.backend, model_config)
        content, planner_events, planner_tool_calls = agent.run(
            system_prompt=self._build_system_prompt("planner", profile),
            task=(
                f"{request.task}\n\n"
                f"Workspace artifacts:\n{self._artifact_listing_text(artifact_manifest)}\n\n"
                f"You may delegate, but only when it materially improves the answer."
            ),
            tools=tools,
            max_turns=profile.max_turns,
        )
        events = [{**item, "role": "planner"} for item in planner_events] + events
        return self._finalize_result(
            request=request,
            profile=request.profile,
            profile_config=profile,
            model_config=model_config,
            content=content,
            mode=profile.mode,
            prompt_variants=prompt_variants,
            tool_calls=planner_tool_calls,
            events=events,
            metadata={
                "workspace_files": artifact_manifest,
                "remaining_delegations": delegation_state["remaining"],
                "request_metadata": request.metadata,
            },
        )

    def _build_system_prompt(self, role: str, profile: ProfileConfig) -> str:
        variant = self._prompt_variant_for(profile, role)
        prompt = self.prompt_catalog.get(role, variant)
        if profile.skills:
            prompt += "\n\n# Active Skills\n\n" + self.skill_library.render(profile.skills)
        return prompt

    @staticmethod
    def _prompt_variant_for(profile: ProfileConfig, role: str) -> str:
        return profile.prompt_overrides.get(role, "default")

    @staticmethod
    def _history_text(stage_outputs: dict[str, str]) -> str:
        if not stage_outputs:
            return "(no prior stage outputs)"
        sections = []
        for name, content in stage_outputs.items():
            sections.append(f"[{name}]\n{content}")
        return "\n\n".join(sections)

    @staticmethod
    def _artifact_listing_text(artifact_manifest: list[str]) -> str:
        return "\n".join(f"- {item}" for item in artifact_manifest) or "- (none)"

    def _materialize_artifacts(self, workspace: Path, artifacts: list[ArtifactInput]) -> list[str]:
        manifest: list[str] = []
        for artifact in artifacts:
            target = workspace / artifact.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if artifact.content is not None:
                target.write_text(artifact.content, encoding="utf-8")
            elif artifact.source_path is not None:
                source = Path(artifact.source_path).expanduser().resolve()
                target.write_text(source.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            else:
                target.write_text("", encoding="utf-8")
            manifest.append(str(target.relative_to(workspace)))
        return sorted(manifest)

    @staticmethod
    def _merge_profile(base_profile: ProfileConfig, request: RunRequest) -> ProfileConfig:
        profile_data = deepcopy(base_profile.model_dump())
        override_data = request.overrides.model_dump(exclude_none=True)
        for key, value in override_data.items():
            if key in {"provider", "model", "temperature", "max_tokens"}:
                continue
            profile_data[key] = value
        return ProfileConfig.model_validate(profile_data)

    @staticmethod
    def _merge_model(base_model: ModelConfig, request: RunRequest) -> ModelConfig:
        model_data = deepcopy(base_model.model_dump())
        override_data = request.overrides.model_dump(exclude_none=True)
        for key in ("provider", "model", "temperature", "max_tokens"):
            if key in override_data:
                model_data[key] = override_data[key]
        return ModelConfig.model_validate(model_data)

    def _finalize_result(
        self,
        *,
        request: RunRequest,
        profile: str,
        profile_config: ProfileConfig,
        model_config: ModelConfig,
        content: str,
        mode: ExecutionMode,
        prompt_variants: dict[str, str],
        tool_calls: list[Any],
        events: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> RunResult:
        enriched_metadata = deepcopy(metadata)
        enriched_metadata["trace"] = self._build_trace(
            request=request,
            profile=profile,
            profile_config=profile_config,
            model_config=model_config,
            prompt_variants=prompt_variants,
            tool_calls=tool_calls,
            events=events,
            metadata=metadata,
        )
        return RunResult(
            content=content,
            mode=mode,
            profile=profile,
            prompt_variants=prompt_variants,
            tool_calls=tool_calls,
            events=events,
            metadata=enriched_metadata,
        )

    def _build_trace(
        self,
        *,
        request: RunRequest,
        profile: str,
        profile_config: ProfileConfig,
        model_config: ModelConfig,
        prompt_variants: dict[str, str],
        tool_calls: list[Any],
        events: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        assistant_turns = 0
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        stages: dict[str, dict[str, Any]] = {}
        tool_sequence: list[str] = []
        conversation: list[dict[str, Any]] = []
        delegated_roles: list[str] = []

        for event in events:
            delegated_role = event.get("delegated_role")
            stage_name = str(delegated_role or event.get("stage") or event.get("role") or profile_config.mode.value)
            stage = stages.setdefault(
                stage_name,
                {
                    "name": stage_name,
                    "role": event.get("role") or delegated_role or profile_config.mode.value,
                    "assistant_turns": 0,
                    "tool_calls": 0,
                    "tool_names": [],
                    "turn_previews": [],
                },
            )
            if delegated_role and delegated_role not in delegated_roles:
                delegated_roles.append(str(delegated_role))
            if event.get("type") == "assistant":
                assistant_turns += 1
                stage["assistant_turns"] += 1
                usage = event.get("usage") or {}
                input_tokens += int(usage.get("input_tokens", 0) or 0)
                output_tokens += int(usage.get("output_tokens", 0) or 0)
                total_tokens += int(usage.get("total_tokens", 0) or 0)
                stage["turn_previews"].append(
                    {
                        "turn": event.get("turn"),
                        "tool_calls": event.get("tool_calls", []),
                        "delegated_role": delegated_role,
                        "content_preview": self._preview_text(event.get("content")),
                    }
                )
                conversation.append(
                    {
                        "type": "assistant",
                        "stage": stage_name,
                        "role": event.get("role"),
                        "turn": event.get("turn"),
                        "tool_calls": event.get("tool_calls", []),
                        "content_preview": self._preview_text(event.get("content")),
                        "delegated_role": delegated_role,
                    }
                )
            elif event.get("type") == "tool_call":
                stage["tool_calls"] += 1
                tool_name = str(event.get("name") or "")
                if tool_name:
                    tool_sequence.append(tool_name)
                    if tool_name not in stage["tool_names"]:
                        stage["tool_names"].append(tool_name)
                conversation.append(
                    {
                        "type": "tool_call",
                        "stage": stage_name,
                        "name": tool_name,
                        "turn": event.get("turn"),
                        "delegated_role": delegated_role,
                    }
                )

        trace = {
            "request": {
                "task": request.task,
                "profile": profile,
                "artifacts": metadata.get("workspace_files", []),
                "metadata": metadata.get("request_metadata", {}),
            },
            "resolved_runtime": {
                "profile": profile,
                "mode": profile_config.mode.value,
                "pipeline": profile_config.pipeline,
                "tools": profile_config.tools,
                "skills": profile_config.skills,
                "prompt_overrides": prompt_variants,
                "max_turns": profile_config.max_turns,
                "max_delegations": profile_config.max_delegations,
                "model": model_config.model_dump(),
            },
            "stages": list(stages.values()),
            "usage": {
                "assistant_turns": assistant_turns,
                "tool_calls": len(tool_calls),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            "tool_sequence": tool_sequence,
            "delegated_roles": delegated_roles,
            "conversation": conversation,
            "stage_outputs": metadata.get("stage_outputs", {}),
        }

        intent_bundle_summary = self._extract_intent_bundle_summary(tool_calls)
        if intent_bundle_summary:
            trace["intent_bundle"] = intent_bundle_summary

        return trace

    @staticmethod
    def _extract_intent_bundle_summary(tool_calls: list[Any]) -> dict[str, Any] | None:
        for record in tool_calls:
            if getattr(record, "name", None) != "fetch_intent_bundle":
                continue
            result = getattr(record, "result", None)
            if not isinstance(result, dict) or result.get("error"):
                continue

            return {
                "intent_id": result.get("intent_id"),
                "intent_name": result.get("intent_name"),
                "intent_iri": result.get("intent_iri"),
                "handler": result.get("handler"),
                "owner": result.get("owner"),
                "current_state": result.get("current_state"),
                "latest_reason": result.get("latest_reason"),
                "counts": result.get("counts", {}),
                "timeline": result.get("timeline", []),
                "observations": result.get("observations", []),
                "contexts": result.get("contexts", []),
            }
        return None

    @staticmethod
    def _preview_text(value: Any, limit: int = 220) -> str:
        if value is None:
            return ""
        text = " ".join(str(value).split())
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

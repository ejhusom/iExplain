from __future__ import annotations

import json
import sys
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from statistics import median
from typing import Any, TextIO

from pydantic import BaseModel, Field

from iexplain.config import AppConfig
from iexplain.eval.base import SuiteAdapter
from iexplain.eval.suites.bgl import BglSuite
from iexplain.eval.suites.bgl_v2 import BglV2Suite
from iexplain.eval.suites.hdfs import HdfsSuite
from iexplain.runtime.models import RunOverrides, RunRequest
from iexplain.runtime.service import IExplainService


SUITES: dict[str, SuiteAdapter] = {
    "hdfs": HdfsSuite(),
    "bgl": BglSuite(),
    "bgl_v2": BglV2Suite(),
}


class ExperimentSuite(BaseModel):
    type: str
    settings: dict[str, Any] = Field(default_factory=dict)


class ExperimentRuntime(BaseModel):
    profile: str = "default"
    overrides: RunOverrides = Field(default_factory=RunOverrides)


class ExperimentSpec(BaseModel):
    name: str
    suite: ExperimentSuite
    runtime: ExperimentRuntime
    output_dir: str = "runs"
    tags: dict[str, str] = Field(default_factory=dict)


class MatrixAxisValue(BaseModel):
    label: str
    patch: dict[str, Any] = Field(default_factory=dict)


class MatrixAxis(BaseModel):
    name: str
    values: list[MatrixAxisValue]


class ExperimentMatrixSpec(BaseModel):
    name: str
    base_experiment: ExperimentSpec
    axes: list[MatrixAxis] = Field(default_factory=list)
    output_dir: str | None = None


@dataclass(frozen=True)
class ProgressState:
    experiment_index: int
    experiment_total: int
    overall_case_offset: int
    overall_case_total: int


class TerminalProgress:
    def __init__(self, *, enabled: bool, stream: TextIO | None = None) -> None:
        self.enabled = enabled
        self.stream = stream or sys.stdout
        self._last_transient_length = 0

    def info(self, message: str) -> None:
        if not self.enabled:
            return
        self._clear_transient()
        self.stream.write(f"{message}\n")
        self.stream.flush()

    def update(self, message: str) -> None:
        if not self.enabled:
            return
        padding = max(0, self._last_transient_length - len(message))
        self.stream.write("\r" + message + (" " * padding))
        self.stream.flush()
        self._last_transient_length = len(message)

    def complete(self, message: str) -> None:
        if not self.enabled:
            return
        self.update(message)
        self.stream.write("\n")
        self.stream.flush()
        self._last_transient_length = 0

    def _clear_transient(self) -> None:
        if not self.enabled or self._last_transient_length == 0:
            return
        self.stream.write("\r" + (" " * self._last_transient_length) + "\r")
        self.stream.flush()
        self._last_transient_length = 0


def load_experiment(path: str | Path) -> ExperimentSpec:
    experiment_path = Path(path).resolve()
    return ExperimentSpec.model_validate_json(experiment_path.read_text(encoding="utf-8"))


def load_experiment_matrix(path: str | Path) -> ExperimentMatrixSpec:
    matrix_path = Path(path).resolve()
    return ExperimentMatrixSpec.model_validate_json(matrix_path.read_text(encoding="utf-8"))


def run_experiment(
    experiment_path: str | Path,
    *,
    config_path: str | Path = "config/app.toml",
    service: IExplainService | None = None,
    dry_run: bool = False,
    show_progress: bool = False,
    progress_stream: TextIO | None = None,
) -> Path:
    experiment_file = Path(experiment_path).resolve()
    experiment = load_experiment(experiment_file)
    reporter = TerminalProgress(enabled=show_progress, stream=progress_stream)
    return _run_loaded_experiment(
        experiment_file=experiment_file,
        experiment=experiment,
        config_path=config_path,
        service=service,
        dry_run=dry_run,
        reporter=reporter,
        progress_state=None,
        matrix_context=None,
    )


def run_matrix_experiment(
    matrix_path: str | Path,
    *,
    config_path: str | Path = "config/app.toml",
    service: IExplainService | None = None,
    dry_run: bool = False,
    show_progress: bool = False,
    progress_stream: TextIO | None = None,
) -> list[Path]:
    matrix_file = Path(matrix_path).resolve()
    matrix = load_experiment_matrix(matrix_file)
    config = service.config if service else AppConfig.from_file(config_path)
    run_service = service or IExplainService(config)
    reporter = TerminalProgress(enabled=show_progress, stream=progress_stream)

    expanded = _expand_matrix(matrix)
    case_counts = [_count_cases(item.experiment) for item in expanded]
    total_cases = sum(case_counts)
    reporter.info(
        f"Matrix {matrix.name}: {len(expanded)} experiments scheduled, {total_cases} total cases."
    )

    run_dirs: list[Path] = []
    overall_case_offset = 0
    for index, (expanded_item, case_total) in enumerate(zip(expanded, case_counts), start=1):
        matrix_context = {
            "name": matrix.name,
            "combination": expanded_item.factors,
            "combination_index": index,
            "combination_total": len(expanded),
        }
        progress_state = ProgressState(
            experiment_index=index,
            experiment_total=len(expanded),
            overall_case_offset=overall_case_offset,
            overall_case_total=total_cases,
        )
        run_dir = _run_loaded_experiment(
            experiment_file=matrix_file,
            experiment=expanded_item.experiment,
            config_path=config_path,
            service=run_service,
            dry_run=dry_run,
            reporter=reporter,
            progress_state=progress_state,
            matrix_context=matrix_context,
        )
        run_dirs.append(run_dir)
        overall_case_offset += case_total

    reporter.info(f"Matrix {matrix.name}: completed {len(run_dirs)}/{len(expanded)} experiments.")
    return run_dirs


def _run_loaded_experiment(
    *,
    experiment_file: Path,
    experiment: ExperimentSpec,
    config_path: str | Path,
    service: IExplainService | None,
    dry_run: bool,
    reporter: TerminalProgress,
    progress_state: ProgressState | None,
    matrix_context: dict[str, Any] | None,
) -> Path:
    config = service.config if service else AppConfig.from_file(config_path)
    run_service = service or IExplainService(config)
    output_root = (experiment_file.parent.parent / experiment.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{_slug(experiment.name)}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    adapter = SUITES[experiment.suite.type]
    cases = adapter.load_cases(experiment.suite.settings)
    effective_progress = progress_state or ProgressState(
        experiment_index=1,
        experiment_total=1,
        overall_case_offset=0,
        overall_case_total=len(cases),
    )

    reporter.info(
        _experiment_start_message(
            experiment=experiment,
            case_total=len(cases),
            progress_state=effective_progress,
            matrix_context=matrix_context,
        )
    )

    resolved_runtime = run_service.resolve_run_config(
        RunRequest(
            task="resolve evaluation runtime",
            profile=experiment.runtime.profile,
            overrides=experiment.runtime.overrides,
        )
    )
    rows = []
    results_path = run_dir / "results.jsonl"
    for case_index, case in enumerate(cases, start=1):
        reporter.update(
            _case_progress_message(
                experiment=experiment,
                case=case.case_id,
                case_index=case_index,
                case_total=len(cases),
                progress_state=effective_progress,
            )
        )
        request = RunRequest(
            task=case.task,
            profile=experiment.runtime.profile,
            artifacts=case.artifacts,
            overrides=experiment.runtime.overrides,
            metadata={"case_id": case.case_id, **case.metadata},
        )
        if dry_run:
            result_payload = {"content": "", "mode": "", "profile": experiment.runtime.profile}
            score = _error_score(experiment.suite.type, "dry_run")
            case_metrics = _empty_case_metrics()
        else:
            started_at = time.perf_counter()
            try:
                result = run_service.run(request)
                latency_ms = (time.perf_counter() - started_at) * 1000.0
                result_payload = result.model_dump()
                case_metrics = _extract_case_metrics(result_payload, latency_ms)
                try:
                    score = adapter.score_case(case, result)
                except Exception as exc:
                    score = _error_score(experiment.suite.type, f"score_error: {exc}")
            except Exception as exc:
                latency_ms = (time.perf_counter() - started_at) * 1000.0
                result_payload = {"error": str(exc)}
                score = _error_score(experiment.suite.type, f"run_error: {exc}")
                case_metrics = _empty_case_metrics(latency_ms=latency_ms)
        row = {
            "case_id": case.case_id,
            "task": case.task,
            "metadata": case.metadata,
            "result": result_payload,
            "score": score,
            "case_metrics": case_metrics,
        }
        rows.append(row)
        with results_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    summary = {
        "name": experiment.name,
        "run_id": run_id,
        "suite": experiment.suite.type,
        "suite_settings": experiment.suite.settings,
        "tags": experiment.tags,
        "runtime": experiment.runtime.model_dump(exclude_none=True),
        "resolved_runtime": resolved_runtime,
        "cases_total": len(rows),
        "metrics": adapter.summarize(rows),
        "performance": _summarize_case_metrics(rows),
        "prompt_variants_seen": _collect_prompt_variants(rows),
    }
    if matrix_context:
        summary["matrix_context"] = matrix_context
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    experiment_payload = experiment.model_dump(exclude_none=True)
    if matrix_context:
        experiment_payload["matrix_context"] = matrix_context
    (run_dir / "experiment.json").write_text(
        json.dumps(experiment_payload, indent=2),
        encoding="utf-8",
    )

    reporter.complete(
        f"[{effective_progress.experiment_index}/{effective_progress.experiment_total}] "
        f"completed {experiment.name} -> {run_dir.name}"
    )
    return run_dir


@dataclass(frozen=True)
class ExpandedExperiment:
    experiment: ExperimentSpec
    factors: dict[str, str]


def _expand_matrix(matrix: ExperimentMatrixSpec) -> list[ExpandedExperiment]:
    base_data = matrix.base_experiment.model_dump(exclude_none=True)
    if matrix.output_dir is not None:
        base_data["output_dir"] = matrix.output_dir

    if not matrix.axes:
        return [ExpandedExperiment(experiment=ExperimentSpec.model_validate(base_data), factors={})]

    expanded: list[ExpandedExperiment] = []
    for values in product(*(axis.values for axis in matrix.axes)):
        data = deepcopy(base_data)
        factors: dict[str, str] = {}
        for axis, value in zip(matrix.axes, values):
            data = _deep_merge(data, value.patch)
            factors[axis.name] = value.label
        suffix = "-".join(f"{_slug(name)}-{_slug(label)}" for name, label in factors.items())
        if suffix:
            data["name"] = f"{base_data['name']}-{suffix}"
        expanded.append(
            ExpandedExperiment(
                experiment=ExperimentSpec.model_validate(data),
                factors=factors,
            )
        )
    return expanded


def _count_cases(experiment: ExperimentSpec) -> int:
    return len(SUITES[experiment.suite.type].load_cases(experiment.suite.settings))


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _experiment_start_message(
    *,
    experiment: ExperimentSpec,
    case_total: int,
    progress_state: ProgressState,
    matrix_context: dict[str, Any] | None,
) -> str:
    factor_label = "-"
    if matrix_context:
        factors = matrix_context.get("combination", {})
        if factors:
            factor_label = ", ".join(f"{name}={value}" for name, value in sorted(factors.items()))
    return (
        f"[{progress_state.experiment_index}/{progress_state.experiment_total}] "
        f"starting {experiment.name} | suite={experiment.suite.type} | cases={case_total} | matrix={factor_label}"
    )


def _case_progress_message(
    *,
    experiment: ExperimentSpec,
    case: str,
    case_index: int,
    case_total: int,
    progress_state: ProgressState,
) -> str:
    overall_case_index = progress_state.overall_case_offset + case_index
    return (
        f"[{progress_state.experiment_index}/{progress_state.experiment_total}] "
        f"{experiment.name} | case {case_index}/{case_total} | "
        f"overall {overall_case_index}/{progress_state.overall_case_total} | {case}"
    )


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text.lower()).strip("-") or "run"


def _error_score(suite_name: str, message: str) -> dict[str, Any]:
    if suite_name == "hdfs":
        return {
            "passed": False,
            "expected_label": None,
            "predicted_label": None,
            "unparseable": True,
            "error": message,
        }
    return {
        "passed": False,
        "error": message,
    }


def _empty_case_metrics(*, latency_ms: float = 0.0) -> dict[str, Any]:
    rounded_latency = round(latency_ms, 3)
    return {
        "latency_ms": rounded_latency,
        "assistant_turns": 0,
        "tool_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def _extract_case_metrics(result_payload: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    metrics = _empty_case_metrics(latency_ms=latency_ms)
    metrics["tool_calls"] = len(result_payload.get("tool_calls", []))
    for event in result_payload.get("events", []):
        if event.get("type") != "assistant":
            continue
        metrics["assistant_turns"] += 1
        usage = event.get("usage") or {}
        metrics["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        metrics["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        metrics["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    return metrics


def _collect_prompt_variants(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    variants_by_role: dict[str, set[str]] = {}
    for row in rows:
        prompt_variants = row.get("result", {}).get("prompt_variants", {})
        for role, variant in prompt_variants.items():
            variants_by_role.setdefault(role, set()).add(str(variant))
    return {
        role: sorted(variants)
        for role, variants in sorted(variants_by_role.items())
    }


def _summarize_case_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(row.get("case_metrics", {}).get("latency_ms", 0.0) or 0.0) for row in rows]
    assistant_turns = sum(int(row.get("case_metrics", {}).get("assistant_turns", 0) or 0) for row in rows)
    tool_calls = sum(int(row.get("case_metrics", {}).get("tool_calls", 0) or 0) for row in rows)
    input_tokens = sum(int(row.get("case_metrics", {}).get("input_tokens", 0) or 0) for row in rows)
    output_tokens = sum(int(row.get("case_metrics", {}).get("output_tokens", 0) or 0) for row in rows)
    total_tokens = sum(int(row.get("case_metrics", {}).get("total_tokens", 0) or 0) for row in rows)
    case_count = len(rows)
    return {
        "cases_measured": case_count,
        "total_latency_ms": round(sum(latencies), 3),
        "avg_latency_ms": round(sum(latencies) / case_count, 3) if case_count else 0.0,
        "median_latency_ms": round(float(median(latencies)), 3) if latencies else 0.0,
        "p95_latency_ms": round(_percentile(latencies, 95.0), 3) if latencies else 0.0,
        "min_latency_ms": round(min(latencies), 3) if latencies else 0.0,
        "max_latency_ms": round(max(latencies), 3) if latencies else 0.0,
        "assistant_turns": assistant_turns,
        "avg_assistant_turns_per_case": round(assistant_turns / case_count, 3) if case_count else 0.0,
        "tool_calls": tool_calls,
        "avg_tool_calls_per_case": round(tool_calls / case_count, 3) if case_count else 0.0,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "avg_input_tokens_per_case": round(input_tokens / case_count, 3) if case_count else 0.0,
        "avg_output_tokens_per_case": round(output_tokens / case_count, 3) if case_count else 0.0,
        "avg_total_tokens_per_case": round(total_tokens / case_count, 3) if case_count else 0.0,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, int(round((percentile / 100.0) * (len(ordered) - 1)))))
    return ordered[position]

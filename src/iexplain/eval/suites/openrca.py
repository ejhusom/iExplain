from __future__ import annotations

import csv
import itertools
import json
import re
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from statistics import mean
from typing import Any

from iexplain.eval.base import EvalCase, SuiteAdapter
from iexplain.runtime.models import ArtifactInput, RunResult


_TIME_PATTERN = re.compile(
    r"The (?:\d+-th|only) root cause occurrence time is within 1 minutes \(i\.e\., <=1min\) of ([^\n]+)"
)
_COMPONENT_PATTERN = re.compile(r"The (?:\d+-th|only) predicted root cause component is ([^\n]+)")
_REASON_PATTERN = re.compile(r"The (?:\d+-th|only) predicted root cause reason is ([^\n]+)")


class OpenRcaSuite(SuiteAdapter):
    suite_name = "openrca"

    def load_cases(self, settings: dict[str, Any]) -> list[EvalCase]:
        root = Path(str(settings["openrca_root"])).expanduser().resolve()
        dataset = str(settings["dataset"])
        sample_limit = int(settings.get("sample_limit", 0) or 0)
        start_idx = int(settings.get("start_idx", 0) or 0)
        allowed_task_indices = {
            str(item) for item in settings.get("task_indices", []) if str(item).strip()
        }

        data_root = _dataset_base_dir(root)
        dataset_root = data_root / dataset
        query_rows = _read_csv_rows(dataset_root / "query.csv")
        record_rows = _read_csv_rows(dataset_root / "record.csv")
        if len(query_rows) != len(record_rows):
            raise ValueError(
                f"OpenRCA query/record length mismatch for {dataset}: "
                f"{len(query_rows)} vs {len(record_rows)}"
            )

        background = _load_openrca_schema(root, dataset)
        cases: list[EvalCase] = []

        for row_index, (query_row, record_row) in enumerate(zip(query_rows, record_rows)):
            if row_index < start_idx:
                continue
            task_index = str(query_row["task_index"])
            if allowed_task_indices and task_index not in allowed_task_indices:
                continue

            date_folder = _date_folder_name(str(record_row["datetime"]))
            telemetry_root = dataset_root / "telemetry" / date_folder
            if not telemetry_root.exists():
                raise FileNotFoundError(f"Telemetry folder not found: {telemetry_root}")

            required_fields = _required_fields(str(query_row["scoring_points"]))
            case_id = f"{_slug(dataset)}-{task_index}-row_{row_index:03d}"
            task = _build_task(
                dataset=dataset,
                date_folder=date_folder,
                instruction=str(query_row["instruction"]),
                required_fields=required_fields,
            )
            artifacts = [
                ArtifactInput(name="openrca_context.md", content=background),
                *_telemetry_artifacts(data_root=data_root, dataset=dataset, telemetry_root=telemetry_root),
            ]
            metadata = {
                "dataset": dataset,
                "task_index": task_index,
                "difficulty": _difficulty(task_index),
                "row_index": row_index,
                "date_folder": date_folder,
                "scoring_points": str(query_row["scoring_points"]),
                "required_fields": required_fields,
                "gold_record": record_row,
            }
            cases.append(EvalCase(case_id=case_id, task=task, artifacts=artifacts, metadata=metadata))
            if sample_limit and len(cases) >= sample_limit:
                break

        return cases

    def score_case(self, case: EvalCase, result: RunResult) -> dict[str, Any]:
        scoring_points = str(case.metadata["scoring_points"])
        parsed_prediction = _parse_prediction(result.content)
        if parsed_prediction is None:
            return {
                "passed": False,
                "score": 0.0,
                "unparseable": True,
                "response": result.content,
                "passing_criteria": [],
                "failing_criteria": _expected_criteria(scoring_points),
            }

        passing_criteria, failing_criteria, score = _evaluate_prediction(parsed_prediction, scoring_points)
        return {
            "passed": score == 1.0,
            "score": score,
            "unparseable": False,
            "response": result.content,
            "passing_criteria": passing_criteria,
            "failing_criteria": failing_criteria,
        }

    def summarize(self, scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(scored_rows)
        if total == 0:
            return {
                "suite": self.suite_name,
                "cases_total": 0,
                "cases_scored": 0,
                "cases_unparseable": 0,
                "pass_rate": 0.0,
                "average_score": 0.0,
                "by_difficulty": {},
            }

        scores = [float(row["score"].get("score", 0.0)) for row in scored_rows]
        unparseable = sum(1 for row in scored_rows if row["score"].get("unparseable"))
        passed = sum(1 for row in scored_rows if row["score"].get("passed"))

        by_difficulty: dict[str, dict[str, Any]] = {}
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in scored_rows:
            difficulty = str(row["metadata"].get("difficulty", "unknown"))
            grouped.setdefault(difficulty, []).append(row)
        for difficulty, rows in grouped.items():
            difficulty_scores = [float(row["score"].get("score", 0.0)) for row in rows]
            by_difficulty[difficulty] = {
                "count": len(rows),
                "pass_rate": round(sum(1 for row in rows if row["score"].get("passed")) / len(rows), 4),
                "average_score": round(mean(difficulty_scores), 4),
            }

        return {
            "suite": self.suite_name,
            "cases_total": total,
            "cases_scored": total,
            "cases_unparseable": unparseable,
            "pass_rate": round(passed / total, 4),
            "average_score": round(mean(scores), 4),
            "by_difficulty": by_difficulty,
        }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _dataset_base_dir(root: Path) -> Path:
    data_dir = root / "dataset" / "data"
    if data_dir.exists():
        return data_dir
    return root / "dataset"


def _dataset_prompt_path(root: Path, dataset: str) -> Path:
    if dataset == "Bank":
        filename = "basic_prompt_Bank.py"
    elif dataset == "Telecom":
        filename = "basic_prompt_Telecom.py"
    elif dataset.startswith("Market/"):
        filename = "basic_prompt_Market.py"
    else:
        raise ValueError(f"Unsupported OpenRCA dataset: {dataset}")
    return root / "rca" / "baseline" / "rca_agent" / "prompt" / filename


def _load_openrca_schema(root: Path, dataset: str) -> str:
    prompt_path = _dataset_prompt_path(root, dataset)
    spec = spec_from_file_location(f"openrca_prompt_{_slug(dataset)}", prompt_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load OpenRCA prompt module from {prompt_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(module.schema)


def _date_folder_name(datetime_text: str) -> str:
    return Path(datetime_text.split(" ")[0].replace("-", "_")).name


def _required_fields(scoring_points: str) -> list[str]:
    fields: list[str] = []
    if _TIME_PATTERN.search(scoring_points):
        fields.append("root cause occurrence datetime")
    if _COMPONENT_PATTERN.search(scoring_points):
        fields.append("root cause component")
    if _REASON_PATTERN.search(scoring_points):
        fields.append("root cause reason")
    return fields


def _build_task(*, dataset: str, date_folder: str, instruction: str, required_fields: list[str]) -> str:
    example = {"1": {field: f"<{field}>" for field in required_fields}}
    return (
        "OpenRCA benchmark task.\n\n"
        f"Original instruction:\n{instruction}\n\n"
        f"Relevant raw telemetry directory in the workspace:\n`dataset/{dataset}/telemetry/{date_folder}/`\n\n"
        "Read `openrca_context.md` before analyzing the telemetry files.\n"
        "Use the raw files from the relevant day folder as your evidence.\n"
        "Return only one JSON object, without markdown fences or extra commentary.\n"
        "This task describes a single failure, so return only key `\"1\"`.\n"
        f"Include only these fields in `\"1\"`: {', '.join(required_fields)}.\n"
        f"Use this shape:\n{json.dumps(example, indent=2)}"
    )


def _telemetry_artifacts(*, data_root: Path, dataset: str, telemetry_root: Path) -> list[ArtifactInput]:
    artifacts: list[ArtifactInput] = []
    for source_path in sorted(path for path in telemetry_root.rglob("*") if path.is_file()):
        relative = source_path.relative_to(data_root)
        artifacts.append(
            ArtifactInput(
                name=f"dataset/{relative.as_posix()}",
                source_path=str(source_path),
            )
        )
    return artifacts


def _difficulty(task_index: str) -> str:
    try:
        task_num = int(task_index.split("_", maxsplit=1)[1])
    except (IndexError, ValueError):
        return "unknown"
    if task_num <= 3:
        return "easy"
    if task_num <= 6:
        return "middle"
    return "hard"


def _parse_prediction(content: str) -> list[dict[str, str]] | None:
    text = content.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
        if match:
            text = match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, dict) and any(str(key).isdigit() for key in payload):
        ordered: list[dict[str, str]] = []
        for key in sorted(payload, key=lambda item: int(item) if str(item).isdigit() else str(item)):
            value = payload[key]
            if not isinstance(value, dict):
                return None
            ordered.append({str(field): str(field_value) for field, field_value in value.items()})
        return ordered

    if isinstance(payload, dict):
        return [{str(field): str(field_value) for field, field_value in payload.items()}]
    return None


def _evaluate_prediction(predictions: list[dict[str, str]], scoring_points: str) -> tuple[list[str], list[str], float]:
    components = _COMPONENT_PATTERN.findall(scoring_points)
    reasons = _REASON_PATTERN.findall(scoring_points)
    times = _TIME_PATTERN.findall(scoring_points)

    prediction_length = len(predictions)
    expected_length = max(len(components), len(reasons), len(times))
    total_criteria = len(components) + len(reasons) + len(times)
    if prediction_length != expected_length or total_criteria == 0:
        return [], _expected_criteria(scoring_points), 0.0

    best_score = -1
    best_passing: list[str] = []
    for permutation in itertools.permutations(predictions):
        current_score = 0
        current_passing: list[str] = []
        for index in range(expected_length):
            prediction = permutation[index]
            if len(components) == expected_length and prediction.get("root cause component") == components[index]:
                current_score += 1
                current_passing.append(components[index])
            if len(reasons) == expected_length and prediction.get("root cause reason") == reasons[index]:
                current_score += 1
                current_passing.append(reasons[index])
            if len(times) == expected_length and _within_one_minute(times[index], prediction.get("root cause occurrence datetime", "")):
                current_score += 1
                current_passing.append(times[index])
        if current_score > best_score:
            best_score = current_score
            best_passing = current_passing

    failing = list(set(_expected_criteria(scoring_points)) - set(best_passing))
    return best_passing, failing, round(best_score / total_criteria, 2)


def _expected_criteria(scoring_points: str) -> list[str]:
    return _COMPONENT_PATTERN.findall(scoring_points) + _REASON_PATTERN.findall(scoring_points) + _TIME_PATTERN.findall(scoring_points)


def _within_one_minute(expected_time: str, predicted_time: str) -> bool:
    time_format = "%Y-%m-%d %H:%M:%S"
    try:
        expected_dt = datetime.strptime(Path(expected_time).name, time_format)
        predicted_dt = datetime.strptime(Path(predicted_time).name, time_format)
    except ValueError:
        return False
    return abs(expected_dt - predicted_dt).total_seconds() <= 60


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

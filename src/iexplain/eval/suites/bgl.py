from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from iexplain.eval.base import EvalCase, SuiteAdapter
from iexplain.runtime.models import ArtifactInput, RunResult


DEFAULT_SMOKE_IDS = {
    "q1_error_count",
    "q3_top_component",
    "q4_top3_components",
    "q5_peak_error_hour",
    "q9_unique_nodes",
    "q12_component_most_errors",
}


class BglSettings(BaseModel):
    log_file: str
    ground_truth_file: str
    tier: str = "smoke"
    selected_ids: list[str] = Field(default_factory=list)


def _extract_json(text: str) -> Any:
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped, count=1)
        stripped = re.sub(r"\s*```$", "", stripped, count=1)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(stripped[start : end + 1])
    raise ValueError("Could not locate JSON object in response.")


class BglSuite(SuiteAdapter):
    suite_name = "bgl"

    def load_cases(self, settings: dict[str, Any]) -> list[EvalCase]:
        cfg = BglSettings.model_validate(settings)
        log_file = Path(cfg.log_file).expanduser().resolve()
        ground_truth = json.loads(Path(cfg.ground_truth_file).expanduser().resolve().read_text(encoding="utf-8"))
        questions = list(ground_truth["evaluation_questions"])
        tier = cfg.tier.strip().lower()
        if tier == "smoke":
            questions = [item for item in questions if item["id"] in DEFAULT_SMOKE_IDS]
        elif tier not in {"full", "all"}:
            raise ValueError(f"Unsupported BGL tier: {cfg.tier}")
        if cfg.selected_ids:
            wanted = set(cfg.selected_ids)
            questions = [item for item in questions if item["id"] in wanted]

        log_content = log_file.read_text(encoding="utf-8", errors="replace")
        cases = []
        for question in questions:
            cases.append(
                EvalCase(
                    case_id=str(question["id"]),
                    task=str(question["question"]),
                    artifacts=[ArtifactInput(name="bgl.log", content=log_content)],
                    metadata=question,
                )
            )
        return cases

    def score_case(self, case: EvalCase, result: RunResult) -> dict[str, Any]:
        parsed = _extract_json(result.content)
        answer = parsed["answer"] if isinstance(parsed, dict) and "answer" in parsed else parsed
        answer_type = str(case.metadata["answer_type"])
        if answer_type == "integer":
            actual = int(re.findall(r"-?\d+", str(answer))[0]) if isinstance(answer, str) else int(answer)
            expected = int(case.metadata["expected"])
            tolerance = int(case.metadata.get("tolerance", 0))
            passed = abs(actual - expected) <= tolerance
            details = f"expected={expected} actual={actual} tolerance={tolerance}"
        elif answer_type == "string_match":
            actual = str(answer).strip().lower()
            expected_values = [str(item).strip().lower() for item in case.metadata["expected"]]
            passed = any(expected in actual or actual in expected for expected in expected_values)
            details = f"expected={expected_values} actual={actual}"
        elif answer_type == "list":
            actual = answer if isinstance(answer, list) else [item.strip() for item in str(answer).split(",") if item.strip()]
            actual_norm = sorted(str(item).strip().lower() for item in actual)
            expected_norm = sorted(str(item).strip().lower() for item in case.metadata["expected"])
            passed = actual_norm == expected_norm
            details = f"expected={expected_norm} actual={actual_norm}"
        else:
            raise ValueError(f"Unsupported answer_type: {answer_type}")
        return {
            "passed": passed,
            "answer_type": answer_type,
            "details": details,
            "response": result.content,
        }

    def summarize(self, scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
        passed = sum(1 for row in scored_rows if row["score"].get("passed"))
        total = len(scored_rows)
        return {
            "suite": self.suite_name,
            "cases_total": total,
            "cases_passed": passed,
            "cases_failed": total - passed,
            "pass_rate": round((passed / total) * 100.0, 2) if total else 0.0,
        }

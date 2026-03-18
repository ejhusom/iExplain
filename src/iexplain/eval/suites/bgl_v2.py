from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from iexplain.eval.base import EvalCase, SuiteAdapter
from iexplain.runtime.models import ArtifactInput, RunResult


class BglV2Settings(BaseModel):
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


class BglV2Suite(SuiteAdapter):
    suite_name = "bgl_v2"

    def load_cases(self, settings: dict[str, Any]) -> list[EvalCase]:
        cfg = BglV2Settings.model_validate(settings)
        log_file = Path(cfg.log_file).expanduser().resolve()
        ground_truth_path = Path(cfg.ground_truth_file).expanduser().resolve()
        ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
        case_records = list(ground_truth["cases"])
        tier = cfg.tier.strip().lower()
        case_records = [item for item in case_records if self._include_tier(str(item.get("tier", "smoke")).lower(), tier)]
        if cfg.selected_ids:
            wanted = set(cfg.selected_ids)
            case_records = [item for item in case_records if item["id"] in wanted]

        log_content = log_file.read_text(encoding="utf-8", errors="replace")
        ground_truth_root = ground_truth_path.parent
        cases = []
        for record in case_records:
            artifacts = [ArtifactInput(name="bgl.log", content=log_content)]
            for item in record.get("artifacts", []):
                artifact_path = Path(item["path"]) if Path(item["path"]).is_absolute() else (ground_truth_root / item["path"]).resolve()
                artifacts.append(
                    ArtifactInput(
                        name=str(item["name"]),
                        content=artifact_path.read_text(encoding="utf-8", errors="replace"),
                    )
                )
            task = str(record["task"]).strip()
            required_output = list(record.get("required_output", ["answer"]))
            task += f"\nReturn only JSON with keys {', '.join(required_output)}."
            if "evidence" in required_output:
                task += "\nUse `sample_refs` from `bgl_query` as evidence references."
            if record.get("instructions"):
                task += f"\n{record['instructions']}"
            cases.append(
                EvalCase(
                    case_id=str(record["id"]),
                    task=task,
                    artifacts=artifacts,
                    metadata=record,
                )
            )
        return cases

    def score_case(self, case: EvalCase, result: RunResult) -> dict[str, Any]:
        parsed = _extract_json(result.content)
        if not isinstance(parsed, dict):
            raise ValueError("BGL v2 responses must decode to a JSON object.")
        required_output = list(case.metadata.get("required_output", ["answer"]))
        missing_fields = [field for field in required_output if field not in parsed]
        fields_passed = not missing_fields

        answer = parsed.get("answer")
        answer_type = str(case.metadata["answer_type"])
        answer_passed, details = self._score_answer(case.metadata, answer_type, answer)

        evidence_passed = True
        if "evidence" in required_output:
            evidence = parsed.get("evidence")
            evidence_passed = isinstance(evidence, list) and len(evidence) >= 1

        passed = answer_passed and fields_passed and evidence_passed
        return {
            "passed": passed,
            "answer_passed": answer_passed,
            "fields_passed": fields_passed,
            "evidence_passed": evidence_passed,
            "answer_type": answer_type,
            "missing_fields": missing_fields,
            "details": details,
            "response": result.content,
        }

    def summarize(self, scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
        passed = sum(1 for row in scored_rows if row["score"].get("passed"))
        total = len(scored_rows)
        answer_passed = sum(1 for row in scored_rows if row["score"].get("answer_passed"))
        evidence_required = sum(1 for row in scored_rows if "evidence" in row.get("metadata", {}).get("required_output", []))
        evidence_passed = sum(1 for row in scored_rows if row["score"].get("evidence_passed"))
        return {
            "suite": self.suite_name,
            "cases_total": total,
            "cases_passed": passed,
            "cases_failed": total - passed,
            "pass_rate": round((passed / total) * 100.0, 2) if total else 0.0,
            "answer_passed": answer_passed,
            "evidence_required": evidence_required,
            "evidence_passed": evidence_passed,
            "by_category": self._summarize_group(scored_rows, "category"),
            "by_tier": self._summarize_group(scored_rows, "tier"),
        }

    @staticmethod
    def _include_tier(case_tier: str, requested_tier: str) -> bool:
        levels = {"smoke": 1, "full": 2, "challenge": 3, "all": 3}
        requested = levels.get(requested_tier)
        current = levels.get(case_tier)
        if requested is None or current is None:
            raise ValueError(f"Unsupported BGL v2 tier: {requested_tier}")
        return current <= requested

    @staticmethod
    def _normalize_list_item(item: Any) -> str:
        if isinstance(item, dict):
            for key in ("value", "answer", "component", "node_id", "hour", "level"):
                value = item.get(key)
                if value is not None:
                    return str(value).strip().lower()
        return str(item).strip().lower()

    @staticmethod
    def _summarize_group(scored_rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for row in scored_rows:
            group_value = str(row.get("metadata", {}).get(key, "unknown"))
            group = groups.setdefault(group_value, {"cases_total": 0, "cases_passed": 0})
            group["cases_total"] += 1
            if row["score"].get("passed"):
                group["cases_passed"] += 1
        for group in groups.values():
            total = group["cases_total"]
            group["cases_failed"] = total - group["cases_passed"]
            group["pass_rate"] = round((group["cases_passed"] / total) * 100.0, 2) if total else 0.0
        return groups

    @staticmethod
    def _score_answer(metadata: dict[str, Any], answer_type: str, answer: Any) -> tuple[bool, str]:
        if answer_type == "integer":
            actual = int(re.findall(r"-?\d+", str(answer))[0]) if isinstance(answer, str) else int(answer)
            expected = int(metadata["expected"])
            tolerance = int(metadata.get("tolerance", 0))
            passed = abs(actual - expected) <= tolerance
            return passed, f"expected={expected} actual={actual} tolerance={tolerance}"
        if answer_type == "string_match":
            actual = str(answer).strip().lower()
            expected_values = [str(item).strip().lower() for item in metadata["expected"]]
            passed = any(expected in actual or actual in expected for expected in expected_values)
            return passed, f"expected={expected_values} actual={actual}"
        if answer_type == "list":
            actual = answer if isinstance(answer, list) else [item.strip() for item in str(answer).split(",") if item.strip()]
            actual_norm = [BglV2Suite._normalize_list_item(item) for item in actual]
            expected_norm = [str(item).strip().lower() for item in metadata["expected"]]
            if metadata.get("order_matters"):
                passed = actual_norm == expected_norm
            else:
                passed = sorted(actual_norm) == sorted(expected_norm)
            return passed, f"expected={expected_norm} actual={actual_norm}"
        if answer_type == "insufficient_evidence":
            actual = str(answer).strip().lower()
            expected_values = [str(item).strip().lower() for item in metadata["expected"]]
            passed = actual in expected_values
            return passed, f"expected={expected_values} actual={actual}"
        raise ValueError(f"Unsupported BGL v2 answer_type: {answer_type}")

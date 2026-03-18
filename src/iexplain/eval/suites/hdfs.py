from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from iexplain.eval.base import EvalCase, SuiteAdapter
from iexplain.runtime.models import ArtifactInput, RunResult


class HdfsSettings(BaseModel):
    labels_csv: str
    sessions_dir: str
    sample_limit: int = 0
    seed: int = 42


def _normalize_label(text: str) -> int | None:
    if '"label": 0' in text or '"label":0' in text:
        return 0
    if '"label": 1' in text or '"label":1' in text:
        return 1
    matches = re.findall(r"\b[01]\b", re.sub(r"\d{4,}", " ", text))
    if matches:
        return int(matches[-1])
    if re.search(r"\bnormal\b", text, re.I):
        return 0
    if re.search(r"\banomal", text, re.I):
        return 1
    return None


class HdfsSuite(SuiteAdapter):
    suite_name = "hdfs"

    def load_cases(self, settings: dict[str, Any]) -> list[EvalCase]:
        cfg = HdfsSettings.model_validate(settings)
        labels_path = Path(cfg.labels_csv).expanduser().resolve()
        sessions_dir = Path(cfg.sessions_dir).expanduser().resolve()
        labels: dict[str, int] = {}
        with labels_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                block_id = str(row.get("BlockId", "")).strip()
                label = str(row.get("Label", "")).strip().lower()
                if not block_id:
                    continue
                labels[block_id] = 1 if label == "anomaly" else 0

        cases = []
        for block_id, expected in sorted(labels.items()):
            session_path = sessions_dir / f"{block_id}.log"
            if not session_path.exists():
                continue
            logs = session_path.read_text(encoding="utf-8", errors="replace").strip()
            if not logs:
                continue
            cases.append(
                EvalCase(
                    case_id=block_id,
                    task=(
                        "Classify the HDFS session in `session.log` as normal (0) or anomalous (1). "
                        "Return JSON with keys `label`, `summary`, and `signals`."
                    ),
                    artifacts=[ArtifactInput(name="session.log", content=logs)],
                    metadata={"expected_label": expected},
                )
            )
        if cfg.sample_limit > 0 and len(cases) > cfg.sample_limit:
            rng = Random(cfg.seed)
            cases = rng.sample(cases, k=cfg.sample_limit)
            cases.sort(key=lambda item: item.case_id)
        return cases

    def score_case(self, case: EvalCase, result: RunResult) -> dict[str, Any]:
        predicted = _normalize_label(result.content)
        expected = int(case.metadata["expected_label"])
        passed = predicted == expected
        return {
            "passed": passed,
            "expected_label": expected,
            "predicted_label": predicted,
            "unparseable": predicted is None,
            "response": result.content,
        }

    def summarize(self, scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
        parsed = [
            row
            for row in scored_rows
            if row["score"].get("predicted_label") is not None and row["score"].get("expected_label") is not None
        ]
        y_true = [row["score"]["expected_label"] for row in parsed]
        y_pred = [row["score"]["predicted_label"] for row in parsed]
        tp = sum(yt == 1 and yp == 1 for yt, yp in zip(y_true, y_pred))
        tn = sum(yt == 0 and yp == 0 for yt, yp in zip(y_true, y_pred))
        fp = sum(yt == 0 and yp == 1 for yt, yp in zip(y_true, y_pred))
        fn = sum(yt == 1 and yp == 0 for yt, yp in zip(y_true, y_pred))
        total = len(y_true)
        accuracy = (tp + tn) / total if total else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        return {
            "suite": self.suite_name,
            "cases_total": len(scored_rows),
            "cases_scored": total,
            "cases_unparseable": sum(1 for row in scored_rows if row["score"].get("unparseable")),
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "TP": tp,
            "TN": tn,
            "FP": fp,
            "FN": fn,
        }

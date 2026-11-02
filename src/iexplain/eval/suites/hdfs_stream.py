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

_TS_RE = re.compile(r"^(\d{6})\s+(\d{6})\b")
_OBJECT_RE = re.compile(r"\{[^{}]*?\"block_id\"[^{}]*?\}", re.DOTALL)


class HdfsStreamSettings(BaseModel):
    labels_csv: str
    sessions_dir: str
    window_size: int = 8
    sample_limit: int = 40
    seed: int = 42


def _timestamp_key(line: str) -> tuple[str, str]:
    match = _TS_RE.match(line)
    if match:
        return match.group(1), match.group(2)
    return "999999", "999999"


def _parse_block_labels(text: str) -> dict[str, int]:
    """Extract a {block_id: label} mapping from a model response.

    Handles the JSON contract first and falls back to a tolerant per-line scan so
    that minor format drift does not silently zero out a window.
    """
    if not text:
        return {}

    cleaned = re.sub(r"```[a-zA-Z]*", "", text).replace("```", "")
    labels: dict[str, int] = {}

    for fragment in _OBJECT_RE.findall(cleaned):
        try:
            obj = json.loads(fragment)
        except json.JSONDecodeError:
            continue
        block_id = str(obj.get("block_id", "")).strip()
        label = obj.get("label")
        if block_id.startswith("blk_") and label in (0, 1, "0", "1"):
            labels[block_id] = int(label)

    if labels:
        return labels

    for match in re.finditer(
        r"(blk_-?\d+)\D{0,40}?(\b[01]\b|anomal\w*|normal)", cleaned, re.IGNORECASE
    ):
        block_id = match.group(1)
        token = match.group(2).lower()
        if token in {"0", "1"}:
            labels[block_id] = int(token)
        elif token.startswith("anomal"):
            labels[block_id] = 1
        elif token.startswith("normal"):
            labels[block_id] = 0
    return labels


class HdfsStreamSuite(SuiteAdapter):
    """Interleaved multi-block HDFS anomaly detection.

    Each case bundles ``window_size`` complete block sessions into a single
    timestamp-interleaved ``stream.log`` artifact. The agent must de-interleave the
    stream and classify every candidate block, so that the execution architecture
    (single_pass, pipeline, agent, planner) is exercised on a task that genuinely
    requires navigating evidence rather than reading one short session.
    """

    suite_name = "hdfs_stream"

    def load_cases(self, settings: dict[str, Any]) -> list[EvalCase]:
        cfg = HdfsStreamSettings.model_validate(settings)
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

        entries: list[tuple[str, int, str]] = []
        for block_id, expected in sorted(labels.items()):
            session_path = sessions_dir / f"{block_id}.log"
            if not session_path.exists():
                continue
            logs = session_path.read_text(encoding="utf-8", errors="replace").strip()
            if not logs:
                continue
            entries.append((block_id, expected, logs))

        if cfg.sample_limit > 0 and len(entries) > cfg.sample_limit:
            rng = Random(cfg.seed)
            entries = rng.sample(entries, k=cfg.sample_limit)
            entries.sort(key=lambda item: item[0])

        cases: list[EvalCase] = []
        window = max(1, cfg.window_size)
        for start in range(0, len(entries), window):
            chunk = entries[start : start + window]
            if not chunk:
                continue
            lines: list[str] = []
            for _, _, logs in chunk:
                lines.extend(line for line in logs.splitlines() if line.strip())
            stream = sorted(lines, key=_timestamp_key)
            block_ids = [block_id for block_id, _, _ in chunk]
            expected_map = {block_id: expected for block_id, expected, _ in chunk}
            task = (
                "The file `stream.log` contains interleaved log lines from several HDFS "
                "block operations. For EACH of the block IDs listed below, gather that "
                "block's log lines from the stream and classify its operation as normal "
                "(0) or anomalous (1):\n"
                + "\n".join(f"- {block_id}" for block_id in block_ids)
                + "\n\nReturn ONLY a JSON object of the form "
                '{"blocks": [{"block_id": "<id>", "label": 0 or 1}, ...]} with exactly '
                "one entry for every block ID listed above."
            )
            cases.append(
                EvalCase(
                    case_id=f"window_{start // window:02d}",
                    task=task,
                    artifacts=[ArtifactInput(name="stream.log", content="\n".join(stream) + "\n")],
                    metadata={"expected": expected_map, "block_ids": block_ids},
                )
            )
        return cases

    def score_case(self, case: EvalCase, result: RunResult) -> dict[str, Any]:
        expected_map = {str(k): int(v) for k, v in case.metadata["expected"].items()}
        predicted_map = _parse_block_labels(result.content)
        per_block: dict[str, dict[str, Any]] = {}
        for block_id, expected in expected_map.items():
            per_block[block_id] = {
                "expected": expected,
                "predicted": predicted_map.get(block_id),
            }
        missing = sum(1 for detail in per_block.values() if detail["predicted"] is None)
        return {
            "per_block": per_block,
            "n_blocks": len(expected_map),
            "n_missing": missing,
            "unparseable": missing == len(expected_map),
            "response": result.content,
        }

    def summarize(self, scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
        tp = tn = fp = fn = 0
        total = 0
        missing = 0
        for row in scored_rows:
            for detail in row["score"].get("per_block", {}).values():
                expected = detail["expected"]
                predicted = detail["predicted"]
                total += 1
                if predicted is None:
                    missing += 1
                    predicted = 1 - expected
                if expected == 1 and predicted == 1:
                    tp += 1
                elif expected == 0 and predicted == 0:
                    tn += 1
                elif expected == 0 and predicted == 1:
                    fp += 1
                elif expected == 1 and predicted == 0:
                    fn += 1
        accuracy = (tp + tn) / total if total else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        return {
            "suite": self.suite_name,
            "cases_total": len(scored_rows),
            "blocks_total": total,
            "blocks_missing": missing,
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

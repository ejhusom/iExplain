from __future__ import annotations

import io
import json
from pathlib import Path

from iexplain.eval.analyze import write_report
from iexplain.eval.runner import run_experiment, run_matrix_experiment
from iexplain.runtime.models import RunRequest, RunResult, ToolCallRecord
from iexplain.runtime.service import IExplainService


class StubEvalService(IExplainService):
    def __init__(self):
        from iexplain.config import AppConfig

        super().__init__(AppConfig.from_file("config/app.toml"))

    def run(self, request: RunRequest) -> RunResult:
        content = '{"label": 0, "summary": "normal", "signals": ["clean flow"]}'
        return RunResult(
            content=content,
            mode="pipeline",
            profile=request.profile,
            prompt_variants={
                "log_preprocessor": "hdfs_few_shot",
                "log_anomaly_detector": "hdfs_few_shot",
                "log_explainer": "hdfs_few_shot",
            },
            tool_calls=[ToolCallRecord(name="read_file")],
            events=[
                {
                    "type": "assistant",
                    "turn": 1,
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    },
                },
                {
                    "type": "tool_call",
                    "turn": 1,
                    "name": "read_file",
                },
                {
                    "type": "assistant",
                    "turn": 2,
                    "usage": {
                        "input_tokens": 12,
                        "output_tokens": 6,
                        "total_tokens": 18,
                    },
                },
            ],
        )


def test_hdfs_experiment_runner(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "blk_1.log").write_text("line 1\nline 2", encoding="utf-8")
    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text("BlockId,Label\nblk_1,Normal\n", encoding="utf-8")
    experiment_path = tmp_path / "experiment.json"
    experiment_path.write_text(
        json.dumps(
            {
                "name": "test-hdfs",
                "suite": {
                    "type": "hdfs",
                    "settings": {
                        "labels_csv": str(labels_csv),
                        "sessions_dir": str(sessions_dir),
                        "sample_limit": 0,
                        "seed": 42,
                    },
                },
                "runtime": {"profile": "hdfs_eval", "overrides": {}},
                "output_dir": "runs",
                "tags": {"suite": "hdfs"},
            }
        ),
        encoding="utf-8",
    )
    run_dir = run_experiment(experiment_path, service=StubEvalService())
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["metrics"]["suite"] == "hdfs"
    assert summary["cases_total"] == 1
    assert summary["resolved_runtime"]["pipeline"] == "hdfs_anomaly"
    assert summary["resolved_runtime"]["model"]["model"] == "gpt-4o-mini"
    assert summary["performance"]["assistant_turns"] == 2
    assert summary["performance"]["tool_calls"] == 1
    assert summary["performance"]["total_tokens"] == 33
    assert summary["prompt_variants_seen"]["log_anomaly_detector"] == ["hdfs_few_shot"]
    assert summary["prompt_variants_seen"]["log_explainer"] == ["hdfs_few_shot"]
    row = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["case_metrics"]["assistant_turns"] == 2
    assert row["case_metrics"]["tool_calls"] == 1


def test_bgl_experiment_runner(tmp_path: Path):
    log_file = tmp_path / "bgl.log"
    log_file.write_text("sample bgl log", encoding="utf-8")
    ground_truth = tmp_path / "ground_truth.json"
    ground_truth.write_text(
        json.dumps(
            {
                "evaluation_questions": [
                    {
                        "id": "q1_error_count",
                        "question": "How many ERROR level log entries are in this file?",
                        "answer_type": "integer",
                        "expected": 41,
                        "tolerance": 0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    experiment_path = tmp_path / "bgl_experiment.json"
    experiment_path.write_text(
        json.dumps(
            {
                "name": "test-bgl",
                "suite": {
                    "type": "bgl",
                    "settings": {
                        "log_file": str(log_file),
                        "ground_truth_file": str(ground_truth),
                        "tier": "smoke",
                    },
                },
                "runtime": {"profile": "bgl_eval", "overrides": {}},
                "output_dir": "runs",
                "tags": {"suite": "bgl"},
            }
        ),
        encoding="utf-8",
    )

    class StubBglService(StubEvalService):
        def run(self, request: RunRequest) -> RunResult:
            return RunResult(
                content='{"answer": 41}',
                mode="pipeline",
                profile=request.profile,
                prompt_variants={"bgl_qa": "default"},
                tool_calls=[ToolCallRecord(name="bgl_answer_question")],
                events=[
                    {
                        "type": "assistant",
                        "turn": 1,
                        "usage": {
                            "input_tokens": 8,
                            "output_tokens": 3,
                            "total_tokens": 11,
                        },
                    },
                    {
                        "type": "tool_call",
                        "turn": 1,
                        "name": "bgl_answer_question",
                    },
                    {
                        "type": "assistant",
                        "turn": 2,
                        "usage": {
                            "input_tokens": 9,
                            "output_tokens": 4,
                            "total_tokens": 13,
                        },
                    },
                ],
            )

    run_dir = run_experiment(experiment_path, service=StubBglService())
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["metrics"]["suite"] == "bgl"
    assert summary["metrics"]["cases_passed"] == 1
    assert summary["suite_settings"]["tier"] == "smoke"
    assert summary["resolved_runtime"]["pipeline"] == "bgl_question_answering"
    assert summary["performance"]["total_tokens"] == 24
    report = write_report(run_dir.parent)
    bgl_rows = [row for row in report["comparison_rows"] if row["name"] == "test-bgl"]
    assert bgl_rows[0]["pipeline"] == "bgl_question_answering"
    assert bgl_rows[0]["prompt_variants"] == "bgl_qa=default"


def test_matrix_runner_and_analysis_outputs(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "blk_1.log").write_text("line 1\nline 2", encoding="utf-8")
    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text("BlockId,Label\nblk_1,Normal\n", encoding="utf-8")
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "name": "test-hdfs-matrix",
                "base_experiment": {
                    "name": "test-hdfs-matrix-run",
                    "suite": {
                        "type": "hdfs",
                        "settings": {
                            "labels_csv": str(labels_csv),
                            "sessions_dir": str(sessions_dir),
                            "sample_limit": 0,
                            "seed": 42,
                        },
                    },
                    "runtime": {"profile": "hdfs_eval", "overrides": {}},
                    "output_dir": "runs",
                    "tags": {"suite": "hdfs"},
                },
                "axes": [
                    {
                        "name": "model",
                        "values": [
                            {
                                "label": "mini",
                                "patch": {"runtime": {"overrides": {"model": "gpt-4o-mini"}}},
                            },
                            {
                                "label": "full",
                                "patch": {"runtime": {"overrides": {"model": "gpt-4o"}}},
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    progress_stream = io.StringIO()
    run_dirs = run_matrix_experiment(
        matrix_path,
        service=StubEvalService(),
        show_progress=True,
        progress_stream=progress_stream,
    )

    assert len(run_dirs) == 2
    first_summary = json.loads((run_dirs[0] / "summary.json").read_text(encoding="utf-8"))
    assert first_summary["matrix_context"]["name"] == "test-hdfs-matrix"
    assert first_summary["matrix_context"]["combination"]["model"] in {"mini", "full"}
    progress_text = progress_stream.getvalue()
    assert "Matrix test-hdfs-matrix" in progress_text
    assert "[1/2]" in progress_text
    assert "overall 1/2" in progress_text

    plots_dir = tmp_path / "plots"
    markdown_output = tmp_path / "report.md"
    json_output = tmp_path / "report.json"
    report = write_report(
        run_dirs[0].parent,
        markdown_output=markdown_output,
        json_output=json_output,
        plots_dir=plots_dir,
    )

    assert report["matrix_factor_names"] == ["model"]
    assert any(plot["kind"] == "score_by_factor" for plot in report["plots"])
    for plot in report["plots"]:
        assert Path(plot["path"]).exists()
    markdown_text = markdown_output.read_text(encoding="utf-8")
    assert "## Matrix Factors" in markdown_text
    assert "![hdfs: score by run]" in markdown_text

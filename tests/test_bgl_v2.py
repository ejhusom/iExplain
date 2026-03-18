from __future__ import annotations

import json
from pathlib import Path

from iexplain.eval.runner import run_experiment
from iexplain.runtime.models import RunRequest, RunResult, ToolCallRecord
from iexplain.runtime.pipelines import get_pipeline
from iexplain.runtime.service import IExplainService
from iexplain.runtime.tools import ToolContext, build_tools


def test_bgl_query_tool_filters_and_ranks(tmp_path):
    log_path = tmp_path / "bgl.log"
    log_path.write_text(
        "\n".join(
            [
                "- 111 222 333 2005-06-03-12.00.00.000000 NODE1 RAS MMCS ERROR first",
                "- 111 222 333 2005-06-03-12.01.00.000000 NODE2 RAS MMCS ERROR second",
                "- 111 222 333 2005-06-03-12.02.00.000000 NODE2 RAS DISCOVERY INFO third",
                "- 111 222 333 2005-06-03-16.02.00.000000 NODE3 RAS MMCS ERROR fourth",
            ]
        ),
        encoding="utf-8",
    )
    tools = build_tools(["bgl_query"], ToolContext(tmp_path))
    result = tools["bgl_query"].call(
        {
            "path": "bgl.log",
            "filters": {"component": "MMCS", "hour": "12", "level": "ERROR"},
            "count_by": ["node_id"],
            "unique_fields": ["node_id"],
            "include_samples": True,
        }
    )
    assert result["matching_rows"] == 2
    assert result["unique_counts"]["node_id"] == 2
    assert result["counts_by"]["node_id"][0] == {"value": "NODE1", "count": 1}
    assert result["sample_refs"][0] == "bgl.log:1"
    assert get_pipeline("bgl_v2_question_answering")[0].tools == ["bgl_query", "read_file"]


class StubBglV2Service(IExplainService):
    def __init__(self):
        from iexplain.config import AppConfig

        super().__init__(AppConfig.from_file("config/app.toml"))

    def run(self, request: RunRequest) -> RunResult:
        return RunResult(
            content='{"answer":"NODE1","evidence":["bgl.log:1"]}',
            mode="pipeline",
            profile=request.profile,
            prompt_variants={"bgl_qa": "v2"},
            tool_calls=[ToolCallRecord(name="bgl_query")],
            events=[
                {"type": "assistant", "turn": 1, "usage": {"input_tokens": 8, "output_tokens": 3, "total_tokens": 11}},
                {"type": "tool_call", "turn": 1, "name": "bgl_query"},
                {"type": "assistant", "turn": 2, "usage": {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13}},
            ],
        )


def test_bgl_v2_experiment_runner(tmp_path: Path):
    log_file = tmp_path / "bgl.log"
    log_file.write_text("sample log", encoding="utf-8")
    focus_nodes = tmp_path / "focus_nodes.txt"
    focus_nodes.write_text("NODE1\nNODE2\n", encoding="utf-8")
    ground_truth = tmp_path / "ground_truth_v2.json"
    ground_truth.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "bglv2_test_case",
                        "tier": "smoke",
                        "category": "multi_artifact",
                        "task": "Using focus_nodes.txt, which listed node produced the most ERROR logs?",
                        "artifacts": [{"name": "focus_nodes.txt", "path": "focus_nodes.txt"}],
                        "answer_type": "string_match",
                        "expected": ["NODE1"],
                        "required_output": ["answer", "evidence"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    experiment_path = tmp_path / "bgl_v2_experiment.json"
    experiment_path.write_text(
        json.dumps(
            {
                "name": "test-bgl-v2",
                "suite": {
                    "type": "bgl_v2",
                    "settings": {
                        "log_file": str(log_file),
                        "ground_truth_file": str(ground_truth),
                        "tier": "smoke",
                    },
                },
                "runtime": {"profile": "bgl_v2_eval", "overrides": {}},
                "output_dir": "runs",
                "tags": {"suite": "bgl_v2"},
            }
        ),
        encoding="utf-8",
    )

    run_dir = run_experiment(experiment_path, service=StubBglV2Service())
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["metrics"]["suite"] == "bgl_v2"
    assert summary["metrics"]["cases_passed"] == 1
    assert summary["metrics"]["by_category"]["multi_artifact"]["cases_passed"] == 1
    assert summary["resolved_runtime"]["pipeline"] == "bgl_v2_question_answering"
    assert summary["prompt_variants_seen"]["bgl_qa"] == ["v2"]

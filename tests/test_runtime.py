from __future__ import annotations

from iexplain.intent_graphdb import (
    IntentBundle,
    IntentCondition,
    IntentContext,
    IntentExpectation,
    IntentObservation,
    IntentReportRecord,
)
from iexplain.config import AppConfig
from iexplain.runtime.llm import ToolCall
from iexplain.runtime.models import ArtifactInput, RunRequest
from iexplain.runtime.pipelines import get_pipeline
from iexplain.runtime.service import IExplainService
from iexplain.runtime.tools import ToolContext, build_tools

from tests.fakes import FakeStep, SequenceBackend


def test_pipeline_mode_hdfs_profile_runs():
    config = AppConfig.from_file("config/app.toml")
    backend = SequenceBackend(
        [
            FakeStep(content="1. Receive block\n2. Timeout while writing"),
            FakeStep(content='{"label": 1, "signals": ["timeout"]}'),
            FakeStep(content='{"label": 1, "summary": "Timeout during write path.", "signals": ["timeout"]}'),
        ]
    )
    service = IExplainService(config, backend=backend)
    result = service.run(
        RunRequest(
            task="Classify the HDFS session.",
            profile="hdfs_eval",
            artifacts=[ArtifactInput(name="session.log", content="timeout example")],
        )
    )
    assert '"label": 1' in result.content
    assert result.mode.value == "pipeline"
    trace = result.metadata["trace"]
    assert trace["resolved_runtime"]["pipeline"] == "hdfs_anomaly"
    assert trace["stages"][0]["name"] == "preprocess"
    assert trace["conversation"][0]["type"] == "assistant"


def test_planner_mode_can_delegate():
    config = AppConfig.from_file("config/app.toml")
    backend = SequenceBackend(
        [
            FakeStep(
                tool_calls=[ToolCall(id="call_1", name="delegate_log_analysis", arguments='{"subtask": "inspect the logs"}')]
            ),
            FakeStep(content="Delegated notes: nothing unusual."),
            FakeStep(content="Final answer based on delegated notes."),
        ]
    )
    service = IExplainService(config, backend=backend)
    result = service.run(
        RunRequest(
            task="Explain the log behavior.",
            profile="autonomous",
            artifacts=[ArtifactInput(name="notes.log", content="all good")],
        )
    )
    assert "Final answer" in result.content
    assert any(event.get("delegated_role") == "role_log_analyst" for event in result.events)
    trace = result.metadata["trace"]
    assert trace["delegated_roles"] == ["role_log_analyst"]
    assert "delegate_log_analysis" in trace["tool_sequence"]
    assert any(stage["name"] == "role_log_analyst" for stage in trace["stages"])


def test_bgl_stats_tool_computes_small_summary(tmp_path):
    log_path = tmp_path / "bgl.log"
    log_path.write_text(
        "\n".join(
            [
                "- 111 222 333 2005-06-03-12.00.00.000000 NODE1 RAS MMCS ERROR first",
                "- 111 222 333 2005-06-03-12.01.00.000000 NODE2 RAS MMCS ERROR second",
                "- 111 222 333 2005-06-03-13.01.00.000000 NODE3 RAS KERNEL INFO third",
            ]
        ),
        encoding="utf-8",
    )
    tools = build_tools(["bgl_file_stats"], ToolContext(tmp_path))
    result = tools["bgl_file_stats"].call({"path": "bgl.log"})
    assert result["total_lines"] == 3
    assert result["level_counts"]["ERROR"] == 2
    assert result["top_component"] == "MMCS"
    assert result["peak_error_hour"] == "12"
    assert result["component_with_most_errors"] == "MMCS"


def test_bgl_pipeline_uses_structured_question_tool(tmp_path):
    log_path = tmp_path / "bgl.log"
    log_path.write_text(
        "\n".join(
            [
                "- 111 222 333 2005-06-03-12.00.00.000000 NODE1 RAS MMCS ERROR first",
                "- 111 222 333 2005-06-03-12.01.00.000000 NODE2 RAS MMCS ERROR second",
                "- 111 222 333 2005-06-03-13.01.00.000000 NODE3 RAS KERNEL INFO third",
            ]
        ),
        encoding="utf-8",
    )
    tools = build_tools(["bgl_answer_question"], ToolContext(tmp_path))
    result = tools["bgl_answer_question"].call(
        {
            "question": "What are the top 3 components by log volume?",
            "path": "bgl.log",
        }
    )
    assert result["answer"] == ["MMCS", "KERNEL"]
    assert get_pipeline("bgl_question_answering")[0].tools == ["bgl_answer_question"]


def test_fetch_intent_bundle_tool_returns_compact_bundle(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self, base_url: str, repository_id: str, *, resource_prefix: str, timeout_seconds: int = 30):
            assert base_url == "http://localhost:7200"
            assert repository_id == "intents_and_intent_reports"
            assert resource_prefix == "http://5g4data.eu/5g4data#"

        def fetch_intent_bundle(self, intent_id: str) -> IntentBundle:
            assert intent_id == "If9587ca040be457d908d54e7aecc2ef6"
            return IntentBundle(
                intent_iri="http://5g4data.eu/5g4data#If9587ca040be457d908d54e7aecc2ef6",
                intent_name="If9587ca040be457d908d54e7aecc2ef6",
                handler="inOrch",
                owner="inSwitch",
                expectations=[
                    IntentExpectation(
                        iri="exp-1",
                        name="DeploymentExpectation",
                        kind="DeploymentExpectation",
                        description="Deploy AI inference service to edge datacenter",
                        target="deployment",
                    )
                ],
                conditions=[
                    IntentCondition(
                        iri="cond-1",
                        name="ComputeLatency",
                        description="Compute latency below threshold",
                        metric="computelatency",
                    )
                ],
                contexts=[
                    IntentContext(
                        iri="ctx-1",
                        name="DeploymentContext",
                        description="EC21 deployment context",
                        attributes={"Application": "ai-inference-service"},
                    )
                ],
                reports=[
                    IntentReportRecord(
                        iri="report-1",
                        report_number=1,
                        generated_at="2026-03-17T09:00:00Z",
                        state="StateIntentReceived",
                        reason="Deployment queued.",
                        handler="inOrch",
                        owner="inSwitch",
                    ),
                    IntentReportRecord(
                        iri="report-2",
                        report_number=2,
                        generated_at="2026-03-17T09:18:00Z",
                        state="StateCompliant",
                        reason="Workload moved and latency recovered.",
                        handler="inOrch",
                        owner="inSwitch",
                    ),
                ],
                observations=[
                    IntentObservation(
                        iri="obs-1",
                        condition="ComputeLatency",
                        metric="computelatency",
                        value=18.0,
                        unit="ms",
                        obtained_at="2026-03-17T09:17:00Z",
                    )
                ],
            )

    monkeypatch.setattr("iexplain.runtime.tools.GraphDBIntentClient", FakeClient)
    tools = build_tools(["fetch_intent_bundle"], ToolContext(tmp_path))
    result = tools["fetch_intent_bundle"].call({"intent_id": "If9587ca040be457d908d54e7aecc2ef6"})

    assert result["current_state"] == "StateCompliant"
    assert result["latest_reason"] == "Workload moved and latency recovered."
    assert result["counts"]["reports"] == 2
    assert result["timeline"][0]["state"] == "StateIntentReceived"
    assert result["observations"][0]["metric"] == "computelatency"
    assert get_pipeline("intent_summary")[0].tools == ["fetch_intent_bundle"]

from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from iexplain.api.app import create_app
from iexplain.config import AppConfig
from iexplain.runtime.models import RunRequest, RunResult
from iexplain.runtime.service import IExplainService


class StubService(IExplainService):
    def __init__(self):
        super().__init__(AppConfig.from_file("config/app.toml"))

    def run(self, request: RunRequest) -> RunResult:
        return RunResult(
            content=f"done: {request.task}",
            mode="agent",
            profile=request.profile,
            metadata={
                "trace": {
                    "request": {"task": request.task, "profile": request.profile, "artifacts": []},
                    "resolved_runtime": {"profile": request.profile, "mode": "agent", "pipeline": None, "model": {"model": "gpt-4o-mini"}},
                    "stages": [{"name": "agent", "role": "general_analyst", "assistant_turns": 1, "tool_calls": 0}],
                    "usage": {"assistant_turns": 1, "tool_calls": 0, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                }
            },
        )


def test_api_job_submission_and_polling(tmp_path):
    service = StubService()
    service.config.paths.runs_dir = str(tmp_path / "runs")
    app = create_app(service=service)
    with TestClient(app) as client:
        response = client.post("/api/v1/jobs", json={"run": {"task": "test task"}})
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        for _ in range(20):
            poll = client.get(f"/api/v1/jobs/{job_id}")
            assert poll.status_code == 200
            payload = poll.json()
            if payload["status"] == "completed":
                assert payload["result"]["content"] == "done: test task"
                return
            time.sleep(0.01)
        raise AssertionError("Job did not complete in time.")


def test_session_lifecycle_and_task_submission(tmp_path):
    service = StubService()
    service.config.paths.runs_dir = str(tmp_path / "runs")
    app = create_app(service=service)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/sessions",
            json={
                "name": "integration test",
                "profile": "intent_demo",
                "metadata": {"source": "external-tool"},
                "overrides": {"max_turns": 3},
            },
        )
        assert created.status_code == 201
        session = created.json()
        session_id = session["session_id"]
        assert session["profile"] == "intent_demo"
        assert session["metadata"]["source"] == "external-tool"

        updated = client.patch(
            f"/api/v1/sessions/{session_id}",
            json={
                "profile": "default",
                "overrides": {"prompt_overrides": {"general_analyst": "default"}},
                "metadata": {"team": "ops"},
            },
        )
        assert updated.status_code == 200
        assert updated.json()["profile"] == "default"
        assert updated.json()["metadata"]["team"] == "ops"

        response = client.post(
            f"/api/v1/sessions/{session_id}/tasks",
            json={
                "task": "session task",
                "metadata": {"ticket": "INC-1"},
                "overrides": {"max_turns": 2},
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["session_id"] == session_id
        job_id = payload["job_id"]

        for _ in range(20):
            poll = client.get(f"/api/v1/jobs/{job_id}")
            assert poll.status_code == 200
            poll_payload = poll.json()
            if poll_payload["status"] == "completed":
                assert poll_payload["session_id"] == session_id
                assert poll_payload["result"]["content"] == "done: session task"
                break
            time.sleep(0.01)
        else:
            raise AssertionError("Session job did not complete in time.")

        session_jobs = client.get(f"/api/v1/sessions/{session_id}/jobs")
        assert session_jobs.status_code == 200
        assert session_jobs.json()[0]["session_id"] == session_id

        deleted = client.delete(f"/api/v1/sessions/{session_id}")
        assert deleted.status_code == 204

    session_path = tmp_path / "runs" / "sessions" / f"{session_id}.json"
    assert not session_path.exists()


def test_inspector_routes(tmp_path):
    service = StubService()
    service.config.paths.runs_dir = str(tmp_path / "runs")
    run_dir = tmp_path / "runs" / "20260317-demo-run"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "name": "demo-run",
                "run_id": "20260317-demo-run",
                "suite": "bgl_v2",
                "cases_total": 2,
                "metrics": {"pass_rate": 1.0},
                "performance": {"assistant_turns": 4, "total_tokens": 120},
                "resolved_runtime": {
                    "profile": "bgl_v2_eval",
                    "pipeline": "bgl_v2_question_answering",
                    "model": {"model": "gpt-4o-mini"},
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "experiment.json").write_text(
        json.dumps({"name": "demo-run", "runtime": {"profile": "bgl_v2_eval"}}),
        encoding="utf-8",
    )
    (run_dir / "results.jsonl").write_text(
        json.dumps({"case_id": "q1", "score": {"passed": True}}) + "\n",
        encoding="utf-8",
    )

    app = create_app(service=service)
    with TestClient(app) as client:
        html = client.get("/inspector")
        assert html.status_code == 200
        assert "iExplain Inspector" in html.text

        context = client.get("/api/v1/inspector/context")
        assert context.status_code == 200
        assert "intent_demo" in context.json()["profiles"]

        runs = client.get("/api/v1/inspector/runs")
        assert runs.status_code == 200
        assert runs.json()[0]["directory"] == "20260317-demo-run"

        run_detail = client.get("/api/v1/inspector/runs/20260317-demo-run")
        assert run_detail.status_code == 200
        assert run_detail.json()["summary"]["name"] == "demo-run"

        response = client.post("/api/v1/jobs", json={"run": {"task": "inspect me", "profile": "intent_demo"}})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        for _ in range(20):
            poll = client.get(f"/api/v1/jobs/{job_id}")
            if poll.json()["status"] == "completed":
                break
            time.sleep(0.01)
        jobs = client.get("/api/v1/jobs")
        assert jobs.status_code == 200
        assert jobs.json()[0]["profile"] == "intent_demo"
        assert jobs.json()[0]["storage_path"].endswith(f"{job_id}.json")

    persisted_path = tmp_path / "runs" / "jobs" / f"{job_id}.json"
    assert persisted_path.exists()
    session_storage = tmp_path / "runs" / "sessions"
    assert session_storage.exists()

    restarted_service = StubService()
    restarted_service.config.paths.runs_dir = str(tmp_path / "runs")
    restarted_app = create_app(service=restarted_service)
    with TestClient(restarted_app) as client:
        jobs = client.get("/api/v1/jobs")
        assert jobs.status_code == 200
        assert any(job["job_id"] == job_id for job in jobs.json())


def test_openapi_exposes_typed_api_contract():
    app = create_app()
    spec = app.openapi()

    assert spec["info"]["description"].startswith("Async API for submitting iExplain runs")
    assert "/inspector" not in spec["paths"]

    jobs_get = spec["paths"]["/api/v1/jobs"]["get"]
    assert jobs_get["operationId"] == "listJobs"
    assert jobs_get["tags"] == ["jobs"]
    assert jobs_get["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"] == "#/components/schemas/JobSummaryResponse"

    job_get = spec["paths"]["/api/v1/jobs/{job_id}"]["get"]
    assert job_get["operationId"] == "getJob"
    assert job_get["tags"] == ["jobs"]
    assert job_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/JobStateResponse"

    catalog_get = spec["paths"]["/api/v1/catalog"]["get"]
    assert catalog_get["operationId"] == "getCatalog"
    assert catalog_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/CatalogResponse"

    inspector_context_get = spec["paths"]["/api/v1/inspector/context"]["get"]
    assert inspector_context_get["operationId"] == "getInspectorContext"
    assert inspector_context_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/InspectorContextResponse"

    session_jobs_get = spec["paths"]["/api/v1/sessions/{session_id}/jobs"]["get"]
    assert session_jobs_get["operationId"] == "listSessionJobs"
    assert session_jobs_get["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"] == "#/components/schemas/JobSummaryResponse"

    components = spec["components"]["schemas"]
    assert "RunResult" in components
    assert components["RunRequest"]["properties"]["task"]["description"].startswith("Natural-language task")
    assert "filesystem path" in components["ArtifactInput"]["properties"]["source_path"]["description"]
    assert components["SubmitJobRequest"]["example"]["run"]["profile"] == "hdfs_eval"

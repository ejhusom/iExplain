from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.responses import HTMLResponse

from iexplain.api.jobs import JobManager
from iexplain.api.models import (
    CatalogResponse,
    HealthResponse,
    JobAcceptedResponse,
    JobStateResponse,
    JobSummaryResponse,
    InspectorContextResponse,
    InspectorRunDetailResponse,
    InspectorRunSummaryResponse,
    SessionCreateRequest,
    SessionResponse,
    SessionTaskRequest,
    SessionUpdateRequest,
    SubmitJobRequest,
)
from iexplain.api.sessions import SessionManager
from iexplain.config import AppConfig
from iexplain.runtime.service import IExplainService


def create_app(
    config_path: str | Path = "config/app.toml",
    *,
    service: IExplainService | None = None,
) -> FastAPI:
    config = service.config if service else AppConfig.from_file(config_path)
    app_service = service or IExplainService(config)
    app_state: dict[str, Any] = {}
    tags_metadata = [
        {"name": "health", "description": "Lightweight service readiness and discovery endpoints."},
        {"name": "jobs", "description": "Asynchronous run submission and polling endpoints."},
        {"name": "sessions", "description": "Stateful session endpoints for repeated task submission."},
        {"name": "inspector", "description": "Inspector-oriented endpoints for viewing persisted runs and API state."},
    ]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        runs_dir = Path(config.paths.runs_dir)
        jobs_dir = runs_dir / "jobs"
        sessions_dir = runs_dir / "sessions"
        app_state["jobs"] = JobManager(
            app_service,
            max_workers=config.api.max_workers,
            storage_dir=jobs_dir,
        )
        app_state["sessions"] = SessionManager(storage_dir=sessions_dir)
        yield
        app_state["jobs"].shutdown()

    app = FastAPI(
        title="iExplain Next",
        version="0.1.0",
        description=(
            "Async API for submitting iExplain runs, polling results, and reusing session defaults. "
            "The OpenAPI schema is available at `/openapi.json`, with interactive docs at `/docs` and `/redoc`."
        ),
        openapi_tags=tags_metadata,
        lifespan=lifespan,
    )

    @app.get("/inspector", response_class=HTMLResponse, include_in_schema=False)
    async def inspector() -> HTMLResponse:
        return HTMLResponse(_load_inspector_html())

    @app.get(
        "/api/v1/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="Service health",
        description="Return a lightweight health response plus the currently available profiles and skills.",
        operation_id="getHealth",
    )
    async def health() -> HealthResponse:
        catalog = app_service.catalog()
        return HealthResponse(
            profiles=sorted(catalog["config"]["profiles"]),
            skills=sorted(catalog["skills"]),
        )

    @app.get(
        "/api/v1/catalog",
        response_model=CatalogResponse,
        tags=["health"],
        summary="Runtime catalog",
        description="Return the resolved runtime catalog, including profiles, prompts, skills, pipelines, tools, and server configuration.",
        operation_id="getCatalog",
    )
    async def catalog() -> CatalogResponse:
        return app_service.catalog()

    @app.get(
        "/api/v1/jobs",
        response_model=list[JobSummaryResponse],
        tags=["jobs"],
        summary="List jobs",
        description="List submitted jobs in reverse chronological order.",
        operation_id="listJobs",
    )
    async def list_jobs() -> list[JobSummaryResponse]:
        return [job.to_summary() for job in app_state["jobs"].list()]

    @app.post(
        "/api/v1/jobs",
        response_model=JobAcceptedResponse,
        status_code=202,
        tags=["jobs"],
        summary="Submit job",
        description="Submit one asynchronous run request and receive a job identifier for polling.",
        operation_id="submitJob",
    )
    async def submit_job(request: SubmitJobRequest) -> JobAcceptedResponse:
        job = app_state["jobs"].submit(request.run)
        return JobAcceptedResponse(job_id=job.job_id, status=job.status, session_id=job.session_id)

    @app.get(
        "/api/v1/jobs/{job_id}",
        response_model=JobStateResponse,
        tags=["jobs"],
        summary="Get job",
        description="Fetch the current state of a submitted job, including the final result when available.",
        operation_id="getJob",
    )
    async def get_job(job_id: str) -> JobStateResponse:
        job = app_state["jobs"].get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.to_response()

    @app.get(
        "/api/v1/sessions",
        response_model=list[SessionResponse],
        tags=["sessions"],
        summary="List sessions",
        description="List persisted sessions in reverse chronological order.",
        operation_id="listSessions",
    )
    async def list_sessions() -> list[SessionResponse]:
        return [session.to_response() for session in app_state["sessions"].list()]

    @app.post(
        "/api/v1/sessions",
        response_model=SessionResponse,
        status_code=201,
        tags=["sessions"],
        summary="Create session",
        description="Create a session that stores default profile, overrides, and metadata for future task submissions.",
        operation_id="createSession",
    )
    async def create_session(request: SessionCreateRequest) -> SessionResponse:
        session = app_state["sessions"].create(
            name=request.name,
            profile=request.profile,
            overrides=request.overrides,
            metadata=request.metadata,
        )
        return session.to_response()

    @app.get(
        "/api/v1/sessions/{session_id}",
        response_model=SessionResponse,
        tags=["sessions"],
        summary="Get session",
        description="Fetch one session and its currently stored defaults.",
        operation_id="getSession",
    )
    async def get_session(session_id: str) -> SessionResponse:
        session = app_state["sessions"].get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.to_response()

    @app.patch(
        "/api/v1/sessions/{session_id}",
        response_model=SessionResponse,
        tags=["sessions"],
        summary="Update session",
        description="Merge updated defaults into an existing session.",
        operation_id="updateSession",
    )
    async def update_session(session_id: str, request: SessionUpdateRequest) -> SessionResponse:
        session = app_state["sessions"].update(session_id, request)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.to_response()

    @app.delete(
        "/api/v1/sessions/{session_id}",
        status_code=204,
        response_class=Response,
        tags=["sessions"],
        summary="Delete session",
        description="Delete a persisted session record.",
        operation_id="deleteSession",
    )
    async def delete_session(session_id: str) -> Response:
        deleted = app_state["sessions"].delete(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return Response(status_code=204)

    @app.get(
        "/api/v1/sessions/{session_id}/jobs",
        response_model=list[JobSummaryResponse],
        tags=["sessions"],
        summary="List session jobs",
        description="List jobs created from a specific session.",
        operation_id="listSessionJobs",
    )
    async def list_session_jobs(session_id: str) -> list[JobSummaryResponse]:
        if not app_state["sessions"].get(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return [job.to_summary() for job in app_state["jobs"].list() if job.session_id == session_id]

    @app.post(
        "/api/v1/sessions/{session_id}/tasks",
        response_model=JobAcceptedResponse,
        status_code=202,
        tags=["sessions"],
        summary="Submit session task",
        description="Submit one task using a session's stored defaults and receive a job identifier for polling.",
        operation_id="submitSessionTask",
    )
    async def submit_session_task(session_id: str, request: SessionTaskRequest) -> JobAcceptedResponse:
        run_request = app_state["sessions"].build_run_request(session_id, request)
        if run_request is None:
            raise HTTPException(status_code=404, detail="Session not found")
        job = app_state["jobs"].submit(run_request, session_id=session_id)
        return JobAcceptedResponse(job_id=job.job_id, status=job.status, session_id=job.session_id)

    @app.get(
        "/api/v1/inspector/context",
        response_model=InspectorContextResponse,
        tags=["inspector"],
        summary="Inspector context",
        description="Return inspector-oriented context such as available profiles and storage directories.",
        operation_id="getInspectorContext",
    )
    async def inspector_context() -> InspectorContextResponse:
        catalog = app_service.catalog()
        return {
            "profiles": sorted(catalog["config"]["profiles"]),
            "runs_dir": str(Path(app_service.config.paths.runs_dir)),
            "jobs_dir": str(Path(app_service.config.paths.runs_dir) / "jobs"),
            "sessions_dir": str(Path(app_service.config.paths.runs_dir) / "sessions"),
        }

    @app.get(
        "/api/v1/inspector/runs",
        response_model=list[InspectorRunSummaryResponse],
        tags=["inspector"],
        summary="List runs",
        description="List persisted evaluation runs that have a summary.json file.",
        operation_id="listInspectorRuns",
    )
    async def list_runs() -> list[InspectorRunSummaryResponse]:
        return _list_run_summaries(Path(app_service.config.paths.runs_dir))

    @app.get(
        "/api/v1/inspector/runs/{run_id}",
        response_model=InspectorRunDetailResponse,
        tags=["inspector"],
        summary="Get run",
        description="Return the stored summary, experiment payload, and a preview of results for one evaluation run.",
        operation_id="getInspectorRun",
    )
    async def get_run(run_id: str) -> InspectorRunDetailResponse:
        run_dir = _resolve_run_dir(Path(app_service.config.paths.runs_dir), run_id)
        if not run_dir.exists():
            raise HTTPException(status_code=404, detail="Run not found")
        return _load_run_detail(run_dir)

    return app


def _load_inspector_html() -> str:
    template_path = Path(__file__).with_name("inspector.html")
    return template_path.read_text(encoding="utf-8")


def _list_run_summaries(runs_dir: Path) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []

    summaries: list[dict[str, Any]] = []
    for run_dir in sorted((path for path in runs_dir.iterdir() if path.is_dir()), reverse=True):
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        resolved_runtime = summary.get("resolved_runtime", {})
        metrics = summary.get("metrics", {})
        performance = summary.get("performance", {})
        summaries.append(
            {
                "run_id": summary.get("run_id", run_dir.name),
                "directory": run_dir.name,
                "path": str(run_dir),
                "name": summary.get("name", run_dir.name),
                "suite": summary.get("suite"),
                "profile": resolved_runtime.get("profile"),
                "pipeline": resolved_runtime.get("pipeline"),
                "model": (resolved_runtime.get("model") or {}).get("model"),
                "cases_total": summary.get("cases_total"),
                "score": metrics.get("accuracy", metrics.get("pass_rate", metrics.get("cases_passed"))),
                "assistant_turns": performance.get("assistant_turns"),
                "total_tokens": performance.get("total_tokens"),
                "matrix_context": summary.get("matrix_context"),
                "updated_at": summary_path.stat().st_mtime,
            }
        )
    return sorted(summaries, key=lambda item: item["updated_at"], reverse=True)


def _resolve_run_dir(runs_dir: Path, run_id: str) -> Path:
    candidate = (runs_dir / run_id).resolve()
    try:
        candidate.relative_to(runs_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid run id") from exc
    return candidate


def _load_run_detail(run_dir: Path) -> dict[str, Any]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    experiment_path = run_dir / "experiment.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8")) if experiment_path.exists() else {}

    results_preview: list[dict[str, Any]] = []
    results_path = run_dir / "results.jsonl"
    if results_path.exists():
        with results_path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= 10:
                    break
                line = line.strip()
                if not line:
                    continue
                results_preview.append(json.loads(line))

    return {
        "summary": summary,
        "experiment": experiment,
        "results_preview": results_preview,
    }

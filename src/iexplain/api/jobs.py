from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from iexplain.api.models import JobStateResponse, JobStatus
from iexplain.runtime.models import RunRequest, RunResult
from iexplain.runtime.service import IExplainService


@dataclass
class JobRecord:
    job_id: str
    run_request: RunRequest
    session_id: str | None = None
    status: JobStatus = JobStatus.pending
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: RunResult | None = None
    storage_path: str | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "task": self.run_request.task,
            "profile": self.run_request.profile,
            "error": self.error,
            "has_result": self.result is not None,
            "storage_path": self.storage_path,
        }

    def to_response(self) -> JobStateResponse:
        return JobStateResponse(
            job_id=self.job_id,
            status=self.status,
            session_id=self.session_id,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error=self.error,
            result=self.result,
        )

    def to_payload(self) -> dict[str, object]:
        response = self.to_response().model_dump(mode="json")
        response["run_request"] = self.run_request.model_dump(mode="json")
        response["storage_path"] = self.storage_path
        return response

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "JobRecord":
        return cls(
            job_id=str(payload["job_id"]),
            run_request=RunRequest.model_validate(payload["run_request"]),
            session_id=str(payload["session_id"]) if payload.get("session_id") is not None else None,
            status=JobStatus(str(payload["status"])),
            created_at=_parse_datetime(payload.get("created_at")),
            started_at=_parse_datetime(payload.get("started_at")),
            completed_at=_parse_datetime(payload.get("completed_at")),
            error=str(payload["error"]) if payload.get("error") is not None else None,
            result=RunResult.model_validate(payload["result"]) if payload.get("result") is not None else None,
            storage_path=str(payload["storage_path"]) if payload.get("storage_path") is not None else None,
        )


class JobManager:
    def __init__(self, service: IExplainService, max_workers: int = 4, storage_dir: str | Path | None = None):
        self.service = service
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: dict[str, JobRecord] = {}
        self.lock = Lock()
        self.storage_dir = Path(storage_dir) if storage_dir is not None else None
        if self.storage_dir is not None:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_existing_jobs()

    def submit(self, run_request: RunRequest, *, session_id: str | None = None) -> JobRecord:
        job = JobRecord(
            job_id=f"job_{uuid.uuid4().hex[:12]}",
            run_request=run_request,
            session_id=session_id,
        )
        if self.storage_dir is not None:
            job.storage_path = str(self._job_path(job.job_id))
        with self.lock:
            self.jobs[job.job_id] = job
            self._persist_job(job)
        self.executor.submit(self._run_job, job.job_id)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self.lock:
            return self.jobs.get(job_id)

    def list(self) -> list[JobRecord]:
        with self.lock:
            return sorted(
                self.jobs.values(),
                key=lambda job: job.created_at,
                reverse=True,
            )

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _run_job(self, job_id: str) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.status = JobStatus.running
            job.started_at = datetime.now(timezone.utc)
            self._persist_job(job)
        try:
            result = self.service.run(job.run_request)
            with self.lock:
                job.status = JobStatus.completed
                job.result = result
                job.completed_at = datetime.now(timezone.utc)
                self._persist_job(job)
        except Exception as exc:
            with self.lock:
                job.status = JobStatus.failed
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                self._persist_job(job)

    def _job_path(self, job_id: str) -> Path:
        assert self.storage_dir is not None
        return self.storage_dir / f"{job_id}.json"

    def _persist_job(self, job: JobRecord) -> None:
        if self.storage_dir is None:
            return
        target = self._job_path(job.job_id)
        job.storage_path = str(target)
        temp_target = target.with_suffix(".json.tmp")
        temp_target.write_text(json.dumps(job.to_payload(), indent=2), encoding="utf-8")
        temp_target.replace(target)

    def _load_existing_jobs(self) -> None:
        assert self.storage_dir is not None
        for path in sorted(self.storage_dir.glob("job_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            job = JobRecord.from_payload(payload)
            job.storage_path = str(path)
            self.jobs[job.job_id] = job


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))

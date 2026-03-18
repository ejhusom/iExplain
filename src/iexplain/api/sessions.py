from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from iexplain.api.models import SessionResponse, SessionTaskRequest, SessionUpdateRequest
from iexplain.runtime.models import RunOverrides, RunRequest


@dataclass
class SessionRecord:
    session_id: str
    profile: str
    overrides: RunOverrides = field(default_factory=RunOverrides)
    metadata: dict[str, object] = field(default_factory=dict)
    name: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    storage_path: str | None = None

    def to_response(self) -> SessionResponse:
        return SessionResponse(
            session_id=self.session_id,
            name=self.name,
            profile=self.profile,
            overrides=self.overrides,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
            storage_path=self.storage_path,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "profile": self.profile,
            "overrides": self.overrides.model_dump(mode="json", exclude_none=True),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "storage_path": self.storage_path,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "SessionRecord":
        return cls(
            session_id=str(payload["session_id"]),
            name=str(payload["name"]) if payload.get("name") is not None else None,
            profile=str(payload["profile"]),
            overrides=RunOverrides.model_validate(payload.get("overrides") or {}),
            metadata=dict(payload.get("metadata") or {}),
            created_at=_parse_datetime(payload.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_parse_datetime(payload.get("updated_at")) or datetime.now(timezone.utc),
            storage_path=str(payload["storage_path"]) if payload.get("storage_path") is not None else None,
        )


class SessionManager:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self.sessions: dict[str, SessionRecord] = {}
        self.lock = Lock()
        self.storage_dir = Path(storage_dir) if storage_dir is not None else None
        if self.storage_dir is not None:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_existing_sessions()

    def create(
        self,
        *,
        profile: str,
        overrides: RunOverrides | None = None,
        metadata: dict[str, object] | None = None,
        name: str | None = None,
    ) -> SessionRecord:
        session = SessionRecord(
            session_id=f"session_{uuid.uuid4().hex[:12]}",
            name=name,
            profile=profile,
            overrides=overrides or RunOverrides(),
            metadata=dict(metadata or {}),
        )
        if self.storage_dir is not None:
            session.storage_path = str(self._session_path(session.session_id))
        with self.lock:
            self.sessions[session.session_id] = session
            self._persist_session(session)
        return session

    def get(self, session_id: str) -> SessionRecord | None:
        with self.lock:
            return self.sessions.get(session_id)

    def list(self) -> list[SessionRecord]:
        with self.lock:
            return sorted(self.sessions.values(), key=lambda item: item.created_at, reverse=True)

    def update(self, session_id: str, update: SessionUpdateRequest) -> SessionRecord | None:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return None
            if update.name is not None:
                session.name = update.name
            if update.profile is not None:
                session.profile = update.profile
            if update.overrides is not None:
                session.overrides = _merge_overrides(session.overrides, update.overrides)
            if update.metadata is not None:
                session.metadata = {**session.metadata, **update.metadata}
            session.updated_at = datetime.now(timezone.utc)
            self._persist_session(session)
            return session

    def delete(self, session_id: str) -> bool:
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session is None:
                return False
            if self.storage_dir is not None:
                path = self._session_path(session_id)
                if path.exists():
                    path.unlink()
            return True

    def build_run_request(self, session_id: str, task_request: SessionTaskRequest) -> RunRequest | None:
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                return None
            metadata = {
                **session.metadata,
                **task_request.metadata,
                "session_id": session.session_id,
            }
            return RunRequest(
                task=task_request.task,
                profile=task_request.profile or session.profile,
                artifacts=task_request.artifacts,
                overrides=_merge_overrides(session.overrides, task_request.overrides),
                metadata=metadata,
            )

    def _session_path(self, session_id: str) -> Path:
        assert self.storage_dir is not None
        return self.storage_dir / f"{session_id}.json"

    def _persist_session(self, session: SessionRecord) -> None:
        if self.storage_dir is None:
            return
        target = self._session_path(session.session_id)
        session.storage_path = str(target)
        temp_target = target.with_suffix(".json.tmp")
        temp_target.write_text(json.dumps(session.to_payload(), indent=2), encoding="utf-8")
        temp_target.replace(target)

    def _load_existing_sessions(self) -> None:
        assert self.storage_dir is not None
        for path in sorted(self.storage_dir.glob("session_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            session = SessionRecord.from_payload(payload)
            session.storage_path = str(path)
            self.sessions[session.session_id] = session


def _merge_overrides(base: RunOverrides, override: RunOverrides) -> RunOverrides:
    base_payload = base.model_dump(exclude_none=True)
    override_payload = override.model_dump(exclude_none=True)
    merged = dict(base_payload)
    merged_prompt_overrides = dict(base_payload.get("prompt_overrides") or {})
    merged_prompt_overrides.update(override_payload.get("prompt_overrides") or {})
    for key, value in override_payload.items():
        if key == "prompt_overrides":
            continue
        merged[key] = value
    if merged_prompt_overrides:
        merged["prompt_overrides"] = merged_prompt_overrides
    elif "prompt_overrides" in merged:
        merged.pop("prompt_overrides")
    return RunOverrides.model_validate(merged)


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))

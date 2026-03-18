from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from iexplain.runtime.models import ArtifactInput, RunResult


@dataclass
class EvalCase:
    case_id: str
    task: str
    artifacts: list[ArtifactInput]
    metadata: dict[str, Any] = field(default_factory=dict)


class SuiteAdapter(ABC):
    suite_name: str

    @abstractmethod
    def load_cases(self, settings: dict[str, Any]) -> list[EvalCase]:
        raise NotImplementedError

    @abstractmethod
    def score_case(self, case: EvalCase, result: RunResult) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def summarize(self, scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

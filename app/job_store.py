from __future__ import annotations

from threading import Lock
from typing import Any


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def create(self, job_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._jobs[job_id] = data
            return dict(self._jobs[job_id])

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def update(self, job_id: str, **updates: Any) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.update(updates)
            return dict(job)


job_store = JobStore()

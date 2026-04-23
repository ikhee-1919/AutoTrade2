import json
from pathlib import Path
from threading import Lock
from typing import Any


class BacktestJobRepository:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists():
            self._file_path.write_text("[]", encoding="utf-8")
        self._lock = Lock()

    def create(self, job_data: dict[str, Any]) -> None:
        with self._lock:
            jobs = self._load()
            jobs.insert(0, job_data)
            self._save(jobs[:200])

    def update(self, job_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            jobs = self._load()
            for idx, job in enumerate(jobs):
                if job.get("job_id") == job_id:
                    updated = {**job, **patch}
                    jobs[idx] = updated
                    self._save(jobs)
                    return updated
        return None

    def get_by_id(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            jobs = self._load()
            for job in jobs:
                if job.get("job_id") == job_id:
                    return job
        return None

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            jobs = self._load()
            return jobs[:limit]

    def list_filtered(
        self,
        limit: int = 20,
        status: str | None = None,
        job_type: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            jobs = self._load()
            if status:
                jobs = [job for job in jobs if job.get("status") == status]
            if job_type:
                jobs = [job for job in jobs if job.get("job_type") == job_type]
            return jobs[:limit]

    def count_by_status(self, statuses: list[str], job_type: str | None = None) -> int:
        status_set = set(statuses)
        with self._lock:
            jobs = self._load()
            return sum(
                1
                for job in jobs
                if job.get("status") in status_set
                and (job_type is None or job.get("job_type") == job_type)
            )

    def get_latest_active_by_request_hash(
        self,
        request_hash: str,
        job_type: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            jobs = self._load()
            for job in jobs:
                if (
                    job.get("request_hash") == request_hash
                    and job.get("status") in {"queued", "running"}
                    and (job_type is None or job.get("job_type") == job_type)
                ):
                    return job
        return None

    def get_next_queued(self, job_type: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            jobs = self._load()
            for job in reversed(jobs):
                if job.get("status") == "queued" and (
                    job_type is None or job.get("job_type") == job_type
                ):
                    return job
        return None

    def _load(self) -> list[dict[str, Any]]:
        raw = self._file_path.read_text(encoding="utf-8")
        return json.loads(raw)

    def _save(self, payload: list[dict[str, Any]]) -> None:
        self._file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

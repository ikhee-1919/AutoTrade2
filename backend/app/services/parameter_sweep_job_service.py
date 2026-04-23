from datetime import datetime
import hashlib
import json
from threading import Lock, Thread
import traceback
from uuid import uuid4

from app.repositories.backtest_job_repository import BacktestJobRepository
from app.schemas.sweep import SweepRunRequest
from app.services.parameter_sweep_service import ParameterSweepService


class ParameterSweepJobService:
    def __init__(
        self,
        sweep_service: ParameterSweepService,
        job_repo: BacktestJobRepository,
        max_concurrent_jobs: int = 1,
    ) -> None:
        self._sweep_service = sweep_service
        self._job_repo = job_repo
        self._max_concurrent_jobs = max_concurrent_jobs
        self._dispatch_lock = Lock()

    def create_job(self, request: SweepRunRequest) -> dict:
        payload = request.model_dump(mode="json")
        request_hash = self._hash_request(payload)
        duplicate = self._job_repo.get_latest_active_by_request_hash(
            request_hash,
            job_type="parameter_sweep",
        )
        if duplicate:
            return {**duplicate, "duplicate_of_job_id": duplicate["job_id"]}

        now = datetime.utcnow().isoformat()
        job = {
            "job_id": uuid4().hex,
            "job_type": "parameter_sweep",
            "status": "queued",
            "progress": 0.0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "related_sweep_run_id": None,
            "total_combinations": None,
            "completed_combinations": 0,
            "failed_combinations": 0,
            "error_summary": None,
            "error_detail": None,
            "retry_count": 0,
            "parent_job_id": None,
            "request_hash": request_hash,
            "duplicate_of_job_id": None,
            "cancel_requested": False,
            "request": payload,
        }
        self._job_repo.create(job)
        self._dispatch_jobs()
        return job

    def get_job(self, job_id: str) -> dict:
        job = self._job_repo.get_by_id(job_id)
        if job is None or job.get("job_type") != "parameter_sweep":
            raise ValueError(f"sweep job not found: {job_id}")
        return job

    def list_jobs(self, limit: int = 20, status: str | None = None) -> list[dict]:
        jobs = self._job_repo.list_filtered(limit=200, status=status)
        filtered = [job for job in jobs if job.get("job_type") == "parameter_sweep"]
        return filtered[:limit]

    def cancel_job(self, job_id: str) -> dict:
        job = self.get_job(job_id)
        if job["status"] in {"completed", "failed", "cancelled"}:
            raise ValueError(f"cannot cancel job in status={job['status']}")
        now = datetime.utcnow().isoformat()
        duration = self._duration_seconds(job.get("started_at"), now)
        updated = self._job_repo.update(
            job_id,
            {
                "status": "cancelled",
                "finished_at": now,
                "duration_seconds": duration,
                "cancel_requested": True,
                "error_summary": "cancelled by user",
            },
        )
        if updated is None:
            raise ValueError(f"sweep job not found: {job_id}")
        self._dispatch_jobs()
        return updated

    def retry_job(self, job_id: str) -> dict:
        old = self.get_job(job_id)
        if old["status"] != "failed":
            raise ValueError("retry is allowed only for failed jobs")
        request = old["request"]
        request_hash = self._hash_request(request)
        duplicate = self._job_repo.get_latest_active_by_request_hash(
            request_hash,
            job_type="parameter_sweep",
        )
        if duplicate:
            return {**duplicate, "duplicate_of_job_id": duplicate["job_id"]}
        now = datetime.utcnow().isoformat()
        job = {
            "job_id": uuid4().hex,
            "job_type": "parameter_sweep",
            "status": "queued",
            "progress": 0.0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "related_sweep_run_id": None,
            "total_combinations": None,
            "completed_combinations": 0,
            "failed_combinations": 0,
            "error_summary": None,
            "error_detail": None,
            "retry_count": int(old.get("retry_count", 0)) + 1,
            "parent_job_id": old["job_id"],
            "request_hash": request_hash,
            "duplicate_of_job_id": None,
            "cancel_requested": False,
            "request": request,
        }
        self._job_repo.create(job)
        self._dispatch_jobs()
        return job

    def _dispatch_jobs(self) -> None:
        with self._dispatch_lock:
            while self._active_running() < self._max_concurrent_jobs:
                next_job = self._next_queued()
                if next_job is None:
                    return
                self._job_repo.update(
                    next_job["job_id"],
                    {"status": "running", "started_at": datetime.utcnow().isoformat(), "progress": 2.0},
                )
                worker = Thread(target=self._run_job, args=(next_job["job_id"],), daemon=True)
                worker.start()

    def _run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)

        def set_progress(done: int, total: int) -> None:
            current = self._job_repo.get_by_id(job_id)
            if not current or current.get("status") != "running":
                return
            pct = 5.0 if total <= 0 else max(5.0, min(100.0, (done / total) * 100))
            self._job_repo.update(
                job_id,
                {
                    "progress": pct,
                    "total_combinations": total,
                    "completed_combinations": done,
                },
            )

        try:
            request = SweepRunRequest(**job["request"])
            result = self._sweep_service.run(request, progress_callback=set_progress)
            now = datetime.utcnow().isoformat()
            self._job_repo.update(
                job_id,
                {
                    "status": "completed",
                    "progress": 100.0,
                    "finished_at": now,
                    "duration_seconds": self._duration_seconds(job.get("started_at"), now),
                    "related_sweep_run_id": result["sweep_run_id"],
                    "total_combinations": result.get("total_combinations", 0),
                    "completed_combinations": result.get("completed_combinations", 0),
                    "failed_combinations": result.get("failed_combinations", 0),
                },
            )
        except Exception as exc:  # noqa: BLE001
            now = datetime.utcnow().isoformat()
            tb = "\n".join(traceback.format_exception_only(type(exc), exc)).strip()
            self._job_repo.update(
                job_id,
                {
                    "status": "failed",
                    "finished_at": now,
                    "duration_seconds": self._duration_seconds(job.get("started_at"), now),
                    "error_summary": str(exc)[:300],
                    "error_detail": tb[:1000],
                },
            )
        finally:
            self._dispatch_jobs()

    def _active_running(self) -> int:
        jobs = self._job_repo.list_filtered(limit=200, status="running")
        return sum(1 for job in jobs if job.get("job_type") == "parameter_sweep")

    def _next_queued(self) -> dict | None:
        jobs = self._job_repo.list_filtered(limit=200, status="queued")
        for job in reversed(jobs):
            if job.get("job_type") == "parameter_sweep":
                return job
        return None

    def _hash_request(self, payload: dict) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _duration_seconds(self, started_at: str | None, finished_at: str) -> float | None:
        if not started_at:
            return None
        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(finished_at)
            return round((end - start).total_seconds(), 6)
        except Exception:  # noqa: BLE001
            return None

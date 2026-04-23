from datetime import datetime
import hashlib
import json
from threading import Lock, Thread
import traceback
from uuid import uuid4

from app.backtest.engine import BacktestCancelledError
from app.repositories.backtest_job_repository import BacktestJobRepository
from app.schemas.backtest import BacktestRunRequest
from app.services.backtest_service import BacktestService


class BacktestJobService:
    def __init__(
        self,
        backtest_service: BacktestService,
        job_repo: BacktestJobRepository,
        max_concurrent_jobs: int = 2,
    ) -> None:
        self._backtest_service = backtest_service
        self._job_repo = job_repo
        self._max_concurrent_jobs = max_concurrent_jobs
        self._dispatch_lock = Lock()

    def create_job(self, request: BacktestRunRequest) -> dict:
        request_payload = request.model_dump(mode="json")
        request_hash = self._hash_request(request_payload)

        active_duplicate = self._job_repo.get_latest_active_by_request_hash(
            request_hash,
            job_type="backtest",
        )
        if active_duplicate:
            return {
                **active_duplicate,
                "duplicate_of_job_id": active_duplicate["job_id"],
            }

        now = datetime.utcnow().isoformat()
        job_id = uuid4().hex
        job = {
            "job_id": job_id,
            "job_type": "backtest",
            "status": "queued",
            "progress": 0.0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "related_run_id": None,
            "error_summary": None,
            "error_detail": None,
            "retry_count": 0,
            "parent_job_id": None,
            "request_hash": request_hash,
            "duplicate_of_job_id": None,
            "cancel_requested": False,
            "request": request_payload,
        }
        self._job_repo.create(job)
        self._dispatch_jobs()
        return job

    def get_job(self, job_id: str) -> dict:
        job = self._job_repo.get_by_id(job_id)
        if job is None:
            raise ValueError(f"job_id not found: {job_id}")
        return job

    def list_jobs(
        self,
        limit: int = 20,
        status: str | None = None,
        job_type: str | None = None,
    ) -> list[dict]:
        return self._job_repo.list_filtered(limit=limit, status=status, job_type=job_type)

    def cancel_job(self, job_id: str) -> dict:
        job = self.get_job(job_id)
        if job["status"] in {"completed", "failed", "cancelled"}:
            raise ValueError(f"cannot cancel job in status={job['status']}")

        now = datetime.utcnow().isoformat()
        started_at = job.get("started_at")
        duration = self._duration_seconds(started_at, now) if started_at else None
        updated = self._job_repo.update(
            job_id,
            {
                "status": "cancelled",
                "progress": job.get("progress", 0.0),
                "cancel_requested": True,
                "finished_at": now,
                "duration_seconds": duration,
                "error_summary": "cancelled by user",
            },
        )
        if updated is None:
            raise ValueError(f"job_id not found: {job_id}")
        self._dispatch_jobs()
        return updated

    def retry_job(self, job_id: str) -> dict:
        old = self.get_job(job_id)
        if old["status"] != "failed":
            raise ValueError("retry is allowed only for failed jobs")

        payload = old["request"]
        request_hash = self._hash_request(payload)

        active_duplicate = self._job_repo.get_latest_active_by_request_hash(
            request_hash,
            job_type="backtest",
        )
        if active_duplicate:
            return {
                **active_duplicate,
                "duplicate_of_job_id": active_duplicate["job_id"],
            }

        now = datetime.utcnow().isoformat()
        new_job = {
            "job_id": uuid4().hex,
            "job_type": "backtest",
            "status": "queued",
            "progress": 0.0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "related_run_id": None,
            "error_summary": None,
            "error_detail": None,
            "retry_count": int(old.get("retry_count", 0)) + 1,
            "parent_job_id": old["job_id"],
            "request_hash": request_hash,
            "duplicate_of_job_id": None,
            "cancel_requested": False,
            "request": payload,
        }
        self._job_repo.create(new_job)
        self._dispatch_jobs()
        return new_job

    def _dispatch_jobs(self) -> None:
        with self._dispatch_lock:
            while (
                self._job_repo.count_by_status(["running"], job_type="backtest")
                < self._max_concurrent_jobs
            ):
                next_job = self._job_repo.get_next_queued(job_type="backtest")
                if next_job is None:
                    return

                job_id = next_job["job_id"]
                started_at = datetime.utcnow().isoformat()
                self._job_repo.update(
                    job_id,
                    {
                        "status": "running",
                        "started_at": started_at,
                        "progress": 2.0,
                    },
                )
                worker = Thread(target=self._run_job, args=(job_id,), daemon=True)
                worker.start()

    def _run_job(self, job_id: str) -> None:
        job = self._job_repo.get_by_id(job_id)
        if not job:
            return
        request_payload = job["request"]

        def set_progress(value: float) -> None:
            current = self._job_repo.get_by_id(job_id)
            if not current or current.get("status") != "running":
                return
            safe = max(current.get("progress", 0.0), min(float(value), 100.0))
            self._job_repo.update(job_id, {"progress": safe})

        def should_cancel() -> bool:
            current = self._job_repo.get_by_id(job_id)
            if not current:
                return True
            return current.get("status") == "cancelled" or bool(current.get("cancel_requested"))

        try:
            run_result = self._backtest_service.run(
                BacktestRunRequest(**request_payload),
                progress_callback=set_progress,
                should_cancel=should_cancel,
            )
            latest = self._job_repo.get_by_id(job_id)
            if latest and latest.get("status") == "cancelled":
                return

            now = datetime.utcnow().isoformat()
            duration = self._duration_seconds(job.get("started_at"), now)
            self._job_repo.update(
                job_id,
                {
                    "status": "completed",
                    "progress": 100.0,
                    "finished_at": now,
                    "duration_seconds": duration,
                    "related_run_id": run_result["run_id"],
                },
            )
        except BacktestCancelledError:
            now = datetime.utcnow().isoformat()
            duration = self._duration_seconds(job.get("started_at"), now)
            self._job_repo.update(
                job_id,
                {
                    "status": "cancelled",
                    "finished_at": now,
                    "duration_seconds": duration,
                    "error_summary": "cancelled by user",
                },
            )
        except Exception as exc:  # noqa: BLE001 - persist failure for operator visibility
            now = datetime.utcnow().isoformat()
            duration = self._duration_seconds(job.get("started_at"), now)
            tb = "\n".join(traceback.format_exception_only(type(exc), exc)).strip()
            self._job_repo.update(
                job_id,
                {
                    "status": "failed",
                    "finished_at": now,
                    "duration_seconds": duration,
                    "error_summary": str(exc)[:300],
                    "error_detail": tb[:1000],
                },
            )
        finally:
            self._dispatch_jobs()

    def _hash_request(self, payload: dict) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _duration_seconds(self, started_at: str | None, finished_at: str) -> float | None:
        if not started_at:
            return None
        try:
            started = datetime.fromisoformat(started_at)
            finished = datetime.fromisoformat(finished_at)
            return round((finished - started).total_seconds(), 6)
        except Exception:  # noqa: BLE001 - metadata fallback only
            return None

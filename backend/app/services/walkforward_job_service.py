from datetime import datetime
import hashlib
import json
from threading import Lock, Thread
import traceback
from uuid import uuid4

from app.repositories.backtest_job_repository import BacktestJobRepository
from app.schemas.walkforward import WalkforwardRunRequest
from app.services.walkforward_service import WalkforwardService


class WalkforwardJobService:
    def __init__(
        self,
        walkforward_service: WalkforwardService,
        job_repo: BacktestJobRepository,
        max_concurrent_jobs: int = 2,
    ) -> None:
        self._walkforward_service = walkforward_service
        self._job_repo = job_repo
        self._max_concurrent_jobs = max_concurrent_jobs
        self._dispatch_lock = Lock()

    def create_job(self, request: WalkforwardRunRequest) -> dict:
        request_payload = request.model_dump(mode="json")
        request_hash = self._hash_request(request_payload)
        duplicate = self._job_repo.get_latest_active_by_request_hash(
            request_hash,
            job_type="walkforward",
        )
        if duplicate:
            return {**duplicate, "duplicate_of_job_id": duplicate["job_id"]}

        now = datetime.utcnow().isoformat()
        job = {
            "job_id": uuid4().hex,
            "job_type": "walkforward",
            "status": "queued",
            "progress": 0.0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "related_walkforward_run_id": None,
            "error_summary": None,
            "error_detail": None,
            "retry_count": 0,
            "parent_job_id": None,
            "request_hash": request_hash,
            "duplicate_of_job_id": None,
            "cancel_requested": False,
            "segment_total": None,
            "segment_completed": 0,
            "failed_segment_index": None,
            "request": request_payload,
        }
        self._job_repo.create(job)
        self._dispatch_jobs()
        return job

    def get_job(self, job_id: str) -> dict:
        job = self._job_repo.get_by_id(job_id)
        if job is None or job.get("job_type") != "walkforward":
            raise ValueError(f"walkforward job_id not found: {job_id}")
        return job

    def list_jobs(self, limit: int = 20, status: str | None = None) -> list[dict]:
        return self._job_repo.list_filtered(limit=limit, status=status, job_type="walkforward")

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
                "cancel_requested": True,
                "finished_at": now,
                "duration_seconds": duration,
                "error_summary": "cancelled by user",
            },
        )
        if updated is None:
            raise ValueError(f"walkforward job_id not found: {job_id}")
        self._dispatch_jobs()
        return updated

    def retry_job(self, job_id: str) -> dict:
        old = self.get_job(job_id)
        if old["status"] != "failed":
            raise ValueError("retry is allowed only for failed jobs")
        payload = old["request"]
        request_hash = self._hash_request(payload)

        duplicate = self._job_repo.get_latest_active_by_request_hash(
            request_hash,
            job_type="walkforward",
        )
        if duplicate:
            return {**duplicate, "duplicate_of_job_id": duplicate["job_id"]}

        now = datetime.utcnow().isoformat()
        new_job = {
            "job_id": uuid4().hex,
            "job_type": "walkforward",
            "status": "queued",
            "progress": 0.0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "related_walkforward_run_id": None,
            "error_summary": None,
            "error_detail": None,
            "retry_count": int(old.get("retry_count", 0)) + 1,
            "parent_job_id": old["job_id"],
            "request_hash": request_hash,
            "duplicate_of_job_id": None,
            "cancel_requested": False,
            "segment_total": None,
            "segment_completed": 0,
            "failed_segment_index": None,
            "request": payload,
        }
        self._job_repo.create(new_job)
        self._dispatch_jobs()
        return new_job

    def _dispatch_jobs(self) -> None:
        with self._dispatch_lock:
            while (
                self._job_repo.count_by_status(["running"], job_type="walkforward")
                < self._max_concurrent_jobs
            ):
                next_job = self._job_repo.get_next_queued(job_type="walkforward")
                if next_job is None:
                    return
                started_at = datetime.utcnow().isoformat()
                self._job_repo.update(
                    next_job["job_id"],
                    {"status": "running", "started_at": started_at, "progress": 2.0},
                )
                worker = Thread(target=self._run_job, args=(next_job["job_id"],), daemon=True)
                worker.start()

    def _run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        request_payload = job["request"]

        def progress(completed: int, total: int, segment_index: int | None) -> None:
            current = self._job_repo.get_by_id(job_id)
            if not current or current.get("status") != "running":
                return
            pct = 5.0 if total <= 0 else max(5.0, min(100.0, (completed / total) * 100))
            self._job_repo.update(
                job_id,
                {
                    "progress": pct,
                    "segment_total": total,
                    "segment_completed": completed,
                    "failed_segment_index": None,
                },
            )

        def should_cancel() -> bool:
            current = self._job_repo.get_by_id(job_id)
            if not current:
                return True
            return current.get("status") == "cancelled" or bool(current.get("cancel_requested"))

        try:
            result = self._walkforward_service.run(
                WalkforwardRunRequest(**request_payload),
                progress_callback=progress,
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
                    "related_walkforward_run_id": result["walkforward_run_id"],
                },
            )
        except ValueError as exc:
            now = datetime.utcnow().isoformat()
            duration = self._duration_seconds(job.get("started_at"), now)
            if "cancelled" in str(exc).lower():
                self._job_repo.update(
                    job_id,
                    {
                        "status": "cancelled",
                        "finished_at": now,
                        "duration_seconds": duration,
                        "error_summary": "cancelled by user",
                    },
                )
            else:
                latest = self._job_repo.get_by_id(job_id) or {}
                tb = "\n".join(traceback.format_exception_only(type(exc), exc)).strip()
                self._job_repo.update(
                    job_id,
                    {
                        "status": "failed",
                        "finished_at": now,
                        "duration_seconds": duration,
                        "error_summary": str(exc)[:300],
                        "error_detail": tb[:1000],
                        "failed_segment_index": latest.get("segment_completed"),
                    },
                )
        except Exception as exc:  # noqa: BLE001
            now = datetime.utcnow().isoformat()
            duration = self._duration_seconds(job.get("started_at"), now)
            latest = self._job_repo.get_by_id(job_id) or {}
            tb = "\n".join(traceback.format_exception_only(type(exc), exc)).strip()
            self._job_repo.update(
                job_id,
                {
                    "status": "failed",
                    "finished_at": now,
                    "duration_seconds": duration,
                    "error_summary": str(exc)[:300],
                    "error_detail": tb[:1000],
                    "failed_segment_index": latest.get("segment_completed"),
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
        except Exception:  # noqa: BLE001
            return None

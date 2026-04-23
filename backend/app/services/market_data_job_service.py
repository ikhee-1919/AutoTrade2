from datetime import datetime
import hashlib
import json
from threading import Lock, Thread
import traceback
from uuid import uuid4

from app.repositories.backtest_job_repository import BacktestJobRepository
from app.schemas.market_data import (
    MarketDataBatchRequest,
    MarketDataCollectRequest,
    MarketDataUpdateRequest,
)
from app.services.market_data_service import MarketDataService


class MarketDataJobService:
    def __init__(
        self,
        market_data_service: MarketDataService,
        job_repo: BacktestJobRepository,
        max_concurrent_jobs: int = 2,
    ) -> None:
        self._market_data_service = market_data_service
        self._job_repo = job_repo
        self._max_concurrent_jobs = max_concurrent_jobs
        self._dispatch_lock = Lock()

    def create_collect_job(self, request: MarketDataCollectRequest) -> dict:
        payload = {"op": "collect", "request": request.model_dump(mode="json")}
        return self._create_job(payload, job_type="market_data_collect")

    def create_update_job(self, request: MarketDataUpdateRequest) -> dict:
        payload = {"op": "update", "request": request.model_dump(mode="json")}
        return self._create_job(payload, job_type="market_data_update")

    def create_validate_job(self, dataset_id: str) -> dict:
        payload = {"op": "validate", "dataset_id": dataset_id}
        return self._create_job(payload, job_type="market_data_validate")

    def create_collect_batch_job(self, request: MarketDataBatchRequest) -> dict:
        payload = {"op": "collect_batch", "request": request.model_dump(mode="json")}
        return self._create_job(payload, job_type="market_data_collect_batch")

    def create_update_batch_job(self, request: MarketDataBatchRequest) -> dict:
        payload = {"op": "update_batch", "request": request.model_dump(mode="json")}
        return self._create_job(payload, job_type="market_data_update_batch")

    def get_job(self, job_id: str) -> dict:
        job = self._job_repo.get_by_id(job_id)
        if job is None or not str(job.get("job_type", "")).startswith("market_data_"):
            raise ValueError(f"market data job not found: {job_id}")
        return job

    def list_jobs(self, limit: int = 20, status: str | None = None, job_type: str | None = None) -> list[dict]:
        if job_type and job_type not in {
            "market_data_collect",
            "market_data_update",
            "market_data_validate",
            "market_data_collect_batch",
            "market_data_update_batch",
        }:
            return []
        if job_type:
            return self._job_repo.list_filtered(limit=limit, status=status, job_type=job_type)
        jobs = self._job_repo.list_filtered(limit=200, status=status)
        jobs = [j for j in jobs if str(j.get("job_type", "")).startswith("market_data_")]
        return jobs[:limit]

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
            raise ValueError(f"market data job not found: {job_id}")
        self._dispatch_jobs()
        return updated

    def retry_job(self, job_id: str) -> dict:
        old = self.get_job(job_id)
        if old["status"] != "failed":
            raise ValueError("retry is allowed only for failed jobs")
        payload = old["request"]
        return self._create_job(
            payload,
            job_type=old["job_type"],
            retry_count=int(old.get("retry_count", 0)) + 1,
            parent_job_id=old["job_id"],
        )

    def _create_job(
        self,
        payload: dict,
        job_type: str,
        retry_count: int = 0,
        parent_job_id: str | None = None,
    ) -> dict:
        request_hash = self._hash_request(payload | {"job_type": job_type})
        duplicate = self._job_repo.get_latest_active_by_request_hash(request_hash, job_type=job_type)
        if duplicate:
            return {**duplicate, "duplicate_of_job_id": duplicate["job_id"]}

        now = datetime.utcnow().isoformat()
        job = {
            "job_id": uuid4().hex,
            "job_type": job_type,
            "status": "queued",
            "progress": 0.0,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "related_dataset_id": None,
            "error_summary": None,
            "error_detail": None,
            "retry_count": retry_count,
            "parent_job_id": parent_job_id,
            "request_hash": request_hash,
            "duplicate_of_job_id": None,
            "cancel_requested": False,
            "request": payload,
            "batch_id": payload.get("batch_id"),
            "total_combinations": None,
            "completed_combinations": 0,
            "failed_combinations": 0,
            "current_symbol": None,
            "current_timeframe": None,
            "combination_results": None,
        }
        self._job_repo.create(job)
        self._dispatch_jobs()
        return job

    def _dispatch_jobs(self) -> None:
        with self._dispatch_lock:
            while self._active_running_count() < self._max_concurrent_jobs:
                next_job = self._next_queued_market_data_job()
                if next_job is None:
                    return
                self._job_repo.update(
                    next_job["job_id"],
                    {"status": "running", "started_at": datetime.utcnow().isoformat(), "progress": 3.0},
                )
                worker = Thread(target=self._run_job, args=(next_job["job_id"],), daemon=True)
                worker.start()

    def _run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)

        def set_progress(value: float) -> None:
            current = self._job_repo.get_by_id(job_id)
            if not current or current.get("status") != "running":
                return
            safe = max(current.get("progress", 0.0), min(float(value), 100.0))
            self._job_repo.update(job_id, {"progress": safe})

        def set_batch_progress(completed: int, total: int, symbol: str | None, timeframe: str | None) -> None:
            current = self._job_repo.get_by_id(job_id)
            if not current or current.get("status") != "running":
                return
            pct = 5.0 if total <= 0 else max(5.0, min(100.0, (completed / total) * 100))
            self._job_repo.update(
                job_id,
                {
                    "progress": pct,
                    "total_combinations": total,
                    "completed_combinations": completed,
                    "current_symbol": symbol,
                    "current_timeframe": timeframe,
                },
            )

        try:
            payload = job["request"]
            op = payload.get("op")
            result: dict
            if op == "collect":
                result = self._market_data_service.collect(
                    MarketDataCollectRequest(**payload["request"]),
                    progress_callback=set_progress,
                )
            elif op == "update":
                result = self._market_data_service.update(
                    MarketDataUpdateRequest(**payload["request"]),
                    progress_callback=set_progress,
                )
            elif op == "validate":
                set_progress(25)
                detail = self._market_data_service.validate_dataset(payload["dataset_id"], progress_callback=set_progress)
                result = {
                    "dataset_id": detail["manifest"]["dataset_id"],
                }
            elif op == "collect_batch":
                req = MarketDataBatchRequest(**payload["request"])
                req.mode = "full_collect"
                result = self._market_data_service.collect_batch(req, progress_callback=set_batch_progress)
            elif op == "update_batch":
                req = MarketDataBatchRequest(**payload["request"])
                req.mode = "incremental_update"
                result = self._market_data_service.collect_batch(req, progress_callback=set_batch_progress)
            else:
                raise ValueError(f"unsupported market data op: {op}")
            now = datetime.utcnow().isoformat()
            self._job_repo.update(
                job_id,
                {
                    "status": "completed",
                    "progress": 100.0,
                    "finished_at": now,
                    "duration_seconds": self._duration_seconds(job.get("started_at"), now),
                    "related_dataset_id": result.get("dataset_id"),
                    "batch_id": result.get("batch_id"),
                    "total_combinations": result.get("total_requested_combinations"),
                    "completed_combinations": result.get("completed_combinations"),
                    "failed_combinations": result.get("failed_combinations"),
                    "combination_results": result.get("items"),
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

    def _active_running_count(self) -> int:
        jobs = self._job_repo.list_filtered(limit=500, status="running")
        return sum(1 for job in jobs if str(job.get("job_type", "")).startswith("market_data_"))

    def _next_queued_market_data_job(self) -> dict | None:
        jobs = self._job_repo.list_filtered(limit=500, status="queued")
        for job in reversed(jobs):
            if str(job.get("job_type", "")).startswith("market_data_"):
                return job
        return None

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

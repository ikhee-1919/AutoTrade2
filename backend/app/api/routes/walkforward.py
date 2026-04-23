from datetime import datetime
import csv
import io
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.dependencies import get_walkforward_job_service, get_walkforward_service
from app.schemas.walkforward import (
    WalkforwardBatchRunRequest,
    WalkforwardBatchRunResponse,
    WalkforwardCompareResponse,
    WalkforwardJobListResponse,
    WalkforwardJobResponse,
    WalkforwardListItem,
    WalkforwardListResponse,
    WalkforwardRunRequest,
    WalkforwardRunResponse,
)
from app.services.walkforward_job_service import WalkforwardJobService
from app.services.walkforward_service import WalkforwardService

router = APIRouter(prefix="/walkforward", tags=["walkforward"])


def _job_status(status: str) -> str:
    return "completed" if status == "succeeded" else status


@router.post("/run", response_model=WalkforwardRunResponse)
def run_walkforward(
    body: WalkforwardRunRequest,
    walkforward_service: WalkforwardService = Depends(get_walkforward_service),
) -> WalkforwardRunResponse:
    try:
        result = walkforward_service.run(body)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WalkforwardRunResponse(**result)


@router.get("", response_model=WalkforwardListResponse)
def list_walkforward_runs(
    limit: int = 20,
    walkforward_service: WalkforwardService = Depends(get_walkforward_service),
) -> WalkforwardListResponse:
    runs = walkforward_service.list_runs(limit=limit)
    items = [
        WalkforwardListItem(
            walkforward_run_id=run["walkforward_run_id"],
            created_at=datetime.fromisoformat(run["created_at"]),
            strategy_id=run["strategy_id"],
            strategy_version=run.get("strategy_version", "unknown"),
            symbol=run["symbol"],
            timeframe=run["timeframe"],
            timeframe_mapping=run.get("timeframe_mapping"),
            requested_period={
                "start_date": datetime.fromisoformat(run["requested_period"]["start_date"]).date(),
                "end_date": datetime.fromisoformat(run["requested_period"]["end_date"]).date(),
            },
            walkforward_mode=run.get("walkforward_mode", "rolling"),
            segment_count=run.get("summary", {}).get("segment_count", 0),
            completed_segment_count=run.get("summary", {}).get("completed_segment_count", 0),
            total_net_return_pct=run.get("summary", {}).get("total_net_return_pct", 0.0),
            average_segment_return_pct=run.get("summary", {}).get("average_segment_return_pct", 0.0),
            profitable_segments=run.get("diagnostics", {}).get("profitable_segments", 0),
            segments_beating_benchmark=run.get("diagnostics", {}).get(
                "segments_beating_benchmark",
                0,
            ),
        )
        for run in runs
    ]
    return WalkforwardListResponse(items=items)


@router.get("/compare", response_model=WalkforwardCompareResponse)
def compare_walkforward_runs(
    walkforward_run_ids: list[str] = Query(default=[]),
    walkforward_service: WalkforwardService = Depends(get_walkforward_service),
) -> WalkforwardCompareResponse:
    try:
        items = walkforward_service.compare_runs(walkforward_run_ids=walkforward_run_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WalkforwardCompareResponse(
        compared_count=len(items),
        best_walkforward_run_id=items[0]["walkforward_run_id"],
        items=items,
    )


@router.get("/compare.csv")
def compare_walkforward_runs_csv(
    walkforward_run_ids: list[str] = Query(default=[]),
    walkforward_service: WalkforwardService = Depends(get_walkforward_service),
) -> Response:
    try:
        items = walkforward_service.compare_runs(walkforward_run_ids=walkforward_run_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "walkforward_run_id",
            "created_at",
            "strategy_id",
            "symbol",
            "walkforward_mode",
            "segment_count",
            "total_net_return_pct",
            "average_segment_return_pct",
            "worst_segment_return_pct",
            "best_segment_return_pct",
            "segments_beating_benchmark",
            "profitable_segments",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item["walkforward_run_id"],
                item["created_at"].isoformat(),
                item["strategy_id"],
                item["symbol"],
                item.get("walkforward_mode", "rolling"),
                item["segment_count"],
                item["total_net_return_pct"],
                item["average_segment_return_pct"],
                item["worst_segment_return_pct"],
                item["best_segment_return_pct"],
                item["segments_beating_benchmark"],
                item["profitable_segments"],
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=walkforward_compare.csv"},
    )


@router.post("/batch-run", response_model=WalkforwardBatchRunResponse)
def batch_run_walkforward(
    body: WalkforwardBatchRunRequest,
    walkforward_service: WalkforwardService = Depends(get_walkforward_service),
    walkforward_job_service: WalkforwardJobService = Depends(get_walkforward_job_service),
) -> WalkforwardBatchRunResponse:
    batch_id = uuid4().hex
    now = datetime.utcnow()
    items = []
    for symbol in body.symbols:
        for mode in body.walkforward_modes:
            request = WalkforwardRunRequest(
                strategy_id=body.strategy_id,
                symbol=symbol,
                timeframe=body.timeframe,
                timeframe_mapping=body.timeframe_mapping,
                start_date=body.start_date,
                end_date=body.end_date,
                train_window_size=body.train_window_size,
                test_window_size=body.test_window_size,
                step_size=body.step_size,
                window_unit=body.window_unit,
                walkforward_mode=mode,
                params=body.params,
                fee_rate=body.fee_rate,
                entry_fee_rate=body.entry_fee_rate,
                exit_fee_rate=body.exit_fee_rate,
                apply_fee_on_entry=body.apply_fee_on_entry,
                apply_fee_on_exit=body.apply_fee_on_exit,
                slippage_rate=body.slippage_rate,
                entry_slippage_rate=body.entry_slippage_rate,
                exit_slippage_rate=body.exit_slippage_rate,
                execution_policy=body.execution_policy,
                benchmark_enabled=body.benchmark_enabled,
                run_tag=f"batch:{batch_id}",
            )
            if body.use_jobs:
                job = walkforward_job_service.create_job(request)
                items.append(
                    {
                        "symbol": symbol,
                        "walkforward_mode": mode,
                        "status": "queued",
                        "job_id": job["job_id"],
                        "walkforward_run_id": None,
                    }
                )
            else:
                result = walkforward_service.run(request)
                items.append(
                    {
                        "symbol": symbol,
                        "walkforward_mode": mode,
                        "status": "completed",
                        "job_id": None,
                        "walkforward_run_id": result["walkforward_run_id"],
                    }
                )
    return WalkforwardBatchRunResponse(
        batch_id=batch_id,
        created_at=now,
        total_requested=len(items),
        items=items,
    )


@router.post("/jobs", response_model=WalkforwardJobResponse)
def create_walkforward_job(
    body: WalkforwardRunRequest,
    job_service: WalkforwardJobService = Depends(get_walkforward_job_service),
) -> WalkforwardJobResponse:
    job = job_service.create_job(body)
    return WalkforwardJobResponse(
        job_id=job["job_id"],
        job_type=job.get("job_type", "walkforward"),
        status=_job_status(job["status"]),
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_walkforward_run_id=job.get("related_walkforward_run_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        segment_total=job.get("segment_total"),
        segment_completed=job.get("segment_completed"),
        failed_segment_index=job.get("failed_segment_index"),
        request=WalkforwardRunRequest(**job["request"]),
    )


@router.get("/jobs", response_model=WalkforwardJobListResponse)
def list_walkforward_jobs(
    limit: int = 20,
    status: str | None = None,
    job_service: WalkforwardJobService = Depends(get_walkforward_job_service),
) -> WalkforwardJobListResponse:
    jobs = job_service.list_jobs(limit=limit, status=status)
    items = [
        WalkforwardJobResponse(
            job_id=job["job_id"],
            job_type=job.get("job_type", "walkforward"),
            status=_job_status(job["status"]),
            progress=job.get("progress", 0.0),
            created_at=datetime.fromisoformat(job["created_at"]),
            started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
            finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
            duration_seconds=job.get("duration_seconds"),
            related_walkforward_run_id=job.get("related_walkforward_run_id"),
            error_summary=job.get("error_summary"),
            error_detail=job.get("error_detail"),
            retry_count=job.get("retry_count", 0),
            parent_job_id=job.get("parent_job_id"),
            request_hash=job.get("request_hash", ""),
            duplicate_of_job_id=job.get("duplicate_of_job_id"),
            segment_total=job.get("segment_total"),
            segment_completed=job.get("segment_completed"),
            failed_segment_index=job.get("failed_segment_index"),
            request=WalkforwardRunRequest(**job["request"]),
        )
        for job in jobs
    ]
    return WalkforwardJobListResponse(items=items)


@router.get("/jobs/{job_id}", response_model=WalkforwardJobResponse)
def get_walkforward_job(
    job_id: str,
    job_service: WalkforwardJobService = Depends(get_walkforward_job_service),
) -> WalkforwardJobResponse:
    try:
        job = job_service.get_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WalkforwardJobResponse(
        job_id=job["job_id"],
        job_type=job.get("job_type", "walkforward"),
        status=_job_status(job["status"]),
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_walkforward_run_id=job.get("related_walkforward_run_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        segment_total=job.get("segment_total"),
        segment_completed=job.get("segment_completed"),
        failed_segment_index=job.get("failed_segment_index"),
        request=WalkforwardRunRequest(**job["request"]),
    )


@router.post("/jobs/{job_id}/cancel", response_model=WalkforwardJobResponse)
def cancel_walkforward_job(
    job_id: str,
    job_service: WalkforwardJobService = Depends(get_walkforward_job_service),
) -> WalkforwardJobResponse:
    try:
        job = job_service.cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WalkforwardJobResponse(
        job_id=job["job_id"],
        job_type=job.get("job_type", "walkforward"),
        status=_job_status(job["status"]),
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_walkforward_run_id=job.get("related_walkforward_run_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        segment_total=job.get("segment_total"),
        segment_completed=job.get("segment_completed"),
        failed_segment_index=job.get("failed_segment_index"),
        request=WalkforwardRunRequest(**job["request"]),
    )


@router.post("/jobs/{job_id}/retry", response_model=WalkforwardJobResponse)
def retry_walkforward_job(
    job_id: str,
    job_service: WalkforwardJobService = Depends(get_walkforward_job_service),
) -> WalkforwardJobResponse:
    try:
        job = job_service.retry_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WalkforwardJobResponse(
        job_id=job["job_id"],
        job_type=job.get("job_type", "walkforward"),
        status=_job_status(job["status"]),
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_walkforward_run_id=job.get("related_walkforward_run_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        segment_total=job.get("segment_total"),
        segment_completed=job.get("segment_completed"),
        failed_segment_index=job.get("failed_segment_index"),
        request=WalkforwardRunRequest(**job["request"]),
    )


@router.post("/rerun/{walkforward_run_id}", response_model=WalkforwardRunResponse)
def rerun_walkforward(
    walkforward_run_id: str,
    walkforward_service: WalkforwardService = Depends(get_walkforward_service),
) -> WalkforwardRunResponse:
    try:
        result = walkforward_service.rerun(walkforward_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WalkforwardRunResponse(**result)


@router.get("/{walkforward_run_id}", response_model=WalkforwardRunResponse)
def get_walkforward_detail(
    walkforward_run_id: str,
    walkforward_service: WalkforwardService = Depends(get_walkforward_service),
) -> WalkforwardRunResponse:
    try:
        result = walkforward_service.get_run_detail(walkforward_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WalkforwardRunResponse(**result)

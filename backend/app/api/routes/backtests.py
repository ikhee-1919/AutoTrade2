from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_backtest_job_service, get_backtest_service
from app.schemas.backtest import (
    BacktestCompareResponse,
    BacktestJobListResponse,
    BacktestJobResponse,
    BacktestRecentItem,
    BacktestRecentResponse,
    BacktestRunRequest,
    BacktestRunResponse,
)
from app.services.backtest_job_service import BacktestJobService
from app.services.backtest_service import BacktestService

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _job_status(status: str) -> str:
    return "completed" if status == "succeeded" else status


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(
    body: BacktestRunRequest,
    backtest_service: BacktestService = Depends(get_backtest_service),
) -> BacktestRunResponse:
    try:
        result = backtest_service.run(body)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BacktestRunResponse(**result)


@router.post("/jobs", response_model=BacktestJobResponse)
def create_backtest_job(
    body: BacktestRunRequest,
    job_service: BacktestJobService = Depends(get_backtest_job_service),
) -> BacktestJobResponse:
    job = job_service.create_job(body)
    return BacktestJobResponse(
        job_id=job["job_id"],
        job_type=job.get("job_type", "backtest"),
        status=_job_status(job["status"]),
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_run_id=job.get("related_run_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        request=BacktestRunRequest(**job["request"]),
    )


@router.get("/jobs", response_model=BacktestJobListResponse)
def list_backtest_jobs(
    limit: int = 20,
    status: str | None = None,
    job_type: str | None = Query(default="backtest"),
    job_service: BacktestJobService = Depends(get_backtest_job_service),
) -> BacktestJobListResponse:
    jobs = job_service.list_jobs(limit=limit, status=status, job_type=job_type)
    items = [
        BacktestJobResponse(
            job_id=job["job_id"],
            job_type=job.get("job_type", "backtest"),
            status=_job_status(job["status"]),
            progress=job.get("progress", 0.0),
            created_at=datetime.fromisoformat(job["created_at"]),
            started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
            finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
            duration_seconds=job.get("duration_seconds"),
            related_run_id=job.get("related_run_id"),
            error_summary=job.get("error_summary"),
            error_detail=job.get("error_detail"),
            retry_count=job.get("retry_count", 0),
            parent_job_id=job.get("parent_job_id"),
            request_hash=job.get("request_hash", ""),
            duplicate_of_job_id=job.get("duplicate_of_job_id"),
            request=BacktestRunRequest(**job["request"]),
        )
        for job in jobs
    ]
    return BacktestJobListResponse(items=items)


@router.get("/jobs/{job_id}", response_model=BacktestJobResponse)
def backtest_job_detail(
    job_id: str,
    job_service: BacktestJobService = Depends(get_backtest_job_service),
) -> BacktestJobResponse:
    try:
        job = job_service.get_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BacktestJobResponse(
        job_id=job["job_id"],
        job_type=job.get("job_type", "backtest"),
        status=_job_status(job["status"]),
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_run_id=job.get("related_run_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        request=BacktestRunRequest(**job["request"]),
    )


@router.post("/jobs/{job_id}/cancel", response_model=BacktestJobResponse)
def cancel_backtest_job(
    job_id: str,
    job_service: BacktestJobService = Depends(get_backtest_job_service),
) -> BacktestJobResponse:
    try:
        job = job_service.cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BacktestJobResponse(
        job_id=job["job_id"],
        job_type=job.get("job_type", "backtest"),
        status=_job_status(job["status"]),
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_run_id=job.get("related_run_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        request=BacktestRunRequest(**job["request"]),
    )


@router.post("/jobs/{job_id}/retry", response_model=BacktestJobResponse)
def retry_backtest_job(
    job_id: str,
    job_service: BacktestJobService = Depends(get_backtest_job_service),
) -> BacktestJobResponse:
    try:
        job = job_service.retry_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BacktestJobResponse(
        job_id=job["job_id"],
        job_type=job.get("job_type", "backtest"),
        status=_job_status(job["status"]),
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_run_id=job.get("related_run_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        request=BacktestRunRequest(**job["request"]),
    )


@router.post("/rerun/{run_id}", response_model=BacktestRunResponse)
def rerun_backtest(
    run_id: str,
    backtest_service: BacktestService = Depends(get_backtest_service),
) -> BacktestRunResponse:
    try:
        result = backtest_service.rerun(run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BacktestRunResponse(**result)


@router.get("/recent", response_model=BacktestRecentResponse)
def recent_backtests(
    limit: int = 5,
    backtest_service: BacktestService = Depends(get_backtest_service),
) -> BacktestRecentResponse:
    runs = backtest_service.recent_runs(limit=limit)
    items = [
        BacktestRecentItem(
            run_id=run["run_id"],
            rerun_of_run_id=run.get("rerun_of_run_id"),
            run_at=datetime.fromisoformat(run["run_at"]),
            strategy_id=run["strategy_id"],
            strategy_version=run.get("strategy_version", "unknown"),
            code_version=run.get("code_version", "unknown"),
            symbol=run["symbol"],
            timeframe=run["timeframe"],
            timeframe_mapping=run.get("timeframe_mapping"),
            indicator_start=(
                datetime.fromisoformat(run["indicator_start"]).date()
                if run.get("indicator_start")
                else None
            ),
            warmup_start=(
                datetime.fromisoformat(run["warmup_start"]).date()
                if run.get("warmup_start")
                else None
            ),
            trade_start=(
                datetime.fromisoformat(run["trade_start"]).date()
                if run.get("trade_start")
                else datetime.fromisoformat(run["start_date"]).date()
            ),
            trade_end=(
                datetime.fromisoformat(run["trade_end"]).date()
                if run.get("trade_end")
                else datetime.fromisoformat(run["end_date"]).date()
            ),
            start_date=datetime.fromisoformat(run["start_date"]).date(),
            end_date=datetime.fromisoformat(run["end_date"]).date(),
            params_used=run.get("params_used", {}),
            params_snapshot=run.get("params_snapshot", run.get("params_used", {})),
            params_hash=run.get("params_hash", ""),
            data_signature=run.get(
                "data_signature",
                {
                    "source": "csv",
                    "candle_count": 0,
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "candles_hash": "",
                    "dataset_id": None,
                    "dataset_signature": None,
                },
            ),
            selected_datasets_by_role=run.get("selected_datasets_by_role", {}),
            execution_config=run.get(
                "execution_config",
                {
                    "execution_policy": "next_open",
                    "fee_rate": 0.0005,
                    "entry_fee_rate": 0.0005,
                    "exit_fee_rate": 0.0005,
                    "apply_fee_on_entry": True,
                    "apply_fee_on_exit": True,
                    "slippage_rate": 0.0003,
                    "entry_slippage_rate": 0.0003,
                    "exit_slippage_rate": 0.0003,
                    "benchmark_enabled": True,
                },
            ),
            run_tag=run.get("run_tag"),
            total_return_pct=run.get("summary", {}).get(
                "total_return_pct",
                run.get("summary", {}).get("net_return_pct", 0.0),
            ),
            gross_return_pct=run.get("summary", {}).get("gross_return_pct", 0.0),
            net_return_pct=run.get("summary", {}).get(
                "net_return_pct",
                run.get("summary", {}).get("total_return_pct", 0.0),
            ),
            total_trading_cost=run.get("summary", {}).get("total_trading_cost", 0.0),
            cost_drag_pct=run.get("summary", {}).get("cost_drag_pct", 0.0),
            benchmark_buy_and_hold_return_pct=run.get("benchmark", {}).get(
                "benchmark_buy_and_hold_return_pct",
                0.0,
            ),
            strategy_excess_return_pct=run.get("benchmark", {}).get("strategy_excess_return_pct", 0.0),
            trade_count=run["summary"]["trade_count"],
        )
        for run in runs
    ]
    return BacktestRecentResponse(items=items)


@router.get("/compare", response_model=BacktestCompareResponse)
def compare_backtests(
    run_ids: list[str] = Query(default=[]),
    backtest_service: BacktestService = Depends(get_backtest_service),
) -> BacktestCompareResponse:
    try:
        compared = backtest_service.compare_runs(run_ids=run_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BacktestCompareResponse(
        compared_count=len(compared),
        best_run_id=compared[0]["run_id"],
        items=compared,
    )


@router.get("/{run_id}", response_model=BacktestRunResponse)
def backtest_detail(
    run_id: str,
    backtest_service: BacktestService = Depends(get_backtest_service),
) -> BacktestRunResponse:
    try:
        result = backtest_service.get_run_detail(run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return BacktestRunResponse(**result)

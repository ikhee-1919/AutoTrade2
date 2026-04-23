from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_parameter_sweep_job_service, get_parameter_sweep_service
from app.schemas.sweep import (
    SweepJobListResponse,
    SweepJobResponse,
    SweepListResponse,
    SweepResultsResponse,
    SweepRunRequest,
    SweepRunResponse,
    SweepTopResponse,
)
from app.services.parameter_sweep_job_service import ParameterSweepJobService
from app.services.parameter_sweep_service import ParameterSweepService

router = APIRouter(prefix="/sweeps", tags=["sweeps"])


def _to_job_response(job: dict) -> SweepJobResponse:
    return SweepJobResponse(
        job_id=job["job_id"],
        job_type=job["job_type"],
        status=job["status"],
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_sweep_run_id=job.get("related_sweep_run_id"),
        total_combinations=job.get("total_combinations"),
        completed_combinations=job.get("completed_combinations"),
        failed_combinations=job.get("failed_combinations"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        request=SweepRunRequest(**job["request"]),
    )


@router.post("/run", response_model=SweepRunResponse | SweepJobResponse)
def run_sweep(
    body: SweepRunRequest,
    sweep_service: ParameterSweepService = Depends(get_parameter_sweep_service),
    sweep_job_service: ParameterSweepJobService = Depends(get_parameter_sweep_job_service),
) -> SweepRunResponse | SweepJobResponse:
    try:
        if body.use_job:
            job = sweep_job_service.create_job(body)
            return _to_job_response(job)
        result = sweep_service.run(body)
        return SweepRunResponse(**result)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=SweepListResponse)
def list_sweeps(
    limit: int = Query(default=20, ge=1, le=100),
    sweep_service: ParameterSweepService = Depends(get_parameter_sweep_service),
) -> SweepListResponse:
    return SweepListResponse(items=sweep_service.list_runs(limit=limit))


@router.get("/jobs", response_model=SweepJobListResponse)
def list_sweep_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    sweep_job_service: ParameterSweepJobService = Depends(get_parameter_sweep_job_service),
) -> SweepJobListResponse:
    jobs = sweep_job_service.list_jobs(limit=limit, status=status)
    return SweepJobListResponse(items=[_to_job_response(job) for job in jobs])


@router.get("/jobs/{job_id}", response_model=SweepJobResponse)
def sweep_job_detail(
    job_id: str,
    sweep_job_service: ParameterSweepJobService = Depends(get_parameter_sweep_job_service),
) -> SweepJobResponse:
    try:
        return _to_job_response(sweep_job_service.get_job(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=SweepJobResponse)
def cancel_sweep_job(
    job_id: str,
    sweep_job_service: ParameterSweepJobService = Depends(get_parameter_sweep_job_service),
) -> SweepJobResponse:
    try:
        return _to_job_response(sweep_job_service.cancel_job(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/retry", response_model=SweepJobResponse)
def retry_sweep_job(
    job_id: str,
    sweep_job_service: ParameterSweepJobService = Depends(get_parameter_sweep_job_service),
) -> SweepJobResponse:
    try:
        return _to_job_response(sweep_job_service.retry_job(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rerun/{sweep_run_id}", response_model=SweepRunResponse)
def rerun_sweep(
    sweep_run_id: str,
    sweep_service: ParameterSweepService = Depends(get_parameter_sweep_service),
) -> SweepRunResponse:
    try:
        result = sweep_service.rerun(sweep_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SweepRunResponse(**result)


@router.get("/{sweep_run_id}/results", response_model=SweepResultsResponse)
def sweep_results(
    sweep_run_id: str,
    sweep_service: ParameterSweepService = Depends(get_parameter_sweep_service),
) -> SweepResultsResponse:
    try:
        items = sweep_service.get_results(sweep_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SweepResultsResponse(sweep_run_id=sweep_run_id, total=len(items), items=items)


@router.get("/{sweep_run_id}/top", response_model=SweepTopResponse)
def sweep_top(
    sweep_run_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default="net_return_pct"),
    sweep_service: ParameterSweepService = Depends(get_parameter_sweep_service),
) -> SweepTopResponse:
    try:
        items = sweep_service.get_top(sweep_run_id=sweep_run_id, limit=limit, sort_by=sort_by)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SweepTopResponse(sweep_run_id=sweep_run_id, sort_by=sort_by, items=items)


@router.get("/{sweep_run_id}", response_model=SweepRunResponse)
def sweep_detail(
    sweep_run_id: str,
    sweep_service: ParameterSweepService = Depends(get_parameter_sweep_service),
) -> SweepRunResponse:
    try:
        return SweepRunResponse(**sweep_service.get_run_detail(sweep_run_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

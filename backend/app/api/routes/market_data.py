from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_market_data_job_service, get_market_data_service
from app.schemas.market_data import (
    MarketDataBatchRequest,
    MarketDataBatchResult,
    MarketDataCollectRequest,
    MarketDataDetailResponse,
    MarketDataJobListResponse,
    MarketDataJobResponse,
    MarketDataListResponse,
    MarketDataOperationResponse,
    MarketDataPreviewResponse,
    MarketDataSummaryResponse,
    MarketDataUpdateRequest,
    MarketDataValidateRequest,
)
from app.services.market_data_job_service import MarketDataJobService
from app.services.market_data_service import MarketDataService

router = APIRouter(prefix="/market-data", tags=["market-data"])


def _to_job_response(job: dict) -> MarketDataJobResponse:
    return MarketDataJobResponse(
        job_id=job["job_id"],
        job_type=job["job_type"],
        status=job["status"],
        progress=job.get("progress", 0.0),
        created_at=datetime.fromisoformat(job["created_at"]),
        started_at=datetime.fromisoformat(job["started_at"]) if job.get("started_at") else None,
        finished_at=datetime.fromisoformat(job["finished_at"]) if job.get("finished_at") else None,
        duration_seconds=job.get("duration_seconds"),
        related_dataset_id=job.get("related_dataset_id"),
        error_summary=job.get("error_summary"),
        error_detail=job.get("error_detail"),
        retry_count=job.get("retry_count", 0),
        parent_job_id=job.get("parent_job_id"),
        request_hash=job.get("request_hash", ""),
        duplicate_of_job_id=job.get("duplicate_of_job_id"),
        batch_id=job.get("batch_id"),
        total_combinations=job.get("total_combinations"),
        completed_combinations=job.get("completed_combinations"),
        failed_combinations=job.get("failed_combinations"),
        current_symbol=job.get("current_symbol"),
        current_timeframe=job.get("current_timeframe"),
        combination_results=job.get("combination_results"),
        request=job.get("request", {}),
    )


@router.post("/collect", response_model=MarketDataOperationResponse)
def collect_market_data(
    body: MarketDataCollectRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataOperationResponse:
    try:
        if body.use_job:
            job = market_data_job_service.create_collect_job(body)
            return MarketDataOperationResponse(mode="job", job_id=job["job_id"], message="collect job queued")
        result = market_data_service.collect(body)
        return MarketDataOperationResponse(mode="sync", result=result)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/update", response_model=MarketDataOperationResponse)
def update_market_data(
    body: MarketDataUpdateRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataOperationResponse:
    try:
        if body.use_job:
            job = market_data_job_service.create_update_job(body)
            return MarketDataOperationResponse(mode="job", job_id=job["job_id"], message="update job queued")
        result = market_data_service.update(body)
        return MarketDataOperationResponse(mode="sync", result=result)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/collect-batch", response_model=MarketDataBatchResult)
def collect_market_data_batch(
    body: MarketDataBatchRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataBatchResult:
    try:
        body.mode = "full_collect"
        if body.use_job:
            job = market_data_job_service.create_collect_batch_job(body)
            return MarketDataBatchResult(
                mode="job",
                batch_id=job["job_id"],
                total_requested_combinations=len(body.symbols) * len(body.timeframes),
                completed_combinations=0,
                failed_combinations=0,
                skipped_combinations=0,
                created_datasets=0,
                updated_datasets=0,
                pass_count=0,
                warning_count=0,
                fail_count=0,
                job_id=job["job_id"],
                items=[],
                message="collect batch job queued",
            )
        return MarketDataBatchResult(**market_data_service.collect_batch(body))
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/update-batch", response_model=MarketDataBatchResult)
def update_market_data_batch(
    body: MarketDataBatchRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataBatchResult:
    try:
        body.mode = "incremental_update"
        if body.use_job:
            job = market_data_job_service.create_update_batch_job(body)
            return MarketDataBatchResult(
                mode="job",
                batch_id=job["job_id"],
                total_requested_combinations=len(body.symbols) * len(body.timeframes),
                completed_combinations=0,
                failed_combinations=0,
                skipped_combinations=0,
                created_datasets=0,
                updated_datasets=0,
                pass_count=0,
                warning_count=0,
                fail_count=0,
                job_id=job["job_id"],
                items=[],
                message="update batch job queued",
            )
        return MarketDataBatchResult(**market_data_service.collect_batch(body))
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=MarketDataListResponse)
def list_market_data(
    source: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    quality_status: str | None = Query(default=None),
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> MarketDataListResponse:
    items = market_data_service.list_datasets(
        source=source,
        symbol=symbol,
        timeframe=timeframe,
        quality_status=quality_status,
    )
    return MarketDataListResponse(items=items)


@router.get("/summary", response_model=MarketDataSummaryResponse)
def market_data_summary(
    source: str | None = Query(default=None),
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> MarketDataSummaryResponse:
    return MarketDataSummaryResponse(**market_data_service.summary(source=source))


@router.get("/by-symbol/{symbol}", response_model=MarketDataListResponse)
def market_data_by_symbol(
    symbol: str,
    source: str | None = Query(default=None),
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> MarketDataListResponse:
    return MarketDataListResponse(items=market_data_service.list_datasets(source=source, symbol=symbol))


@router.get("/jobs", response_model=MarketDataJobListResponse)
def list_market_data_jobs(
    limit: int = 20,
    status: str | None = None,
    job_type: str | None = Query(default=None),
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataJobListResponse:
    jobs = market_data_job_service.list_jobs(limit=limit, status=status, job_type=job_type)
    return MarketDataJobListResponse(items=[_to_job_response(job) for job in jobs])


@router.get("/jobs/{job_id}", response_model=MarketDataJobResponse)
def market_data_job_detail(
    job_id: str,
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataJobResponse:
    try:
        return _to_job_response(market_data_job_service.get_job(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=MarketDataJobResponse)
def cancel_market_data_job(
    job_id: str,
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataJobResponse:
    try:
        return _to_job_response(market_data_job_service.cancel_job(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/retry", response_model=MarketDataJobResponse)
def retry_market_data_job(
    job_id: str,
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataJobResponse:
    try:
        return _to_job_response(market_data_job_service.retry_job(job_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{dataset_id}", response_model=MarketDataDetailResponse)
def dataset_detail(
    dataset_id: str,
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> MarketDataDetailResponse:
    try:
        payload = market_data_service.get_dataset(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MarketDataDetailResponse(**payload)


@router.post("/{dataset_id}/validate", response_model=MarketDataOperationResponse)
def validate_dataset(
    dataset_id: str,
    body: MarketDataValidateRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    market_data_job_service: MarketDataJobService = Depends(get_market_data_job_service),
) -> MarketDataOperationResponse:
    try:
        if body.use_job:
            job = market_data_job_service.create_validate_job(dataset_id)
            return MarketDataOperationResponse(mode="job", job_id=job["job_id"], message="validate job queued")
        detail = market_data_service.validate_dataset(dataset_id)
        result = {
            "dataset_id": detail["manifest"]["dataset_id"],
            "source": detail["manifest"]["source"],
            "symbol": detail["manifest"]["symbol"],
            "timeframe": detail["manifest"]["timeframe"],
            "requested_period": {
                "start_date": datetime.fromisoformat(detail["manifest"]["start_at"]).date()
                if detail["manifest"].get("start_at")
                else datetime.utcnow().date(),
                "end_date": datetime.fromisoformat(detail["manifest"]["end_at"]).date()
                if detail["manifest"].get("end_at")
                else datetime.utcnow().date(),
            },
            "fetched_count": 0,
            "saved_count": detail["manifest"]["row_count"],
            "duplicate_removed_count": 0,
            "actual_range": {
                "start_at": detail["manifest"].get("start_at"),
                "end_at": detail["manifest"].get("end_at"),
            },
            "dataset_path": detail["manifest"]["path"],
            "data_signature": detail["manifest"]["data_signature"],
            "quality_status": detail["manifest"]["quality_status"],
        }
        return MarketDataOperationResponse(mode="sync", result=result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{dataset_id}/preview", response_model=MarketDataPreviewResponse)
def preview_dataset(
    dataset_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    tail: bool = Query(default=True),
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> MarketDataPreviewResponse:
    try:
        return MarketDataPreviewResponse(**market_data_service.preview_dataset(dataset_id, limit=limit, tail=tail))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

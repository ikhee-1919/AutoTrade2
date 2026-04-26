from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_chart_service
from app.schemas.chart import (
    ChartBacktestOverlayResponse,
    ChartCandlesResponse,
    ChartIndicatorsResponse,
)
from app.services.chart_service import ChartService

router = APIRouter(prefix="/charts", tags=["charts"])


@router.get("/candles", response_model=ChartCandlesResponse)
def get_chart_candles(
    symbol: str = Query(...),
    timeframe: str = Query("1d"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    chart_service: ChartService = Depends(get_chart_service),
) -> ChartCandlesResponse:
    try:
        payload = chart_service.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChartCandlesResponse(**payload)


@router.get("/indicators", response_model=ChartIndicatorsResponse)
def get_chart_indicators(
    symbol: str = Query(...),
    timeframe: str = Query("1d"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    indicators: list[str] | None = Query(default=None),
    chart_service: ChartService = Depends(get_chart_service),
) -> ChartIndicatorsResponse:
    try:
        payload = chart_service.get_indicators(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            indicators=indicators,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChartIndicatorsResponse(**payload)


@router.get("/backtest-overlay", response_model=ChartBacktestOverlayResponse)
def get_backtest_overlay(
    run_id: str = Query(...),
    chart_service: ChartService = Depends(get_chart_service),
) -> ChartBacktestOverlayResponse:
    try:
        payload = chart_service.get_backtest_overlay(run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ChartBacktestOverlayResponse(**payload)

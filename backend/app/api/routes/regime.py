from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_regime_analysis_service
from app.schemas.regime import RegimeAnalyzeResponse, RegimeBatchAnalyzeResponse
from app.services.regime_analysis_service import RegimeAnalysisService

router = APIRouter(prefix="/regime", tags=["regime"])


@router.get("/analyze", response_model=RegimeAnalyzeResponse)
def analyze_regime(
    symbol: str,
    indicator_start: date,
    analysis_start: date,
    analysis_end: date,
    regime_service: RegimeAnalysisService = Depends(get_regime_analysis_service),
) -> RegimeAnalyzeResponse:
    try:
        payload = regime_service.analyze(
            symbol=symbol,
            indicator_start=indicator_start,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegimeAnalyzeResponse(**payload)


@router.get("/analyze/batch", response_model=RegimeBatchAnalyzeResponse)
def analyze_regime_batch(
    symbols: list[str] = Query(default=[]),
    indicator_start: date = Query(...),
    analysis_start: date = Query(...),
    analysis_end: date = Query(...),
    regime_service: RegimeAnalysisService = Depends(get_regime_analysis_service),
) -> RegimeBatchAnalyzeResponse:
    try:
        payload = regime_service.analyze_batch(
            symbols=symbols,
            indicator_start=indicator_start,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegimeBatchAnalyzeResponse(**payload)

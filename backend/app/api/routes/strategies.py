from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_strategy_service
from app.schemas.strategy import (
    StrategyDetailResponse,
    StrategyMetaResponse,
    StrategyParamsResponse,
    StrategyParamsUpdateRequest,
)
from app.services.strategy_service import StrategyService

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyMetaResponse])
def list_strategies(strategy_service: StrategyService = Depends(get_strategy_service)) -> list[StrategyMetaResponse]:
    return [
        StrategyMetaResponse(
            strategy_id=s.metadata().strategy_id,
            name=s.metadata().name,
            version=s.metadata().version,
            description=s.metadata().description,
            short_description=s.metadata().short_description,
            mode=s.metadata().mode,
            spot_long_only=s.metadata().spot_long_only,
            required_roles=s.required_timeframe_roles(),
            optional_roles=s.optional_timeframe_roles(),
        )
        for s in strategy_service.list_strategies()
    ]


@router.get("/{strategy_id}", response_model=StrategyDetailResponse)
def get_strategy(
    strategy_id: str,
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> StrategyDetailResponse:
    try:
        strategy = strategy_service.get_strategy(strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    meta = strategy.metadata()
    return StrategyDetailResponse(
        strategy_id=meta.strategy_id,
        name=meta.name,
        version=meta.version,
        description=meta.description,
        short_description=meta.short_description,
        mode=meta.mode,
        spot_long_only=meta.spot_long_only,
        required_roles=strategy.required_timeframe_roles(),
        optional_roles=strategy.optional_timeframe_roles(),
        default_params=strategy.default_params(),
        default_timeframe_mapping=strategy.default_timeframe_mapping(),
    )


@router.get("/{strategy_id}/params", response_model=StrategyParamsResponse)
def get_strategy_params(
    strategy_id: str,
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> StrategyParamsResponse:
    try:
        params = strategy_service.get_effective_params(strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StrategyParamsResponse(strategy_id=strategy_id, params=params)


@router.put("/{strategy_id}/params", response_model=StrategyParamsResponse)
def update_strategy_params(
    strategy_id: str,
    body: StrategyParamsUpdateRequest,
    strategy_service: StrategyService = Depends(get_strategy_service),
) -> StrategyParamsResponse:
    try:
        updated = strategy_service.update_params(strategy_id, body.params)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StrategyParamsResponse(strategy_id=strategy_id, params=updated)

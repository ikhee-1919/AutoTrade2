from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_signal_service, get_symbol_service
from app.schemas.signal import SignalResponse, SymbolListResponse
from app.services.signal_service import SignalService
from app.services.symbol_service import SymbolService

router = APIRouter(tags=["market"])


@router.get("/symbols", response_model=SymbolListResponse)
def symbols(
    timeframe: str = Query(default="1d"),
    symbol_service: SymbolService = Depends(get_symbol_service),
) -> SymbolListResponse:
    return SymbolListResponse(symbols=symbol_service.list_symbols(timeframe=timeframe))


@router.get("/signals/{symbol}", response_model=SignalResponse)
def symbol_signals(
    symbol: str,
    strategy_id: str = Query(default="ma_regime_v1"),
    timeframe: str = Query(default="1d"),
    signal_service: SignalService = Depends(get_signal_service),
) -> SignalResponse:
    try:
        payload = signal_service.get_symbol_signals(
            symbol=symbol,
            strategy_id=strategy_id,
            timeframe=timeframe,
        )
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SignalResponse(**payload)

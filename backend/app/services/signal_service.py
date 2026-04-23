from datetime import date

from app.data.providers.csv_provider import CSVDataProvider
from app.services.strategy_service import StrategyService
from app.strategy.base import StrategyContext


class SignalService:
    def __init__(self, strategy_service: StrategyService, data_provider: CSVDataProvider) -> None:
        self._strategy_service = strategy_service
        self._data_provider = data_provider

    def get_symbol_signals(
        self,
        symbol: str,
        strategy_id: str,
        timeframe: str,
        max_points: int = 80,
    ) -> dict:
        strategy = self._strategy_service.get_strategy(strategy_id)
        params = self._strategy_service.get_effective_params(strategy_id)

        candles = self._data_provider.load_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start_date=date(2000, 1, 1),
            end_date=date(2100, 1, 1),
        )
        if not candles:
            raise ValueError(f"No candle data found for {symbol}/{timeframe}")

        signals = []
        warmup = strategy.warmup_candles(params)
        bundle = None
        if strategy.uses_context():
            mapping = strategy.default_timeframe_mapping() or {"entry": timeframe}
            if "entry" not in mapping:
                mapping["entry"] = timeframe
            try:
                bundle = self._data_provider.load_timeframe_bundle(
                    symbol=symbol,
                    timeframe_mapping=mapping,
                    start_date=date(2000, 1, 1),
                    end_date=date(2100, 1, 1),
                )
            except FileNotFoundError:
                fallback_mapping = {role: timeframe for role in mapping.keys()}
                bundle = self._data_provider.load_timeframe_bundle(
                    symbol=symbol,
                    timeframe_mapping=fallback_mapping,
                    start_date=date(2000, 1, 1),
                    end_date=date(2100, 1, 1),
                )
        for idx in range(warmup, len(candles)):
            history = candles[: idx + 1]
            if strategy.uses_context() and bundle is not None:
                as_of = candles[idx].timestamp
                candles_by_role = {
                    role: [c for c in rows if c.timestamp <= as_of]
                    for role, rows in bundle["candles_by_role"].items()
                }
                if "entry" not in candles_by_role:
                    candles_by_role["entry"] = history
                decision = strategy.evaluate_context(
                    context=StrategyContext(
                        symbol=symbol,
                        timeframe_mapping=bundle["mapping"],
                        candles_by_role=candles_by_role,
                        metadata_by_role=bundle.get("metadata_by_role", {}),
                        as_of=as_of,
                        entry_role="entry",
                    ),
                    params=params,
                )
            else:
                decision = strategy.evaluate(history, params)
            signals.append(
                {
                    "timestamp": candles[idx].timestamp.isoformat(),
                    "price": candles[idx].close,
                    "regime": decision.regime,
                    "entry_allowed": decision.entry_allowed,
                    "score": decision.score,
                    "reject_reason": decision.reject_reason,
                }
            )

        recent_prices = candles[-max_points:]
        recent_signals = signals[-max_points:]

        return {
            "symbol": symbol,
            "strategy_id": strategy_id,
            "timeframe": timeframe,
            "prices": [
                {"timestamp": candle.timestamp.isoformat(), "close": candle.close}
                for candle in recent_prices
            ],
            "signals": recent_signals,
        }

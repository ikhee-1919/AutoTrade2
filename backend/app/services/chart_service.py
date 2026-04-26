from __future__ import annotations

from datetime import date
from statistics import mean

from app.data.providers.csv_provider import CSVDataProvider
from app.repositories.backtest_run_repository import BacktestRunRepository


class ChartService:
    def __init__(
        self,
        data_provider: CSVDataProvider,
        run_repository: BacktestRunRepository,
    ) -> None:
        self._data_provider = data_provider
        self._run_repository = run_repository

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
    ) -> dict:
        normalized = self._data_provider.normalize_timeframe(timeframe)
        candles = self._data_provider.load_ohlcv(
            symbol=symbol,
            timeframe=normalized,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "symbol": symbol,
            "timeframe": normalized,
            "start_date": start_date,
            "end_date": end_date,
            "dataset": self._dataset_meta(self._data_provider.get_last_dataset_meta()),
            "items": [
                {
                    "time": candle.timestamp.isoformat(),
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
                for candle in candles
            ],
        }

    def get_indicators(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
        indicators: list[str] | None = None,
    ) -> dict:
        normalized = self._data_provider.normalize_timeframe(timeframe)
        candles = self._data_provider.load_ohlcv(
            symbol=symbol,
            timeframe=normalized,
            start_date=start_date,
            end_date=end_date,
        )
        selected = self._normalize_indicators(indicators)

        ema20 = self._ema(candles, 20) if "ema20" in selected else [None] * len(candles)
        ema50 = self._ema(candles, 50) if "ema50" in selected else [None] * len(candles)
        ema120 = self._ema(candles, 120) if "ema120" in selected else [None] * len(candles)
        rsi14 = self._rsi(candles, 14) if "rsi14" in selected else [None] * len(candles)
        volume_ma20 = self._sma_volume(candles, 20) if "volume_ma20" in selected else [None] * len(candles)

        items = []
        for idx, candle in enumerate(candles):
            items.append(
                {
                    "time": candle.timestamp.isoformat(),
                    "ema20": ema20[idx],
                    "ema50": ema50[idx],
                    "ema120": ema120[idx],
                    "rsi14": rsi14[idx],
                    "volume_ma20": volume_ma20[idx],
                }
            )

        return {
            "symbol": symbol,
            "timeframe": normalized,
            "start_date": start_date,
            "end_date": end_date,
            "dataset": self._dataset_meta(self._data_provider.get_last_dataset_meta()),
            "indicators": selected,
            "items": items,
        }

    def get_backtest_overlay(self, run_id: str) -> dict:
        run = self._run_repository.get_by_id(run_id)
        if run is None:
            raise ValueError(f"run_id not found: {run_id}")

        trades = [
            {
                "entry_time": trade.get("entry_time"),
                "entry_price": float(trade.get("entry_price", trade.get("filled_entry_price", 0.0))),
                "exit_time": trade.get("exit_time"),
                "exit_price": float(trade.get("exit_price", trade.get("filled_exit_price", 0.0))),
                "exit_reason": str(trade.get("reason", "")),
                "gross_pct": float(trade.get("gross_pnl", 0.0)),
                "net_pct": float(trade.get("net_pnl", trade.get("pnl", 0.0))),
            }
            for trade in run.get("trades", [])
        ]

        return {
            "run_id": run_id,
            "run_meta": {
                "strategy_id": run.get("strategy_id", "unknown"),
                "strategy_version": run.get("strategy_version", "unknown"),
                "code_version": run.get("code_version", "unknown"),
                "symbol": run.get("symbol", ""),
                "timeframe": run.get("timeframe", "1d"),
                "timeframe_mapping": run.get("timeframe_mapping"),
            },
            "trades": trades,
        }

    def _normalize_indicators(self, indicators: list[str] | None) -> list[str]:
        default = ["ema20", "ema50", "ema120", "rsi14", "volume_ma20"]
        if not indicators:
            return default
        allowed = set(default)
        selected = []
        for item in indicators:
            key = item.strip().lower()
            if key in allowed and key not in selected:
                selected.append(key)
        return selected or default

    def _dataset_meta(self, raw: dict | None) -> dict | None:
        if not raw:
            return None
        return {
            "source_type": raw.get("source_type", "unknown"),
            "dataset_id": raw.get("dataset_id"),
            "symbol": raw.get("symbol", ""),
            "timeframe": raw.get("timeframe", ""),
            "dataset_signature": raw.get("data_signature"),
            "quality_status": raw.get("quality_status"),
            "updated_at": raw.get("updated_at"),
        }

    def _ema(self, candles, period: int) -> list[float | None]:
        if not candles:
            return []
        closes = [c.close for c in candles]
        alpha = 2 / (period + 1)
        out: list[float | None] = []
        ema = closes[0]
        for close in closes:
            ema = close * alpha + ema * (1 - alpha)
            out.append(round(ema, 8))
        return out

    def _rsi(self, candles, period: int) -> list[float | None]:
        if not candles:
            return []
        closes = [c.close for c in candles]
        if len(closes) < 2:
            return [50.0 for _ in closes]

        gains = [0.0]
        losses = [0.0]
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))

        values: list[float | None] = [50.0 for _ in closes]
        warm = min(period + 1, len(closes))
        if warm <= 1:
            return values

        avg_gain = mean(gains[1:warm]) if warm > 1 else 0.0
        avg_loss = mean(losses[1:warm]) if warm > 1 else 0.0

        for i in range(warm, len(closes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            rs = avg_gain / max(avg_loss, 1e-9)
            values[i] = round(100 - (100 / (1 + rs)), 8)
        return values

    def _sma_volume(self, candles, period: int) -> list[float | None]:
        if not candles:
            return []
        out: list[float | None] = []
        volumes = [c.volume for c in candles]
        for idx in range(len(volumes)):
            begin = max(0, idx - period + 1)
            window = volumes[begin : idx + 1]
            out.append(round(sum(window) / len(window), 8))
        return out

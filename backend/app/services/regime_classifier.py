from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from app.models.candle import Candle


RegimeLabel = str


@dataclass(frozen=True)
class RegimePoint:
    date: str
    close: float
    sma200: float | None
    ema20: float | None
    ema50: float | None
    ema200: float | None
    sma200_slope_5d: float | None
    sma200_slope_20d: float | None
    distance_from_sma200_pct: float | None
    above_sma200: bool | None
    has_sufficient_history: bool
    regime: RegimeLabel


class RegimeClassifier:
    """200D-based market regime classifier for daily candles."""

    def classify_series(
        self,
        candles: list[Candle],
        sma_length: int = 200,
        ema_fast: int = 20,
        ema_mid: int = 50,
        ema_slow: int = 200,
        slope_short_lookback: int = 5,
        slope_long_lookback: int = 20,
    ) -> list[RegimePoint]:
        if not candles:
            return []

        closes = [c.close for c in candles]
        sma200_series = self._sma_series(closes, sma_length)
        ema_fast_series = self._ema(closes, ema_fast)
        ema_mid_series = self._ema(closes, ema_mid)
        ema_slow_series = self._ema(closes, ema_slow)

        out: list[RegimePoint] = []
        for idx, candle in enumerate(candles):
            sma200 = sma200_series[idx]
            ema20 = ema_fast_series[idx]
            ema50 = ema_mid_series[idx]
            ema200 = ema_slow_series[idx]

            if sma200 is None:
                out.append(
                    RegimePoint(
                        date=candle.timestamp.date().isoformat(),
                        close=float(candle.close),
                        sma200=None,
                        ema20=round(ema20, 6),
                        ema50=round(ema50, 6),
                        ema200=round(ema200, 6),
                        sma200_slope_5d=None,
                        sma200_slope_20d=None,
                        distance_from_sma200_pct=None,
                        above_sma200=None,
                        has_sufficient_history=False,
                        regime="insufficient_history",
                    )
                )
                continue

            slope_5 = self._slope(sma200_series, idx, slope_short_lookback)
            slope_20 = self._slope(sma200_series, idx, slope_long_lookback)
            distance_pct = ((candle.close - sma200) / max(sma200, 1e-9)) * 100
            above = candle.close > sma200
            recovery_signal = candle.close > ema20 and (
                ema20 >= ema50
                or (slope_5 is not None and slope_5 >= 0)
                or (distance_pct > -2.0)
            )

            if above and (slope_20 is not None and slope_20 > 0):
                regime = "bull_above_200"
            elif above:
                regime = "above_200_weak"
            elif (
                not above
                and (slope_20 is not None and slope_20 < 0)
                and ema20 < ema50
                and not recovery_signal
            ):
                regime = "below_200_downtrend"
            else:
                regime = "below_200_recovery"

            out.append(
                RegimePoint(
                    date=candle.timestamp.date().isoformat(),
                    close=round(float(candle.close), 6),
                    sma200=round(float(sma200), 6),
                    ema20=round(float(ema20), 6),
                    ema50=round(float(ema50), 6),
                    ema200=round(float(ema200), 6),
                    sma200_slope_5d=round(float(slope_5), 8) if slope_5 is not None else None,
                    sma200_slope_20d=round(float(slope_20), 8) if slope_20 is not None else None,
                    distance_from_sma200_pct=round(float(distance_pct), 6),
                    above_sma200=above,
                    has_sufficient_history=True,
                    regime=regime,
                )
            )
        return out

    def classify_last(self, candles: list[Candle], **kwargs) -> RegimePoint | None:
        points = self.classify_series(candles, **kwargs)
        return points[-1] if points else None

    def summarize_segment_return(self, points: list[RegimePoint]) -> float:
        if len(points) < 2:
            return 0.0
        compounded = 1.0
        for i in range(1, len(points)):
            prev = points[i - 1].close
            cur = points[i].close
            compounded *= 1 + ((cur - prev) / max(prev, 1e-9))
        return (compounded - 1) * 100

    def average_distance(self, points: list[RegimePoint]) -> float:
        vals = [p.distance_from_sma200_pct for p in points if p.distance_from_sma200_pct is not None]
        if not vals:
            return 0.0
        return mean(vals)

    def slope_state(self, points: list[RegimePoint]) -> str:
        vals = [p.sma200_slope_20d for p in points if p.sma200_slope_20d is not None]
        if not vals:
            return "unknown"
        m = mean(vals)
        if m > 0:
            return "rising"
        if m < 0:
            return "falling"
        return "flat"

    def _sma_series(self, values: list[float], window: int) -> list[float | None]:
        out: list[float | None] = [None] * len(values)
        if len(values) < window:
            return out
        rolling_sum = sum(values[:window])
        out[window - 1] = rolling_sum / window
        for idx in range(window, len(values)):
            rolling_sum += values[idx] - values[idx - window]
            out[idx] = rolling_sum / window
        return out

    def _ema(self, values: list[float], window: int) -> list[float]:
        if not values:
            return []
        k = 2 / (window + 1)
        out: list[float] = []
        ema = values[0]
        for value in values:
            ema = value * k + ema * (1 - k)
            out.append(ema)
        return out

    def _slope(self, series: list[float | None], idx: int, lookback: int) -> float | None:
        if idx - lookback < 0:
            return None
        now = series[idx]
        prev = series[idx - lookback]
        if now is None or prev is None:
            return None
        return now - prev

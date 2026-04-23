from statistics import mean
from typing import Any

from app.models.candle import Candle
from app.strategy.base import BaseStrategy, StrategyDecision, StrategyMetadata


class MovingAverageRegimeStrategy(BaseStrategy):
    """Simple sample strategy for platform validation."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="ma_regime_v1",
            name="MA Regime + Volume",
            version="1.0.0",
            description=(
                "Uses short/long moving averages and volume expansion to identify bullish entries. "
                "Returns explicit reject reasons and risk plan for explainability."
            ),
        )

    def default_params(self) -> dict[str, Any]:
        return {
            "short_window": 20,
            "long_window": 50,
            "volume_window": 20,
            "volume_multiplier": 1.2,
            "score_threshold": 0.7,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06,
        }

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        validated = self.default_params() | params

        int_fields = ["short_window", "long_window", "volume_window"]
        float_fields = [
            "volume_multiplier",
            "score_threshold",
            "stop_loss_pct",
            "take_profit_pct",
        ]

        for field in int_fields:
            value = int(validated[field])
            if value <= 1:
                raise ValueError(f"{field} must be greater than 1")
            validated[field] = value

        for field in float_fields:
            value = float(validated[field])
            if value <= 0:
                raise ValueError(f"{field} must be positive")
            validated[field] = value

        if validated["short_window"] >= validated["long_window"]:
            raise ValueError("short_window must be smaller than long_window")

        if validated["score_threshold"] > 1.0:
            raise ValueError("score_threshold must be <= 1.0")

        return validated

    def evaluate(self, candles: list[Candle], params: dict[str, Any]) -> StrategyDecision:
        p = self.validate_params(params)

        short_window = p["short_window"]
        long_window = p["long_window"]
        volume_window = p["volume_window"]
        latest = candles[-1]

        if len(candles) < long_window:
            return StrategyDecision(
                strategy_name=self.metadata().name,
                regime="unknown",
                entry_allowed=False,
                score=0.0,
                reject_reason="insufficient_history",
                stop_loss=None,
                take_profit=None,
                debug_info={"required": long_window, "current": len(candles)},
            )

        short_ma = mean(c.close for c in candles[-short_window:])
        long_ma = mean(c.close for c in candles[-long_window:])
        avg_volume = mean(c.volume for c in candles[-volume_window:])

        regime = self._detect_regime(short_ma=short_ma, long_ma=long_ma)
        trend_ok = latest.close > short_ma
        volume_ok = latest.volume >= avg_volume * p["volume_multiplier"]
        regime_ok = regime == "bullish"

        score = (0.4 if regime_ok else 0.0) + (0.3 if trend_ok else 0.0) + (0.3 if volume_ok else 0.0)
        entry_allowed = score >= p["score_threshold"]
        reject_reason = None if entry_allowed else self._reject_reason(regime_ok, trend_ok, volume_ok)

        stop_loss = latest.close * (1 - p["stop_loss_pct"])
        take_profit = latest.close * (1 + p["take_profit_pct"])

        return StrategyDecision(
            strategy_name=self.metadata().name,
            regime=regime,
            entry_allowed=entry_allowed,
            score=round(score, 4),
            reject_reason=reject_reason,
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            debug_info={
                "close": latest.close,
                "short_ma": round(short_ma, 4),
                "long_ma": round(long_ma, 4),
                "avg_volume": round(avg_volume, 4),
                "latest_volume": latest.volume,
                "conditions": {
                    "regime_ok": regime_ok,
                    "trend_ok": trend_ok,
                    "volume_ok": volume_ok,
                },
            },
        )

    def _detect_regime(self, short_ma: float, long_ma: float) -> str:
        if short_ma > long_ma * 1.005:
            return "bullish"
        if short_ma < long_ma * 0.995:
            return "bearish"
        return "neutral"

    def _reject_reason(self, regime_ok: bool, trend_ok: bool, volume_ok: bool) -> str:
        if not regime_ok:
            return "regime_not_bullish"
        if not trend_ok:
            return "trend_below_short_ma"
        if not volume_ok:
            return "volume_not_confirmed"
        return "score_below_threshold"

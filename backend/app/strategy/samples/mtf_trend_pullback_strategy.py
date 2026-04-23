from statistics import mean
from typing import Any

from app.strategy.base import BaseStrategy, StrategyContext, StrategyDecision, StrategyMetadata


class MTFTrendPullbackStrategy(BaseStrategy):
    """Sample multi-timeframe strategy for framework validation."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="mtf_trend_pullback_v1",
            name="MTF Trend Pullback",
            version="1.0.0",
            description=(
                "Uses trend/setup/entry timeframe roles. "
                "Trend is determined on higher timeframe, setup on mid timeframe, "
                "and entry trigger on lower timeframe."
            ),
            mode="multi_timeframe",
            required_roles=["trend", "setup", "entry"],
            optional_roles=["confirmation"],
        )

    def uses_context(self) -> bool:
        return True

    def required_timeframe_roles(self) -> list[str]:
        return ["trend", "setup", "entry"]

    def optional_timeframe_roles(self) -> list[str]:
        return ["confirmation"]

    def default_timeframe_mapping(self) -> dict[str, str]:
        return {"trend": "60m", "setup": "15m", "entry": "5m"}

    def default_params(self) -> dict[str, Any]:
        return {
            "trend_short_window": 20,
            "trend_long_window": 50,
            "setup_pullback_pct": 0.004,
            "entry_breakout_lookback": 5,
            "score_threshold": 0.7,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.04,
        }

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        validated = self.default_params() | params
        int_fields = ["trend_short_window", "trend_long_window", "entry_breakout_lookback"]
        float_fields = ["setup_pullback_pct", "score_threshold", "stop_loss_pct", "take_profit_pct"]

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

        if validated["trend_short_window"] >= validated["trend_long_window"]:
            raise ValueError("trend_short_window must be smaller than trend_long_window")
        if validated["score_threshold"] > 1.0:
            raise ValueError("score_threshold must be <= 1.0")
        return validated

    def warmup_candles(self, params: dict[str, Any]) -> int:
        p = self.validate_params(params)
        return max(p["trend_long_window"], p["entry_breakout_lookback"] + 2)

    def evaluate(self, candles, params):  # type: ignore[override]
        # This strategy requires multi-timeframe context.
        p = self.validate_params(params)
        latest = candles[-1] if candles else None
        return StrategyDecision(
            strategy_name=self.metadata().name,
            regime="unknown",
            entry_allowed=False,
            score=0.0,
            reject_reason="mtf_context_required",
            stop_loss=(latest.close * (1 - p["stop_loss_pct"])) if latest else None,
            take_profit=(latest.close * (1 + p["take_profit_pct"])) if latest else None,
            debug_info={"hint": "use evaluate_context"},
        )

    def evaluate_context(self, context: StrategyContext, params: dict[str, Any]) -> StrategyDecision:
        p = self.validate_params(params)
        trend = context.candles_by_role.get("trend", [])
        setup = context.candles_by_role.get("setup", [])
        entry = context.candles_by_role.get("entry", [])

        if len(trend) < p["trend_long_window"]:
            return StrategyDecision(
                strategy_name=self.metadata().name,
                regime="unknown",
                entry_allowed=False,
                score=0.0,
                reject_reason="insufficient_trend_history",
                stop_loss=None,
                take_profit=None,
                debug_info={"required": p["trend_long_window"], "trend_len": len(trend)},
            )
        if len(setup) < 10 or len(entry) < p["entry_breakout_lookback"] + 1:
            return StrategyDecision(
                strategy_name=self.metadata().name,
                regime="unknown",
                entry_allowed=False,
                score=0.0,
                reject_reason="insufficient_setup_or_entry_history",
                stop_loss=None,
                take_profit=None,
                debug_info={"setup_len": len(setup), "entry_len": len(entry)},
            )

        trend_short = mean(c.close for c in trend[-p["trend_short_window"] :])
        trend_long = mean(c.close for c in trend[-p["trend_long_window"] :])
        regime = self._regime(trend_short, trend_long)
        trend_ok = regime == "bullish"

        setup_latest = setup[-1]
        setup_prev_mean = mean(c.close for c in setup[-10:-1])
        setup_pullback = (setup_prev_mean - setup_latest.close) / max(setup_prev_mean, 1e-9)
        setup_ok = 0.0 <= setup_pullback <= p["setup_pullback_pct"] * 2

        entry_latest = entry[-1]
        entry_breakout = entry_latest.close > max(c.high for c in entry[-p["entry_breakout_lookback"] - 1 : -1])
        entry_ok = entry_breakout

        score = (0.5 if trend_ok else 0.0) + (0.25 if setup_ok else 0.0) + (0.25 if entry_ok else 0.0)
        allowed = score >= p["score_threshold"]

        reject_reason = None
        if not allowed:
            if not trend_ok:
                reject_reason = "trend_not_bullish"
            elif not setup_ok:
                reject_reason = "setup_not_ready"
            elif not entry_ok:
                reject_reason = "entry_breakout_missing"
            else:
                reject_reason = "score_below_threshold"

        stop_loss = entry_latest.close * (1 - p["stop_loss_pct"])
        take_profit = entry_latest.close * (1 + p["take_profit_pct"])
        return StrategyDecision(
            strategy_name=self.metadata().name,
            regime=regime,
            entry_allowed=allowed,
            score=round(score, 4),
            reject_reason=reject_reason,
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            debug_info={
                "timeframe_mapping": context.timeframe_mapping,
                "regime_by_role": {
                    "trend": regime,
                    "setup": "pullback_ok" if setup_ok else "pullback_fail",
                    "entry": "breakout_ok" if entry_ok else "breakout_fail",
                },
                "conditions": {
                    "trend_ok": trend_ok,
                    "setup_ok": setup_ok,
                    "entry_ok": entry_ok,
                },
                "as_of": context.as_of.isoformat(),
            },
        )

    def _regime(self, short_ma: float, long_ma: float) -> str:
        if short_ma > long_ma * 1.002:
            return "bullish"
        if short_ma < long_ma * 0.998:
            return "bearish"
        return "neutral"

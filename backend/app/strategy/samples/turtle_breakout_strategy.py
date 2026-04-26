from statistics import mean
from typing import Any

from app.models.candle import Candle
from app.strategy.base import BaseStrategy, StrategyDecision, StrategyMetadata


class TurtleBreakoutStrategy(BaseStrategy):
    """Long-only turtle-style breakout strategy (v1 skeleton)."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="turtle_breakout_v1",
            name="Turtle Breakout v1 (Long Only)",
            version="1.0.0",
            description=(
                "Long-only turtle breakout strategy: 20-bar close breakout entry, "
                "MA trend filter, ATR-based stop, and 10-bar channel exit."
            ),
        )

    def default_params(self) -> dict[str, Any]:
        return {
            "breakout_entry_length": 20,
            "breakout_exit_length": 10,
            "trend_ma_length": 200,
            "atr_length": 20,
            "atr_stop_multiple": 2.0,
            "risk_per_trade_pct": 0.02,
            "require_trend_filter": True,
            "use_close_breakout_only": True,
            "allow_reentry_after_stop": True,
            "min_atr_pct": None,
            "max_atr_pct": None,
        }

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        p = self.default_params() | params

        int_fields = ["breakout_entry_length", "breakout_exit_length", "trend_ma_length", "atr_length"]
        for field in int_fields:
            p[field] = int(p[field])
            if p[field] < 2:
                raise ValueError(f"{field} must be >= 2")

        float_fields = ["atr_stop_multiple", "risk_per_trade_pct"]
        for field in float_fields:
            p[field] = float(p[field])
            if p[field] <= 0:
                raise ValueError(f"{field} must be positive")

        if p["risk_per_trade_pct"] >= 1.0:
            raise ValueError("risk_per_trade_pct must be less than 1.0")

        p["require_trend_filter"] = bool(p["require_trend_filter"])
        p["use_close_breakout_only"] = bool(p["use_close_breakout_only"])
        p["allow_reentry_after_stop"] = bool(p["allow_reentry_after_stop"])

        for field in ("min_atr_pct", "max_atr_pct"):
            if p[field] is None:
                continue
            p[field] = float(p[field])
            if p[field] <= 0:
                raise ValueError(f"{field} must be positive when provided")

        if p["min_atr_pct"] is not None and p["max_atr_pct"] is not None:
            if p["min_atr_pct"] >= p["max_atr_pct"]:
                raise ValueError("min_atr_pct must be smaller than max_atr_pct")

        return p

    def warmup_candles(self, params: dict[str, Any]) -> int:
        p = self.validate_params(params)
        return max(
            p["breakout_entry_length"] + 1,
            p["breakout_exit_length"] + 1,
            p["trend_ma_length"],
            p["atr_length"] + 1,
        )

    def evaluate(self, candles: list[Candle], params: dict[str, Any]) -> StrategyDecision:
        p = self.validate_params(params)
        warmup = self.warmup_candles(p)

        if len(candles) < warmup:
            return StrategyDecision(
                strategy_name=self.metadata().name,
                strategy_version=self.metadata().version,
                regime="unknown",
                entry_allowed=False,
                score=0.0,
                reject_reason="insufficient_history",
                stop_loss=None,
                take_profit=None,
                reason_tags=["insufficient_history"],
                debug_info={"required": warmup, "current": len(candles)},
            )

        latest = candles[-1]
        prev_entry = candles[-(p["breakout_entry_length"] + 1) : -1]
        prev_exit = candles[-(p["breakout_exit_length"] + 1) : -1]

        breakout_entry_level = max(c.high for c in prev_entry)
        breakout_exit_level = min(c.low for c in prev_exit)

        if p["use_close_breakout_only"]:
            is_breakout = latest.close > breakout_entry_level
        else:
            is_breakout = latest.high > breakout_entry_level

        is_exit_breakdown = latest.close < breakout_exit_level

        trend_ma_value = mean(c.close for c in candles[-p["trend_ma_length"] :])
        is_above_trend_ma = latest.close > trend_ma_value

        atr_value = self._atr(candles, p["atr_length"])
        stop_distance = atr_value * p["atr_stop_multiple"]
        stop_loss = latest.close - stop_distance
        # Keep TP far away to let channel-exit/stop dominate under the current engine contract.
        take_profit = latest.close + stop_distance * 100.0

        atr_pct = atr_value / max(latest.close, 1e-9)
        atr_regime_ok = True
        if p["min_atr_pct"] is not None:
            atr_regime_ok = atr_regime_ok and atr_pct >= p["min_atr_pct"]
        if p["max_atr_pct"] is not None:
            atr_regime_ok = atr_regime_ok and atr_pct <= p["max_atr_pct"]

        trend_filter_ok = (not p["require_trend_filter"]) or is_above_trend_ma

        # Long-only: if exit channel breaks, push bearish regime so open positions can be closed.
        if is_exit_breakdown:
            regime = "bearish"
        elif is_above_trend_ma:
            regime = "bullish"
        else:
            regime = "neutral"

        score = 0.0
        score += 0.55 if is_breakout else 0.0
        score += 0.30 if trend_filter_ok else 0.0
        score += 0.15 if atr_regime_ok else 0.0

        reason_tags: list[str] = ["long_only"]
        reject_reason = None

        if is_exit_breakdown:
            reason_tags.append("exit_channel_breakdown")
            reject_reason = "below_exit_channel"
        elif not is_breakout:
            reason_tags.append("entry_breakout_not_met")
            reject_reason = "breakout_not_confirmed"
        elif not trend_filter_ok:
            reason_tags.append("trend_filter_failed")
            reject_reason = "trend_filter_blocked"
        elif not atr_regime_ok:
            reason_tags.append("atr_regime_failed")
            reject_reason = "atr_regime_blocked"

        entry_allowed = reject_reason is None

        stop_distance_pct = stop_distance / max(latest.close, 1e-9)
        theoretical_position_notional_multiple = (
            p["risk_per_trade_pct"] / max(stop_distance_pct, 1e-9)
            if stop_distance_pct > 0
            else None
        )

        debug_info = {
            "breakout_entry_level": round(breakout_entry_level, 6),
            "breakout_exit_level": round(breakout_exit_level, 6),
            "atr_value": round(atr_value, 8),
            "trend_ma_value": round(trend_ma_value, 6),
            "close_price": round(latest.close, 6),
            "is_breakout": is_breakout,
            "is_above_trend_ma": is_above_trend_ma,
            "is_exit_breakdown": is_exit_breakdown,
            "stop_distance": round(stop_distance, 8),
            "stop_distance_pct": round(stop_distance_pct, 8),
            "risk_metadata": {
                "risk_per_trade_pct": p["risk_per_trade_pct"],
                "theoretical_position_notional_multiple": round(theoretical_position_notional_multiple, 6)
                if theoretical_position_notional_multiple is not None
                else None,
                "note": "Sizing engine not implemented yet; metadata only.",
            },
            "params_used": p,
        }

        return StrategyDecision(
            strategy_name=self.metadata().name,
            strategy_version=self.metadata().version,
            regime=regime,
            entry_allowed=entry_allowed,
            score=round(score, 4),
            reject_reason=reject_reason,
            stop_loss=round(stop_loss, 6),
            take_profit=round(take_profit, 6),
            reason_tags=reason_tags,
            debug_info=debug_info,
        )

    def _atr(self, candles: list[Candle], period: int) -> float:
        if len(candles) < 2:
            return 0.0

        tr_values: list[float] = []
        for idx in range(1, len(candles)):
            current = candles[idx]
            prev = candles[idx - 1]
            tr = max(
                current.high - current.low,
                abs(current.high - prev.close),
                abs(current.low - prev.close),
            )
            tr_values.append(tr)

        if not tr_values:
            return 0.0

        window = tr_values[-period:]
        return float(mean(window))

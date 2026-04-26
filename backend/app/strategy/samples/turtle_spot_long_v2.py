from statistics import mean
from typing import Any

from app.strategy.base import BaseStrategy, StrategyContext, StrategyDecision, StrategyMetadata


class TurtleSpotLongV2Strategy(BaseStrategy):
    """Spot-long-only turtle style strategy with strict daily MA200 trend gate."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="turtle_spot_long_v2",
            name="Turtle Spot Long v2",
            version="2.0.0",
            description=(
                "Spot long-only turtle breakout strategy. Entry is allowed only when daily close is above daily MA200 "
                "and MA200 slope is rising. Under that gate, entry breakout/ATR stop/exit channel are evaluated."
            ),
            short_description=(
                "현물 롱 전용: 일봉 MA200 상승추세 필수 게이트 + 하위 타임프레임 돌파 진입"
            ),
            mode="multi_timeframe",
            required_roles=["trend", "entry"],
            optional_roles=["setup"],
            spot_long_only=True,
        )

    def uses_context(self) -> bool:
        return True

    def required_timeframe_roles(self) -> list[str]:
        return ["trend", "entry"]

    def optional_timeframe_roles(self) -> list[str]:
        return ["setup"]

    def default_timeframe_mapping(self) -> dict[str, str]:
        return {"trend": "1d", "setup": "240m", "entry": "60m"}

    def default_params(self) -> dict[str, Any]:
        return {
            "breakout_entry_length": 20,
            "breakout_exit_length": 10,
            "trend_ma_length": 200,
            "trend_slope_lookback": 20,
            "atr_length": 20,
            "atr_stop_multiple": 2.0,
            "require_trend_filter": True,
            "use_close_breakout_only": True,
            "setup_ma_length_short": 20,
            "setup_ma_length_long": 50,
            "require_setup_confirmation": False,
            "max_extension_atr": None,
            "volume_surge_ratio": 1.5,
            "require_volume_confirmation": False,
            "min_atr_pct": None,
            "max_atr_pct": None,
        }

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        p = self.default_params() | params

        int_fields = [
            "breakout_entry_length",
            "breakout_exit_length",
            "trend_ma_length",
            "trend_slope_lookback",
            "atr_length",
            "setup_ma_length_short",
            "setup_ma_length_long",
        ]
        for field in int_fields:
            p[field] = int(p[field])
            if p[field] < 2:
                raise ValueError(f"{field} must be >= 2")

        p["atr_stop_multiple"] = float(p["atr_stop_multiple"])
        if p["atr_stop_multiple"] <= 0:
            raise ValueError("atr_stop_multiple must be positive")

        p["volume_surge_ratio"] = float(p["volume_surge_ratio"])
        if p["volume_surge_ratio"] <= 0:
            raise ValueError("volume_surge_ratio must be positive")

        if p["setup_ma_length_short"] >= p["setup_ma_length_long"]:
            raise ValueError("setup_ma_length_short must be smaller than setup_ma_length_long")

        p["require_trend_filter"] = bool(p["require_trend_filter"])
        p["use_close_breakout_only"] = bool(p["use_close_breakout_only"])
        p["require_setup_confirmation"] = bool(p["require_setup_confirmation"])
        p["require_volume_confirmation"] = bool(p["require_volume_confirmation"])

        for field in ("max_extension_atr", "min_atr_pct", "max_atr_pct"):
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
            p["breakout_entry_length"] + 2,
            p["breakout_exit_length"] + 2,
            p["atr_length"] + 2,
            40,
        )

    def evaluate(self, candles, params):  # type: ignore[override]
        latest = candles[-1] if candles else None
        return StrategyDecision(
            strategy_name=self.metadata().name,
            strategy_version=self.metadata().version,
            regime="unknown",
            entry_allowed=False,
            score=0.0,
            reject_reason="mtf_context_required",
            stop_loss=(latest.close * 0.98) if latest else None,
            take_profit=(latest.close * 1.03) if latest else None,
            reason_tags=["mtf_context_required"],
            debug_info={},
        )

    def evaluate_context(self, context: StrategyContext, params: dict[str, Any]) -> StrategyDecision:
        p = self.validate_params(params)

        trend = context.candles_by_role.get("trend", [])
        entry = context.candles_by_role.get("entry", [])
        setup = context.candles_by_role.get("setup", [])

        trend_required = p["trend_ma_length"] + p["trend_slope_lookback"] + 2
        entry_required = max(p["breakout_entry_length"] + 2, p["breakout_exit_length"] + 2, p["atr_length"] + 2)

        if len(trend) < trend_required:
            return self._reject(
                reject_reason="insufficient_trend_history",
                regime="unknown",
                score=0.0,
                stop_loss=None,
                take_profit=None,
                reason_tags=["insufficient_trend_history"],
                debug_info={"trend_required": trend_required, "trend_len": len(trend), "timeframe_mapping": context.timeframe_mapping},
            )
        if len(entry) < entry_required:
            return self._reject(
                reject_reason="insufficient_entry_history",
                regime="unknown",
                score=0.0,
                stop_loss=None,
                take_profit=None,
                reason_tags=["insufficient_entry_history"],
                debug_info={"entry_required": entry_required, "entry_len": len(entry), "timeframe_mapping": context.timeframe_mapping},
            )

        trend_close = [c.close for c in trend]
        trend_ma_series = self._sma_series(trend_close, p["trend_ma_length"])
        daily_ma200 = trend_ma_series[-1]
        slope_lookback = min(p["trend_slope_lookback"], len(trend_ma_series) - 1)
        daily_ma200_prev = trend_ma_series[-(slope_lookback + 1)]
        daily_ma200_slope = daily_ma200 - daily_ma200_prev
        daily_close = trend[-1].close

        is_above_daily_ma200 = daily_close > daily_ma200
        is_daily_ma200_rising = daily_ma200_slope > 0

        trend_gate_ok = True
        if p["require_trend_filter"]:
            trend_gate_ok = is_above_daily_ma200 and is_daily_ma200_rising

        latest = entry[-1]
        prev_entry = entry[-(p["breakout_entry_length"] + 1) : -1]
        prev_exit = entry[-(p["breakout_exit_length"] + 1) : -1]

        breakout_entry_level = max(c.high for c in prev_entry)
        breakout_exit_level = min(c.low for c in prev_exit)

        is_breakout = latest.close > breakout_entry_level if p["use_close_breakout_only"] else latest.high > breakout_entry_level
        is_exit_breakdown = latest.close < breakout_exit_level

        atr_value = self._atr(entry, p["atr_length"])
        stop_distance = atr_value * p["atr_stop_multiple"]
        stop_loss = latest.close - stop_distance
        take_profit = latest.close + stop_distance * 100.0

        entry_ma20 = mean(c.close for c in entry[-20:]) if len(entry) >= 20 else mean(c.close for c in entry)
        extension_atr = (latest.close - entry_ma20) / max(atr_value, 1e-9)
        not_extended = True
        if p["max_extension_atr"] is not None:
            not_extended = extension_atr < p["max_extension_atr"]

        volume_ratio = latest.volume / max(mean(c.volume for c in entry[-20:]), 1e-9)
        volume_ok = volume_ratio >= p["volume_surge_ratio"]

        atr_pct = atr_value / max(latest.close, 1e-9)
        vol_regime_ok = True
        if p["min_atr_pct"] is not None:
            vol_regime_ok = vol_regime_ok and atr_pct >= p["min_atr_pct"]
        if p["max_atr_pct"] is not None:
            vol_regime_ok = vol_regime_ok and atr_pct <= p["max_atr_pct"]

        setup_ok = True
        setup_short = None
        setup_long = None
        if p["require_setup_confirmation"]:
            need_setup = max(p["setup_ma_length_short"], p["setup_ma_length_long"]) + 2
            if len(setup) < need_setup:
                setup_ok = False
            else:
                setup_short = mean(c.close for c in setup[-p["setup_ma_length_short"] :])
                setup_long = mean(c.close for c in setup[-p["setup_ma_length_long"] :])
                setup_ok = setup_short > setup_long and setup[-1].close > setup_long

        reason_tags: list[str] = ["spot_long_only"]
        reject_reason: str | None = None

        if is_exit_breakdown:
            reject_reason = "exit_channel_breakdown"
            reason_tags.append("exit_channel_breakdown")
        elif p["require_trend_filter"] and not is_above_daily_ma200:
            reject_reason = "daily_below_ma200"
            reason_tags.append("daily_below_ma200")
        elif p["require_trend_filter"] and not is_daily_ma200_rising:
            reject_reason = "daily_ma200_not_rising"
            reason_tags.append("daily_ma200_not_rising")
        elif not is_breakout:
            reject_reason = "breakout_not_confirmed"
            reason_tags.append("breakout_not_confirmed")
        elif p["require_setup_confirmation"] and not setup_ok:
            reject_reason = "setup_filter_failed"
            reason_tags.append("setup_filter_failed")
        elif p["require_volume_confirmation"] and not volume_ok:
            reject_reason = "volume_not_confirmed"
            reason_tags.append("volume_not_confirmed")
        elif not not_extended:
            reject_reason = "too_extended"
            reason_tags.append("too_extended")
        elif not vol_regime_ok:
            reject_reason = "volatility_regime_out_of_range"
            reason_tags.append("volatility_regime_out_of_range")

        entry_allowed = reject_reason is None and trend_gate_ok

        regime = "bearish" if is_exit_breakdown else ("bullish" if trend_gate_ok else "neutral")

        score = 0.0
        score += 0.55 if trend_gate_ok else 0.0
        score += 0.25 if is_breakout else 0.0
        score += 0.10 if setup_ok else 0.0
        score += 0.05 if volume_ok else 0.0
        score += 0.05 if not_extended and vol_regime_ok else 0.0

        debug_info = {
            "timeframe_mapping": context.timeframe_mapping,
            "daily_ma200": round(daily_ma200, 6),
            "daily_ma200_slope": round(daily_ma200_slope, 8),
            "daily_close": round(daily_close, 6),
            "is_above_daily_ma200": is_above_daily_ma200,
            "is_daily_ma200_rising": is_daily_ma200_rising,
            "breakout_entry_level": round(breakout_entry_level, 6),
            "breakout_exit_level": round(breakout_exit_level, 6),
            "is_breakout": is_breakout,
            "is_exit_breakdown": is_exit_breakdown,
            "atr_value": round(atr_value, 8),
            "atr_pct": round(atr_pct, 8),
            "stop_distance": round(stop_distance, 8),
            "extension_atr": round(extension_atr, 8),
            "volume_ratio": round(volume_ratio, 6),
            "setup_short_ma": round(setup_short, 6) if setup_short is not None else None,
            "setup_long_ma": round(setup_long, 6) if setup_long is not None else None,
            "setup_ok": setup_ok,
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

    def _reject(
        self,
        reject_reason: str,
        regime: str,
        score: float,
        stop_loss: float | None,
        take_profit: float | None,
        reason_tags: list[str],
        debug_info: dict[str, Any],
    ) -> StrategyDecision:
        return StrategyDecision(
            strategy_name=self.metadata().name,
            strategy_version=self.metadata().version,
            regime=regime,
            entry_allowed=False,
            score=score,
            reject_reason=reject_reason,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason_tags=reason_tags,
            debug_info=debug_info,
        )

    def _sma_series(self, values: list[float], window: int) -> list[float]:
        if len(values) < window:
            return []
        out: list[float] = []
        for idx in range(window - 1, len(values)):
            out.append(mean(values[idx - window + 1 : idx + 1]))
        return out

    def _atr(self, candles, period: int) -> float:
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
        return float(mean(tr_values[-period:]))

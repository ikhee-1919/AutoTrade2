from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from app.models.candle import Candle
from app.strategy.base import BaseStrategy, StrategyContext, StrategyDecision, StrategyMetadata


class MTFTrendPullbackV2Strategy(BaseStrategy):
    """Stricter MTF pullback continuation strategy with chase/cooldown controls."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="mtf_trend_pullback_v2",
            name="MTF Trend Pullback v2",
            version="2.0.0",
            description=(
                "1d trend gate + 60m pullback setup + 15m rebound trigger. "
                "Adds chase filter, ATR+swing stop, confirmed reversal exit, and stop-loss cooldown."
            ),
            short_description=(
                "1d 상승추세 위에서 60m 눌림과 15m rebound를 확인해 진입하는 MTF pullback continuation 전략"
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
        return {"trend": "1d", "setup": "60m", "entry": "15m"}

    def default_params(self) -> dict[str, Any]:
        return {
            "trend_ema_fast": 20,
            "trend_ema_slow": 50,
            "trend_slope_lookback": 10,
            "require_fast_above_slow": True,
            "require_slow_slope_positive": True,
            "setup_rsi_length": 14,
            "setup_rsi_min": 40.0,
            "setup_rsi_max": 60.0,
            "setup_pullback_near_pct": 1.2,
            "setup_swing_lookback": 8,
            "reject_lower_low": True,
            "entry_ema_length": 20,
            "entry_local_high_lookback": 5,
            "require_close_above_entry_ma": True,
            "require_local_high_break": True,
            "entry_volume_sma_length": 20,
            "entry_volume_multiplier": 1.1,
            "max_distance_from_60m_ema20_pct": 2.5,
            "max_atr_extension": 1.5,
            "atr_length": 14,
            "atr_stop_mult": 1.8,
            "swing_lookback": 8,
            "swing_buffer_atr": 0.2,
            "min_stop_pct": 0.8,
            "max_stop_pct": 3.5,
            "regime_reversal_confirm_bars": 2,
            "exit_on_60m_close_below_ema50": True,
            "exit_on_1d_bearish": True,
            "time_stop_hours": 72,
            "time_stop_min_profit_pct": 0.5,
            "after_stop_loss_hours": 12,
            "after_two_consecutive_stop_loss_hours": 48,
            "after_profit_exit_hours": 0,
            "enable_breakeven_after_1r": False,
            "enable_trailing_after_2r": False,
            "trailing_atr_mult": 1.5,
            "fee_buffer_pct": 0.0,
        }

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        p = self.default_params() | params

        int_fields = [
            "trend_ema_fast",
            "trend_ema_slow",
            "trend_slope_lookback",
            "setup_rsi_length",
            "setup_swing_lookback",
            "entry_ema_length",
            "entry_local_high_lookback",
            "entry_volume_sma_length",
            "atr_length",
            "swing_lookback",
            "regime_reversal_confirm_bars",
            "time_stop_hours",
            "after_stop_loss_hours",
            "after_two_consecutive_stop_loss_hours",
            "after_profit_exit_hours",
        ]
        for key in int_fields:
            p[key] = int(p[key])
            if key == "after_profit_exit_hours":
                if p[key] < 0:
                    raise ValueError(f"{key} must be >= 0")
                continue
            if p[key] <= 0:
                raise ValueError(f"{key} must be positive")

        float_fields = [
            "setup_rsi_min",
            "setup_rsi_max",
            "setup_pullback_near_pct",
            "entry_volume_multiplier",
            "max_distance_from_60m_ema20_pct",
            "max_atr_extension",
            "atr_stop_mult",
            "swing_buffer_atr",
            "min_stop_pct",
            "max_stop_pct",
            "time_stop_min_profit_pct",
            "trailing_atr_mult",
            "fee_buffer_pct",
        ]
        for key in float_fields:
            p[key] = float(p[key])
            if p[key] < 0:
                raise ValueError(f"{key} must be >= 0")

        bool_fields = [
            "require_fast_above_slow",
            "require_slow_slope_positive",
            "reject_lower_low",
            "require_close_above_entry_ma",
            "require_local_high_break",
            "exit_on_60m_close_below_ema50",
            "exit_on_1d_bearish",
            "enable_breakeven_after_1r",
            "enable_trailing_after_2r",
        ]
        for key in bool_fields:
            p[key] = bool(p[key])

        if p["trend_ema_fast"] >= p["trend_ema_slow"]:
            raise ValueError("trend_ema_fast must be smaller than trend_ema_slow")
        if p["setup_rsi_min"] >= p["setup_rsi_max"]:
            raise ValueError("setup_rsi_min must be smaller than setup_rsi_max")
        if p["min_stop_pct"] >= p["max_stop_pct"]:
            raise ValueError("min_stop_pct must be smaller than max_stop_pct")
        if p["entry_volume_multiplier"] < 1.0:
            raise ValueError("entry_volume_multiplier should be >= 1.0")
        if p["setup_pullback_near_pct"] > 10:
            raise ValueError("setup_pullback_near_pct is too large")
        return p

    def warmup_candles(self, params: dict[str, Any]) -> int:
        p = self.validate_params(params)
        return max(
            p["trend_ema_slow"] + p["trend_slope_lookback"] + 5,
            p["setup_swing_lookback"] * 2 + p["setup_rsi_length"] + 5,
            p["entry_ema_length"] + p["entry_volume_sma_length"] + p["atr_length"] + 10,
            p["entry_local_high_lookback"] + p["swing_lookback"] + 5,
            80,
        )

    def evaluate(self, candles: list[Candle], params: dict[str, Any]) -> StrategyDecision:
        latest = candles[-1] if candles else None
        return StrategyDecision(
            strategy_name=self.metadata().name,
            strategy_version=self.metadata().version,
            regime="unknown",
            entry_allowed=False,
            score=0.0,
            reject_reason="mtf_context_required",
            stop_loss=(latest.close * 0.985) if latest else None,
            take_profit=(latest.close * 1.03) if latest else None,
            reason_tags=["mtf_context_required"],
            debug_info={},
        )

    def evaluate_context(self, context: StrategyContext, params: dict[str, Any]) -> StrategyDecision:
        p = self.validate_params(params)
        trend = context.candles_by_role.get("trend", [])
        setup = context.candles_by_role.get("setup", [])
        entry = context.candles_by_role.get("entry", [])
        runtime_state = context.runtime_state or {}

        min_trend = p["trend_ema_slow"] + p["trend_slope_lookback"] + 2
        min_setup = max(60, p["setup_swing_lookback"] * 2 + p["setup_rsi_length"] + 2)
        min_entry = max(
            60,
            p["entry_ema_length"] + 2,
            p["entry_volume_sma_length"] + 2,
            p["atr_length"] + 2,
            p["entry_local_high_lookback"] + 2,
            p["swing_lookback"] + 2,
        )
        if len(trend) < min_trend:
            return self._reject("insufficient_trend_history", context, runtime_state)
        if len(setup) < min_setup:
            return self._reject("insufficient_setup_history", context, runtime_state)
        if len(entry) < min_entry:
            return self._reject("insufficient_entry_history", context, runtime_state)

        daily_ema20 = self._ema(trend, p["trend_ema_fast"])
        daily_ema50 = self._ema(trend, p["trend_ema_slow"])
        daily_close = trend[-1].close
        daily_fast_above_slow = daily_ema20[-1] > daily_ema50[-1]
        daily_above_slow = daily_close > daily_ema50[-1]
        slope_lookback = min(p["trend_slope_lookback"], len(daily_ema50) - 1)
        daily_slow_slope = daily_ema50[-1] - daily_ema50[-(slope_lookback + 1)]
        slow_slope_ok = daily_slow_slope >= 0
        is_daily_bearish = (daily_close < daily_ema50[-1]) or (daily_ema20[-1] < daily_ema50[-1])

        trend_ok = daily_above_slow
        if p["require_fast_above_slow"]:
            trend_ok = trend_ok and daily_fast_above_slow
        if p["require_slow_slope_positive"]:
            trend_ok = trend_ok and slow_slope_ok

        setup_ema20 = self._ema(setup, 20)
        setup_ema50 = self._ema(setup, 50)
        setup_close = setup[-1].close
        setup_above_ema50 = setup_close > setup_ema50[-1]
        near_ema20 = abs(setup_close - setup_ema20[-1]) / max(setup_close, 1e-9) * 100 <= p["setup_pullback_near_pct"]
        near_ema50 = abs(setup_close - setup_ema50[-1]) / max(setup_close, 1e-9) * 100 <= p["setup_pullback_near_pct"]
        setup_pullback_ok = setup_above_ema50 and (near_ema20 or near_ema50)

        setup_rsi = self._rsi(setup, p["setup_rsi_length"])
        setup_rsi_ok = p["setup_rsi_min"] <= setup_rsi[-1] <= p["setup_rsi_max"]

        setup_recent_low = min(c.low for c in setup[-p["setup_swing_lookback"] :])
        setup_prev_low = min(c.low for c in setup[-(p["setup_swing_lookback"] * 2) : -p["setup_swing_lookback"]])
        lower_low_blocked = p["reject_lower_low"] and setup_recent_low <= setup_prev_low

        entry_ema20 = self._ema(entry, p["entry_ema_length"])
        prev_close = entry[-2].close
        prev_ema = entry_ema20[-2]
        reclaim_trigger = prev_close <= prev_ema and entry[-1].close > entry_ema20[-1]
        local_high = max(c.high for c in entry[-(p["entry_local_high_lookback"] + 1) : -1])
        local_high_break = entry[-1].close > local_high

        trigger_candidates: list[bool] = []
        if p["require_close_above_entry_ma"]:
            trigger_candidates.append(reclaim_trigger)
        if p["require_local_high_break"]:
            trigger_candidates.append(local_high_break)
        trigger_ok = any(trigger_candidates) if trigger_candidates else True

        vol_sma = mean(c.volume for c in entry[-p["entry_volume_sma_length"] :])
        volume_ok = entry[-1].volume > vol_sma * p["entry_volume_multiplier"]

        atr_values = self._atr(entry, p["atr_length"])
        atr_15m = atr_values[-1]
        chase_distance_pct = ((entry[-1].close - setup_ema20[-1]) / max(setup_ema20[-1], 1e-9)) * 100
        chase_ok = (
            chase_distance_pct <= p["max_distance_from_60m_ema20_pct"]
            and entry[-1].close <= entry_ema20[-1] + atr_15m * p["max_atr_extension"]
        )

        recent_15m_swing_low = min(c.low for c in entry[-p["swing_lookback"] :])
        stop_from_swing = recent_15m_swing_low - p["swing_buffer_atr"] * atr_15m
        stop_from_atr = entry[-1].close - p["atr_stop_mult"] * atr_15m
        stop_loss = min(stop_from_swing, stop_from_atr)
        stop_distance_pct = ((entry[-1].close - stop_loss) / max(entry[-1].close, 1e-9)) * 100

        cooldown_state = self._cooldown_state(context.as_of, runtime_state, p)
        in_cooldown = cooldown_state["in_cooldown"]

        position_state = runtime_state.get("position") if isinstance(runtime_state.get("position"), dict) else None
        exit_signal_reason: str | None = None
        if position_state:
            if p["exit_on_1d_bearish"] and is_daily_bearish:
                exit_signal_reason = "daily_trend_bearish"
            elif p["exit_on_60m_close_below_ema50"] and self._below_ema_consecutive(
                setup,
                setup_ema50,
                p["regime_reversal_confirm_bars"],
            ):
                exit_signal_reason = "regime_reversal_confirmed"
            else:
                entry_price = float(position_state.get("entry_price", entry[-1].close))
                held_hours = max(
                    0.0,
                    (context.as_of - datetime.fromisoformat(str(position_state.get("entry_time")))).total_seconds() / 3600,
                )
                unrealized_pnl_pct = ((entry[-1].close - entry_price) / max(entry_price, 1e-9)) * 100
                if held_hours >= p["time_stop_hours"] and unrealized_pnl_pct < p["time_stop_min_profit_pct"]:
                    exit_signal_reason = "time_stop"

        reject_reason: str | None = None
        reason_tags: list[str] = []
        if is_daily_bearish:
            reject_reason = "1d_trend_bearish"
        elif not trend_ok:
            reject_reason = "trend_not_bullish"
        elif not setup_pullback_ok:
            reject_reason = "setup_not_pullback"
        elif not setup_rsi_ok:
            reject_reason = "rsi_out_of_range"
        elif lower_low_blocked:
            reject_reason = "setup_not_pullback"
        elif not trigger_ok:
            reject_reason = "no_reclaim_trigger"
        elif not volume_ok:
            reject_reason = "volume_not_confirmed"
        elif not chase_ok:
            reject_reason = "chase_filter_blocked"
        elif stop_distance_pct < p["min_stop_pct"]:
            reject_reason = "stop_too_tight"
        elif stop_distance_pct > p["max_stop_pct"]:
            reject_reason = "risk_too_wide"
        elif in_cooldown:
            reject_reason = "cooldown_after_stop"

        score = 0.0
        score += 0.28 if trend_ok else 0.0
        score += 0.22 if setup_pullback_ok else 0.0
        score += 0.2 if setup_rsi_ok else 0.0
        score += 0.18 if trigger_ok else 0.0
        score += 0.07 if volume_ok else 0.0
        score += 0.05 if chase_ok else 0.0

        entry_allowed = reject_reason is None
        if reject_reason:
            reason_tags.append(reject_reason)

        regime = "bullish"
        if is_daily_bearish:
            regime = "bearish"
        elif exit_signal_reason:
            regime = "bearish"
        elif not trend_ok:
            regime = "neutral"

        take_profit = entry[-1].close + atr_15m * 6.0
        debug_info = {
            "timeframe_mapping": context.timeframe_mapping,
            "regime_by_role": {
                "trend": "bullish" if trend_ok else "not_bullish",
                "setup": "pullback_ok" if setup_pullback_ok else "pullback_fail",
                "entry": "trigger_ok" if trigger_ok else "trigger_fail",
            },
            "daily_close": round(daily_close, 6),
            "daily_ema20": round(daily_ema20[-1], 6),
            "daily_ema50": round(daily_ema50[-1], 6),
            "daily_ema50_slope": round(daily_slow_slope, 8),
            "is_daily_bullish": trend_ok,
            "setup_close": round(setup_close, 6),
            "setup_ema50": round(setup_ema50[-1], 6),
            "setup_rsi": round(setup_rsi[-1], 4),
            "entry_close": round(entry[-1].close, 6),
            "entry_ema20": round(entry_ema20[-1], 6),
            "entry_prev_local_high": round(local_high, 6),
            "entry_volume": round(entry[-1].volume, 6),
            "entry_volume_sma20": round(vol_sma, 6),
            "atr_15m": round(atr_15m, 8),
            "recent_15m_swing_low": round(recent_15m_swing_low, 6),
            "stop_distance_pct": round(stop_distance_pct, 6),
            "chase_distance_pct": round(chase_distance_pct, 6),
            "cooldown_state": cooldown_state,
            "setup_recent_low": round(setup_recent_low, 6),
            "setup_previous_low": round(setup_prev_low, 6),
            "reclaim_trigger": reclaim_trigger,
            "local_high_break": local_high_break,
            "volume_ok": volume_ok,
            "chase_ok": chase_ok,
            "exit_signal_reason": exit_signal_reason,
            "optional_features": {
                "enable_breakeven_after_1r": p["enable_breakeven_after_1r"],
                "enable_trailing_after_2r": p["enable_trailing_after_2r"],
                "note": "breakeven/trailing stop is reserved for a future engine extension.",
            },
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

    def _reject(self, reason: str, context: StrategyContext, runtime_state: dict[str, Any]) -> StrategyDecision:
        return StrategyDecision(
            strategy_name=self.metadata().name,
            strategy_version=self.metadata().version,
            regime="unknown",
            entry_allowed=False,
            score=0.0,
            reject_reason=reason,
            stop_loss=None,
            take_profit=None,
            reason_tags=[reason],
            debug_info={
                "timeframe_mapping": context.timeframe_mapping,
                "runtime_state": runtime_state,
            },
        )

    def _cooldown_state(
        self,
        as_of: datetime,
        runtime_state: dict[str, Any],
        p: dict[str, Any],
    ) -> dict[str, Any]:
        last_exit_reason = runtime_state.get("last_exit_reason")
        last_exit_time_raw = runtime_state.get("last_exit_time")
        consecutive_stop_losses = int(runtime_state.get("consecutive_stop_losses") or 0)
        last_exit_was_profit = bool(runtime_state.get("last_exit_was_profit"))
        cooldown_hours = 0
        if last_exit_reason == "stop_loss":
            cooldown_hours = (
                p["after_two_consecutive_stop_loss_hours"]
                if consecutive_stop_losses >= 2
                else p["after_stop_loss_hours"]
            )
        elif last_exit_was_profit:
            cooldown_hours = p["after_profit_exit_hours"]

        cooldown_until = None
        in_cooldown = False
        if last_exit_time_raw and cooldown_hours > 0:
            try:
                last_exit_time = datetime.fromisoformat(str(last_exit_time_raw))
                cooldown_until = last_exit_time + timedelta(hours=cooldown_hours)
                in_cooldown = as_of < cooldown_until
            except ValueError:
                cooldown_until = None
                in_cooldown = False

        return {
            "last_exit_reason": last_exit_reason,
            "last_exit_time": last_exit_time_raw,
            "consecutive_stop_losses": consecutive_stop_losses,
            "cooldown_hours": cooldown_hours,
            "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
            "in_cooldown": in_cooldown,
        }

    def _below_ema_consecutive(self, candles: list[Candle], ema: list[float], bars: int) -> bool:
        bars = max(1, bars)
        if len(candles) < bars or len(ema) < bars:
            return False
        for idx in range(1, bars + 1):
            if candles[-idx].close >= ema[-idx]:
                return False
        return True

    def _ema(self, candles: list[Candle], length: int) -> list[float]:
        closes = [c.close for c in candles]
        if not closes:
            return []
        k = 2 / (length + 1)
        out: list[float] = []
        ema = closes[0]
        for close in closes:
            ema = close * k + ema * (1 - k)
            out.append(ema)
        return out

    def _rsi(self, candles: list[Candle], period: int) -> list[float]:
        closes = [c.close for c in candles]
        if len(closes) < period + 1:
            return [50.0 for _ in closes]
        gains = [0.0]
        losses = [0.0]
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))
        rsi_values = [50.0] * len(closes)
        avg_gain = mean(gains[1 : period + 1])
        avg_loss = mean(losses[1 : period + 1])
        for i in range(period + 1, len(closes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            rs = avg_gain / max(avg_loss, 1e-9)
            rsi_values[i] = 100 - (100 / (1 + rs))
        return rsi_values

    def _atr(self, candles: list[Candle], period: int) -> list[float]:
        tr: list[float] = [candles[0].high - candles[0].low]
        for i in range(1, len(candles)):
            c = candles[i]
            p = candles[i - 1]
            tr.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
        atr_values = [tr[0]]
        alpha = 1 / period
        atr = tr[0]
        for value in tr[1:]:
            atr = (1 - alpha) * atr + alpha * value
            atr_values.append(atr)
        return atr_values

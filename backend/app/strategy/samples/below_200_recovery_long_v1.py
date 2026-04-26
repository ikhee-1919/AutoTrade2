from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from app.models.candle import Candle
from app.services.regime_classifier import RegimeClassifier
from app.strategy.base import BaseStrategy, StrategyContext, StrategyDecision, StrategyMetadata


class Below200RecoveryLongV1Strategy(BaseStrategy):
    """Spot long-only strategy for below_200_recovery regime."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="below_200_recovery_long_v1",
            name="Below 200 Recovery Long v1",
            version="1.0.0",
            description=(
                "Spot long-only recovery strategy. "
                "Trades only in below_200_recovery regime using 4h structure, 1h setup, and 15m trigger."
            ),
            short_description=(
                "200일선 아래 회복 구간에서 4H higher low + 1H 눌림 + 15M 재상승 확인 후 진입하는 현물 롱 전략"
            ),
            mode="multi_timeframe",
            required_roles=["regime", "trend", "setup", "trigger"],
            optional_roles=["execution"],
            spot_long_only=True,
        )

    def uses_context(self) -> bool:
        return True

    def required_timeframe_roles(self) -> list[str]:
        return ["regime", "trend", "setup", "trigger"]

    def optional_timeframe_roles(self) -> list[str]:
        return ["execution"]

    def default_timeframe_mapping(self) -> dict[str, str]:
        return {
            "regime": "1d",
            "trend": "4h",
            "setup": "1h",
            "trigger": "15m",
            "execution": "5m",
        }

    def default_params(self) -> dict[str, Any]:
        return {
            "entry_score_threshold": 70.0,
            "regime_sma_length": 200,
            "regime_ema_fast": 20,
            "regime_ema_mid": 50,
            "max_distance_below_sma200_pct": 12.0,
            "require_daily_ema20_recovery": True,
            "trend_ema_fast": 20,
            "trend_ema_slow": 50,
            "require_higher_low": True,
            "require_4h_close_above_ema20": True,
            "setup_rsi_length": 14,
            "setup_rsi_min": 42.0,
            "setup_rsi_max": 62.0,
            "require_pullback_near_ema": True,
            "setup_pullback_near_pct": 1.2,
            "reject_lower_low": True,
            "trigger_ema_length": 20,
            "require_close_above_trigger_ema": True,
            "require_local_high_break": True,
            "trigger_local_high_lookback": 5,
            "trigger_volume_sma_length": 20,
            "trigger_volume_multiplier": 1.1,
            "execution_ema_length": 20,
            "execution_atr_length": 14,
            "max_execution_spike_pct": 1.5,
            "max_execution_atr_extension": 1.5,
            "atr_length": 14,
            "atr_stop_mult": 1.6,
            "swing_lookback": 8,
            "swing_buffer_atr": 0.2,
            "min_stop_pct": 0.7,
            "max_stop_pct": 3.0,
            "structure_break_confirm_bars": 2,
            "time_stop_hours": 48,
            "time_stop_min_profit_pct": 0.5,
            "after_stop_loss_hours": 12,
            "after_two_consecutive_stop_loss_hours": 36,
            "after_profit_exit_hours": 0,
        }

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        p = self.default_params() | params

        positive_int_fields = [
            "regime_sma_length",
            "regime_ema_fast",
            "regime_ema_mid",
            "trend_ema_fast",
            "trend_ema_slow",
            "setup_rsi_length",
            "trigger_ema_length",
            "trigger_local_high_lookback",
            "trigger_volume_sma_length",
            "execution_ema_length",
            "execution_atr_length",
            "atr_length",
            "swing_lookback",
            "structure_break_confirm_bars",
            "time_stop_hours",
        ]
        nonnegative_int_fields = [
            "after_stop_loss_hours",
            "after_two_consecutive_stop_loss_hours",
            "after_profit_exit_hours",
        ]
        float_fields = [
            "entry_score_threshold",
            "max_distance_below_sma200_pct",
            "setup_rsi_min",
            "setup_rsi_max",
            "setup_pullback_near_pct",
            "trigger_volume_multiplier",
            "max_execution_spike_pct",
            "max_execution_atr_extension",
            "atr_stop_mult",
            "swing_buffer_atr",
            "min_stop_pct",
            "max_stop_pct",
            "time_stop_min_profit_pct",
        ]

        for key in positive_int_fields:
            p[key] = int(p[key])
            if p[key] <= 0:
                raise ValueError(f"{key} must be positive")

        for key in nonnegative_int_fields:
            p[key] = int(p[key])
            if p[key] < 0:
                raise ValueError(f"{key} must be >= 0")

        for key in float_fields:
            p[key] = float(p[key])
            if p[key] < 0:
                raise ValueError(f"{key} must be >= 0")

        bool_fields = [
            "require_daily_ema20_recovery",
            "require_higher_low",
            "require_4h_close_above_ema20",
            "require_pullback_near_ema",
            "reject_lower_low",
            "require_close_above_trigger_ema",
            "require_local_high_break",
        ]
        for key in bool_fields:
            p[key] = bool(p[key])

        if p["setup_rsi_min"] >= p["setup_rsi_max"]:
            raise ValueError("setup_rsi_min must be smaller than setup_rsi_max")
        if p["min_stop_pct"] >= p["max_stop_pct"]:
            raise ValueError("min_stop_pct must be smaller than max_stop_pct")
        if p["trend_ema_fast"] >= p["trend_ema_slow"]:
            raise ValueError("trend_ema_fast must be smaller than trend_ema_slow")
        if p["regime_ema_fast"] >= p["regime_ema_mid"]:
            raise ValueError("regime_ema_fast must be smaller than regime_ema_mid")
        if not (0 <= p["entry_score_threshold"] <= 100):
            raise ValueError("entry_score_threshold must be in [0, 100]")

        return p

    def warmup_candles(self, params: dict[str, Any]) -> int:
        p = self.validate_params(params)
        return max(
            p["regime_sma_length"] + 30,
            p["trend_ema_slow"] + p["swing_lookback"] * 2 + 10,
            p["setup_rsi_length"] + p["swing_lookback"] * 2 + 10,
            p["trigger_ema_length"] + p["trigger_volume_sma_length"] + p["atr_length"] + 10,
            p["execution_ema_length"] + p["execution_atr_length"] + 10,
            240,
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
            take_profit=(latest.close * 1.02) if latest else None,
            reason_tags=["mtf_context_required"],
            debug_info={},
        )

    def evaluate_context(self, context: StrategyContext, params: dict[str, Any]) -> StrategyDecision:
        p = self.validate_params(params)
        regime = context.candles_by_role.get("regime", [])
        trend = context.candles_by_role.get("trend", [])
        setup = context.candles_by_role.get("setup", [])
        trigger = context.candles_by_role.get("trigger", [])
        execution = context.candles_by_role.get("execution", [])
        runtime_state = context.runtime_state or {}

        if len(regime) < p["regime_sma_length"] + 2:
            return self._reject("insufficient_regime_history", context, runtime_state)
        if len(trend) < p["trend_ema_slow"] + p["swing_lookback"] * 2 + 2:
            return self._reject("insufficient_trend_history", context, runtime_state)
        if len(setup) < max(p["setup_rsi_length"] + 2, p["swing_lookback"] * 2 + 2):
            return self._reject("insufficient_setup_history", context, runtime_state)
        if len(trigger) < max(
            p["trigger_ema_length"] + 2,
            p["trigger_local_high_lookback"] + 2,
            p["trigger_volume_sma_length"] + 2,
            p["atr_length"] + 2,
        ):
            return self._reject("insufficient_trigger_history", context, runtime_state)

        regime_classifier = RegimeClassifier()
        regime_point = regime_classifier.classify_last(
            regime,
            sma_length=p["regime_sma_length"],
            ema_fast=p["regime_ema_fast"],
            ema_mid=p["regime_ema_mid"],
            ema_slow=p["regime_sma_length"],
            slope_short_lookback=5,
            slope_long_lookback=20,
        )
        if regime_point is None or not regime_point.has_sufficient_history:
            return self._reject("insufficient_regime_history", context, runtime_state)

        daily_close = float(regime_point.close)
        daily_sma200 = float(regime_point.sma200 or 0.0)
        daily_ema20 = float(regime_point.ema20 or daily_close)
        daily_ema20_prev = self._ema(regime, p["regime_ema_fast"])[-2]
        distance_from_sma200_pct = ((daily_sma200 - daily_close) / max(daily_sma200, 1e-9)) * 100
        is_recovery_regime = regime_point.regime == "below_200_recovery"
        too_far_below = distance_from_sma200_pct > p["max_distance_below_sma200_pct"]
        daily_recovery_ok = (daily_ema20 >= daily_ema20_prev and daily_close >= daily_ema20)

        trend_ema20 = self._ema(trend, p["trend_ema_fast"])
        trend_ema50 = self._ema(trend, p["trend_ema_slow"])
        trend_close = trend[-1].close
        trend_higher_low = self._higher_low(trend, p["swing_lookback"])
        trend_close_above_ema20 = trend_close > trend_ema20[-1]
        trend_recovery_ready = (
            (trend_higher_low or not p["require_higher_low"])
            and (trend_close_above_ema20 or not p["require_4h_close_above_ema20"])
            and trend_ema20[-1] >= trend_ema50[-1] * 0.98
        )

        setup_ema20 = self._ema(setup, 20)
        setup_ema50 = self._ema(setup, 50)
        setup_close = setup[-1].close
        near_ema = (
            abs(setup_close - setup_ema20[-1]) / max(setup_close, 1e-9) * 100 <= p["setup_pullback_near_pct"]
            or abs(setup_close - setup_ema50[-1]) / max(setup_close, 1e-9) * 100 <= p["setup_pullback_near_pct"]
        )
        setup_rsi = self._rsi(setup, p["setup_rsi_length"])[-1]
        setup_rsi_ok = p["setup_rsi_min"] <= setup_rsi <= p["setup_rsi_max"]
        setup_recent_low = min(c.low for c in setup[-p["swing_lookback"] :])
        setup_prev_low = min(c.low for c in setup[-(p["swing_lookback"] * 2) : -p["swing_lookback"]])
        setup_lower_low_break = setup_recent_low <= setup_prev_low
        setup_ok = (
            (near_ema or not p["require_pullback_near_ema"])
            and setup_rsi_ok
            and not (p["reject_lower_low"] and setup_lower_low_break)
        )

        trigger_ema20 = self._ema(trigger, p["trigger_ema_length"])
        trigger_close = trigger[-1].close
        trigger_reclaim = trigger_close > trigger_ema20[-1]
        prev_local_high = max(c.high for c in trigger[-(p["trigger_local_high_lookback"] + 1) : -1])
        local_high_break = trigger_close > prev_local_high
        trigger_vol_sma = mean(c.volume for c in trigger[-p["trigger_volume_sma_length"] :])
        trigger_volume_ok = trigger[-1].volume >= trigger_vol_sma * p["trigger_volume_multiplier"]
        trigger_ok = (
            (trigger_reclaim or not p["require_close_above_trigger_ema"])
            and (local_high_break or not p["require_local_high_break"])
            and trigger_volume_ok
        )

        execution_ok = True
        execution_info = {"available": False}
        if len(execution) >= max(20, p["execution_ema_length"] + p["execution_atr_length"] + 2):
            exec_ema = self._ema(execution, p["execution_ema_length"])
            exec_atr = self._atr(execution, p["execution_atr_length"])
            spike_pct = ((execution[-1].close - execution[-2].close) / max(execution[-2].close, 1e-9)) * 100
            extension = (execution[-1].close - exec_ema[-1]) / max(exec_atr, 1e-9)
            execution_ok = spike_pct <= p["max_execution_spike_pct"] and extension <= p["max_execution_atr_extension"]
            execution_info = {
                "available": True,
                "spike_pct": round(spike_pct, 6),
                "extension_atr": round(extension, 6),
            }

        trigger_atr = self._atr(trigger, p["atr_length"])
        recent_swing_low = min(c.low for c in trigger[-p["swing_lookback"] :])
        stop_from_swing = recent_swing_low - p["swing_buffer_atr"] * trigger_atr
        stop_from_atr = trigger_close - p["atr_stop_mult"] * trigger_atr
        stop_loss = min(stop_from_swing, stop_from_atr)
        stop_distance_pct = ((trigger_close - stop_loss) / max(trigger_close, 1e-9)) * 100

        cooldown_state = self._cooldown_state(context.as_of, runtime_state, p)
        in_cooldown = cooldown_state["in_cooldown"]

        position_state = runtime_state.get("position") if isinstance(runtime_state.get("position"), dict) else None
        exit_signal_reason: str | None = None
        if position_state:
            if regime_point.regime == "below_200_downtrend":
                exit_signal_reason = "daily_recovery_failed"
            elif self._below_ema_consecutive(trend, trend_ema20, p["structure_break_confirm_bars"]):
                exit_signal_reason = "recovery_structure_failed"
            else:
                entry_price = float(position_state.get("entry_price", trigger_close))
                held_hours = max(
                    0.0,
                    (context.as_of - datetime.fromisoformat(str(position_state.get("entry_time")))).total_seconds()
                    / 3600,
                )
                unrealized_pnl_pct = ((trigger_close - entry_price) / max(entry_price, 1e-9)) * 100
                if held_hours >= p["time_stop_hours"] and unrealized_pnl_pct < p["time_stop_min_profit_pct"]:
                    exit_signal_reason = "time_stop"

        reject_reason: str | None = None
        if not is_recovery_regime:
            reject_reason = "not_below_200_recovery"
        elif too_far_below:
            reject_reason = "too_far_below_sma200"
        elif p["require_daily_ema20_recovery"] and not daily_recovery_ok:
            reject_reason = "daily_recovery_not_confirmed"
        elif p["require_higher_low"] and not trend_higher_low:
            reject_reason = "trend_higher_low_missing"
        elif p["require_4h_close_above_ema20"] and not trend_close_above_ema20:
            reject_reason = "trend_below_ema20"
        elif not trend_recovery_ready:
            reject_reason = "recovery_structure_not_ready"
        elif p["require_pullback_near_ema"] and not near_ema:
            reject_reason = "setup_not_pullback"
        elif not setup_rsi_ok:
            reject_reason = "setup_rsi_out_of_range"
        elif p["reject_lower_low"] and setup_lower_low_break:
            reject_reason = "setup_lower_low_break"
        elif p["require_close_above_trigger_ema"] and not trigger_reclaim:
            reject_reason = "no_trigger_reclaim"
        elif p["require_local_high_break"] and not local_high_break:
            reject_reason = "no_local_high_break"
        elif not trigger_volume_ok:
            reject_reason = "trigger_volume_not_confirmed"
        elif not execution_ok:
            reject_reason = "execution_overextended"
        elif stop_distance_pct < p["min_stop_pct"]:
            reject_reason = "stop_too_tight"
        elif stop_distance_pct > p["max_stop_pct"]:
            reject_reason = "risk_too_wide"
        elif in_cooldown:
            reject_reason = "cooldown_after_stop"

        score_breakdown = {
            "regime": 30.0 if (is_recovery_regime and not too_far_below and (daily_recovery_ok or not p["require_daily_ema20_recovery"])) else 0.0,
            "trend": 25.0 if trend_recovery_ready else 0.0,
            "setup": 20.0 if setup_ok else 0.0,
            "trigger": 20.0 if trigger_ok else 0.0,
            "execution": 5.0 if execution_ok else 0.0,
        }
        score = sum(score_breakdown.values())
        if reject_reason is None and score < p["entry_score_threshold"]:
            reject_reason = "score_below_threshold"

        entry_allowed = reject_reason is None
        regime_label = "bearish" if exit_signal_reason else regime_point.regime

        debug_info = {
            "timeframe_mapping": context.timeframe_mapping,
            "score_breakdown": score_breakdown,
            "daily_close": round(daily_close, 6),
            "daily_sma200": round(daily_sma200, 6),
            "daily_ema20": round(daily_ema20, 6),
            "distance_from_sma200_pct": round(distance_from_sma200_pct, 6),
            "is_recovery_regime": is_recovery_regime,
            "daily_recovery_ok": daily_recovery_ok,
            "trend_close": round(trend_close, 6),
            "trend_ema20": round(trend_ema20[-1], 6),
            "trend_ema50": round(trend_ema50[-1], 6),
            "trend_higher_low": trend_higher_low,
            "setup_close": round(setup_close, 6),
            "setup_ema20": round(setup_ema20[-1], 6),
            "setup_ema50": round(setup_ema50[-1], 6),
            "setup_rsi": round(setup_rsi, 6),
            "setup_lower_low_break": setup_lower_low_break,
            "trigger_close": round(trigger_close, 6),
            "trigger_ema20": round(trigger_ema20[-1], 6),
            "prev_local_high": round(prev_local_high, 6),
            "trigger_volume": round(trigger[-1].volume, 6),
            "trigger_volume_sma": round(trigger_vol_sma, 6),
            "execution": execution_info,
            "atr_value": round(trigger_atr, 8),
            "stop_loss": round(stop_loss, 6),
            "stop_distance_pct": round(stop_distance_pct, 6),
            "cooldown_state": cooldown_state,
            "exit_signal_reason": exit_signal_reason,
        }

        return StrategyDecision(
            strategy_name=self.metadata().name,
            strategy_version=self.metadata().version,
            regime=regime_label,
            entry_allowed=entry_allowed,
            score=round(score, 4),
            reject_reason=reject_reason,
            stop_loss=round(stop_loss, 6),
            take_profit=round(trigger_close + trigger_atr * 4.0, 6),
            reason_tags=[reject_reason] if reject_reason else ["entry_allowed"],
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
            debug_info={"timeframe_mapping": context.timeframe_mapping, "runtime_state": runtime_state},
        )

    def _cooldown_state(self, as_of: datetime, runtime_state: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
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
                pass

        return {
            "last_exit_reason": last_exit_reason,
            "last_exit_time": last_exit_time_raw,
            "consecutive_stop_losses": consecutive_stop_losses,
            "cooldown_hours": cooldown_hours,
            "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
            "in_cooldown": in_cooldown,
        }

    def _higher_low(self, candles: list[Candle], lookback: int) -> bool:
        if len(candles) < lookback * 2 + 1:
            return False
        recent = candles[-lookback:]
        prev = candles[-(lookback * 2) : -lookback]
        return min(c.low for c in recent) > min(c.low for c in prev)

    def _below_ema_consecutive(self, candles: list[Candle], ema: list[float], bars: int) -> bool:
        bars = max(1, bars)
        if len(candles) < bars or len(ema) < bars:
            return False
        for i in range(1, bars + 1):
            if candles[-i].close >= ema[-i]:
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

    def _atr(self, candles: list[Candle], period: int) -> float:
        if len(candles) < 2:
            return 0.0
        tr_values: list[float] = []
        for i in range(1, len(candles)):
            cur = candles[i]
            prev = candles[i - 1]
            tr = max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
            tr_values.append(tr)
        return float(mean(tr_values[-period:])) if tr_values else 0.0

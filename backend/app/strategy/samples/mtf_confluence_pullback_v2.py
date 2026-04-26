from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from app.models.candle import Candle
from app.services.regime_classifier import RegimeClassifier
from app.strategy.base import BaseStrategy, StrategyContext, StrategyDecision, StrategyMetadata


class MTFConfluencePullbackV2Strategy(BaseStrategy):
    """Spot long-only MTF confluence strategy with role-based weighting and hard gates."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="mtf_confluence_pullback_v2",
            name="MTF Confluence Pullback v2",
            version="2.0.0",
            description=(
                "Spot long-only MTF confluence strategy. "
                "Uses 1d regime gate (MA200), 4h trend, 1h setup, 15m trigger, and optional 30m/5m checks."
            ),
            short_description=(
                "200D/1D 방향 + 4H/1H 구조 + 30M/15M 회복 + 5M 추격 방지 기반 현물 롱 전용 MTF 전략"
            ),
            mode="multi_timeframe",
            required_roles=["regime", "trend", "setup", "trigger"],
            optional_roles=["confirmation", "execution"],
            spot_long_only=True,
        )

    def uses_context(self) -> bool:
        return True

    def required_timeframe_roles(self) -> list[str]:
        return ["regime", "trend", "setup", "trigger"]

    def optional_timeframe_roles(self) -> list[str]:
        return ["confirmation", "execution"]

    def default_timeframe_mapping(self) -> dict[str, str]:
        return {
            "regime": "1d",
            "trend": "4h",
            "setup": "1h",
            "confirmation": "30m",
            "trigger": "15m",
            "execution": "5m",
        }

    def default_params(self) -> dict[str, Any]:
        return {
            "entry_score_threshold": 70.0,
            "trend_ma_length": 200,
            "trend_slope_lookback": 20,
            "regime_ema_fast": 20,
            "regime_ema_mid": 50,
            "regime_ema_slow": 200,
            "require_regime_ema_stack": False,
            "trend_ema_fast": 20,
            "trend_ema_slow": 50,
            "trend_swing_lookback": 8,
            "allow_trend_alt_gate": False,
            "trend_structure_tolerance_pct": 0.0,
            "setup_rsi_length": 14,
            "setup_rsi_min": 40.0,
            "setup_rsi_max": 60.0,
            "setup_pullback_near_pct": 1.2,
            "setup_reject_lower_low": True,
            "setup_lower_low_tolerance_pct": 0.0,
            "entry_ema_length": 20,
            "entry_local_high_lookback": 5,
            "entry_volume_sma_length": 20,
            "entry_volume_multiplier": 1.1,
            "require_local_high_break": True,
            "allow_reclaim_bullish_without_high_break": False,
            "require_trigger_volume_confirmation": True,
            "trigger_bullish_body_ratio_min": 0.3,
            "confirmation_ema_length": 20,
            "confirmation_momentum_bars": 3,
            "confirmation_min_volume_ratio": 0.8,
            "execution_ema_length": 20,
            "execution_atr_length": 14,
            "max_execution_spike_pct": 1.5,
            "max_distance_from_setup_ema_pct": 2.5,
            "max_trigger_atr_extension": 1.5,
            "atr_length": 14,
            "atr_stop_mult": 1.8,
            "swing_lookback": 8,
            "swing_buffer_atr": 0.2,
            "min_stop_pct": 0.8,
            "max_stop_pct": 3.5,
            "trend_exit_confirm_bars": 2,
            "time_stop_hours": 72,
            "time_stop_min_profit_pct": 0.5,
            "after_stop_loss_hours": 12,
            "after_two_consecutive_stop_loss_hours": 48,
            "after_profit_exit_hours": 0,
        }

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        p = self.default_params() | params
        positive_int_fields = [
            "trend_ma_length",
            "trend_slope_lookback",
            "regime_ema_fast",
            "regime_ema_mid",
            "regime_ema_slow",
            "trend_ema_fast",
            "trend_ema_slow",
            "trend_swing_lookback",
            "setup_rsi_length",
            "entry_ema_length",
            "entry_local_high_lookback",
            "entry_volume_sma_length",
            "confirmation_ema_length",
            "confirmation_momentum_bars",
            "execution_ema_length",
            "execution_atr_length",
            "atr_length",
            "swing_lookback",
            "trend_exit_confirm_bars",
            "time_stop_hours",
        ]
        nonnegative_int_fields = [
            "after_stop_loss_hours",
            "after_two_consecutive_stop_loss_hours",
            "after_profit_exit_hours",
        ]
        for key in positive_int_fields:
            p[key] = int(p[key])
            if p[key] <= 0:
                raise ValueError(f"{key} must be positive")
        for key in nonnegative_int_fields:
            p[key] = int(p[key])
            if p[key] < 0:
                raise ValueError(f"{key} must be >= 0")

        float_fields = [
            "entry_score_threshold",
            "setup_rsi_min",
            "setup_rsi_max",
            "setup_pullback_near_pct",
            "setup_lower_low_tolerance_pct",
            "trend_structure_tolerance_pct",
            "entry_volume_multiplier",
            "trigger_bullish_body_ratio_min",
            "confirmation_min_volume_ratio",
            "max_execution_spike_pct",
            "max_distance_from_setup_ema_pct",
            "max_trigger_atr_extension",
            "atr_stop_mult",
            "swing_buffer_atr",
            "min_stop_pct",
            "max_stop_pct",
            "time_stop_min_profit_pct",
        ]
        for key in float_fields:
            p[key] = float(p[key])
            if p[key] < 0:
                raise ValueError(f"{key} must be >= 0")

        p["require_regime_ema_stack"] = bool(p["require_regime_ema_stack"])
        p["setup_reject_lower_low"] = bool(p["setup_reject_lower_low"])
        p["allow_trend_alt_gate"] = bool(p["allow_trend_alt_gate"])
        p["require_local_high_break"] = bool(p["require_local_high_break"])
        p["allow_reclaim_bullish_without_high_break"] = bool(p["allow_reclaim_bullish_without_high_break"])
        p["require_trigger_volume_confirmation"] = bool(p["require_trigger_volume_confirmation"])

        if not (0 <= p["entry_score_threshold"] <= 100):
            raise ValueError("entry_score_threshold must be in [0, 100]")
        if p["setup_rsi_min"] >= p["setup_rsi_max"]:
            raise ValueError("setup_rsi_min must be smaller than setup_rsi_max")
        if p["min_stop_pct"] >= p["max_stop_pct"]:
            raise ValueError("min_stop_pct must be smaller than max_stop_pct")
        if p["trend_ema_fast"] >= p["trend_ema_slow"]:
            raise ValueError("trend_ema_fast must be smaller than trend_ema_slow")
        if not (p["regime_ema_fast"] < p["regime_ema_mid"] < p["regime_ema_slow"]):
            raise ValueError("regime ema lengths must satisfy fast < mid < slow")
        return p

    def warmup_candles(self, params: dict[str, Any]) -> int:
        p = self.validate_params(params)
        return max(
            p["trend_ma_length"] + p["trend_slope_lookback"] + 5,
            p["regime_ema_slow"] + 5,
            p["trend_ema_slow"] + p["trend_swing_lookback"] * 2 + 10,
            p["setup_rsi_length"] + p["swing_lookback"] * 2 + 10,
            p["entry_ema_length"] + p["entry_volume_sma_length"] + p["atr_length"] + 10,
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
            take_profit=(latest.close * 1.03) if latest else None,
            reason_tags=["mtf_context_required"],
            debug_info={},
        )

    def evaluate_context(self, context: StrategyContext, params: dict[str, Any]) -> StrategyDecision:
        p = self.validate_params(params)
        regime_classifier = RegimeClassifier()
        regime = context.candles_by_role.get("regime", [])
        trend = context.candles_by_role.get("trend", [])
        setup = context.candles_by_role.get("setup", [])
        trigger = context.candles_by_role.get("trigger", [])
        confirmation = context.candles_by_role.get("confirmation", [])
        execution = context.candles_by_role.get("execution", [])
        runtime_state = context.runtime_state or {}

        if len(regime) < p["trend_ma_length"] + p["trend_slope_lookback"] + 2:
            return self._reject("insufficient_regime_history", context, runtime_state)
        if len(trend) < p["trend_ema_slow"] + p["trend_swing_lookback"] * 2 + 2:
            return self._reject("insufficient_trend_history", context, runtime_state)
        if len(setup) < max(p["setup_rsi_length"] + 2, p["swing_lookback"] * 2 + 2):
            return self._reject("insufficient_setup_history", context, runtime_state)
        if len(trigger) < max(
            p["entry_ema_length"] + 2,
            p["entry_local_high_lookback"] + 2,
            p["entry_volume_sma_length"] + 2,
            p["atr_length"] + 2,
        ):
            return self._reject("insufficient_trigger_history", context, runtime_state)

        regime_point = regime_classifier.classify_last(
            regime,
            sma_length=p["trend_ma_length"],
            ema_fast=p["regime_ema_fast"],
            ema_mid=p["regime_ema_mid"],
            ema_slow=p["regime_ema_slow"],
            slope_short_lookback=5,
            slope_long_lookback=p["trend_slope_lookback"],
        )
        if regime_point is None or not regime_point.has_sufficient_history:
            return self._reject("insufficient_regime_history", context, runtime_state)
        daily_close = float(regime_point.close)
        ma200_now = float(regime_point.sma200 or 0.0)
        ma200_slope = float(regime_point.sma200_slope_20d or 0.0)
        regime_ema20 = [float(regime_point.ema20 or daily_close)]
        regime_ema50 = [float(regime_point.ema50 or daily_close)]
        regime_ema200 = [float(regime_point.ema200 or daily_close)]
        regime_stack_ok = regime_ema20[-1] > regime_ema50[-1] > regime_ema200[-1]
        daily_above_ma200 = bool(regime_point.above_sma200)
        daily_ma200_rising = ma200_slope > 0
        regime_class = regime_point.regime
        regime_gate_ok = regime_class == "bull_above_200"
        if p["require_regime_ema_stack"]:
            regime_gate_ok = regime_gate_ok and regime_stack_ok

        trend_ema20 = self._ema(trend, p["trend_ema_fast"])
        trend_ema50 = self._ema(trend, p["trend_ema_slow"])
        trend_close = trend[-1].close
        trend_slope = trend_ema50[-1] - trend_ema50[-2]
        trend_ema20_slope = trend_ema20[-1] - trend_ema20[-2]
        trend_structure_ok = self._higher_structure(
            trend,
            p["trend_swing_lookback"],
            tolerance_pct=p["trend_structure_tolerance_pct"],
        )
        trend_primary_ok = (
            trend_close > trend_ema50[-1]
            and trend_ema20[-1] > trend_ema50[-1]
            and trend_slope >= 0
            and trend_structure_ok
        )
        trend_alt_ok = (
            trend_close > trend_ema50[-1]
            and trend_ema20_slope >= 0
            and trend_structure_ok
        )
        trend_ok = trend_primary_ok or (p["allow_trend_alt_gate"] and trend_alt_ok)

        setup_ema20 = self._ema(setup, 20)
        setup_ema50 = self._ema(setup, 50)
        setup_close = setup[-1].close
        setup_above_ema50 = setup_close > setup_ema50[-1]
        near_ema20 = abs(setup_close - setup_ema20[-1]) / max(setup_close, 1e-9) * 100 <= p["setup_pullback_near_pct"]
        near_ema50 = abs(setup_close - setup_ema50[-1]) / max(setup_close, 1e-9) * 100 <= p["setup_pullback_near_pct"]
        setup_pullback_ok = setup_above_ema50 and (near_ema20 or near_ema50)
        setup_rsi = self._rsi(setup, p["setup_rsi_length"])
        setup_rsi_ok = p["setup_rsi_min"] <= setup_rsi[-1] <= p["setup_rsi_max"]
        setup_recent_low = min(c.low for c in setup[-p["swing_lookback"] :])
        setup_prev_low = min(c.low for c in setup[-(p["swing_lookback"] * 2) : -p["swing_lookback"]])
        lower_low_tolerance = max(0.0, p["setup_lower_low_tolerance_pct"]) / 100.0
        setup_lower_low_break = setup_recent_low < setup_prev_low * (1 - lower_low_tolerance)
        setup_ok = setup_pullback_ok and setup_rsi_ok and (not (p["setup_reject_lower_low"] and setup_lower_low_break))

        confirmation_ok = True
        confirmation_details = {"available": False}
        if len(confirmation) >= max(10, p["confirmation_ema_length"] + p["confirmation_momentum_bars"] + 1):
            conf_ema = self._ema(confirmation, p["confirmation_ema_length"])
            conf_reclaim = confirmation[-1].close > conf_ema[-1]
            conf_lows = [c.low for c in confirmation[-p["confirmation_momentum_bars"] :]]
            conf_low_slowing = conf_lows[-1] >= min(conf_lows[:-1]) if len(conf_lows) > 1 else True
            conf_vol = confirmation[-1].volume / max(mean(c.volume for c in confirmation[-20:]), 1e-9)
            confirmation_ok = conf_reclaim and conf_low_slowing and conf_vol >= p["confirmation_min_volume_ratio"]
            confirmation_details = {
                "available": True,
                "close_above_ema": conf_reclaim,
                "low_slowing": conf_low_slowing,
                "volume_ratio": round(conf_vol, 6),
            }

        trigger_ema = self._ema(trigger, p["entry_ema_length"])
        trigger_close = trigger[-1].close
        trigger_reclaim = trigger_close > trigger_ema[-1]
        prev_local_high = max(c.high for c in trigger[-(p["entry_local_high_lookback"] + 1) : -1])
        local_high_break = trigger_close > prev_local_high
        trigger_vol_sma = mean(c.volume for c in trigger[-p["entry_volume_sma_length"] :])
        trigger_volume_ok = (
            trigger[-1].volume >= trigger_vol_sma * p["entry_volume_multiplier"]
            if p["require_trigger_volume_confirmation"]
            else True
        )
        trigger_range = max(trigger[-1].high - trigger[-1].low, 1e-9)
        trigger_body_ratio = abs(trigger[-1].close - trigger[-1].open) / trigger_range
        trigger_bullish_close = (
            trigger[-1].close > trigger[-1].open and trigger_body_ratio >= p["trigger_bullish_body_ratio_min"]
        )
        local_high_ok = local_high_break
        if p["allow_reclaim_bullish_without_high_break"]:
            local_high_ok = local_high_ok or (trigger_reclaim and trigger_bullish_close)
        if not p["require_local_high_break"]:
            local_high_ok = local_high_ok or (trigger_reclaim and trigger_bullish_close)
        trigger_ok = trigger_reclaim and local_high_ok and trigger_volume_ok

        trigger_atr = self._atr(trigger, p["atr_length"])
        chase_distance_pct = ((trigger_close - setup_ema20[-1]) / max(setup_ema20[-1], 1e-9)) * 100
        trigger_atr_extension_ok = trigger_close <= trigger_ema[-1] + trigger_atr * p["max_trigger_atr_extension"]
        distance_ok = chase_distance_pct <= p["max_distance_from_setup_ema_pct"]
        chase_ok = distance_ok and trigger_atr_extension_ok

        execution_ok = True
        execution_details = {"available": False}
        if len(execution) >= max(20, p["execution_ema_length"] + p["execution_atr_length"] + 2):
            exec_ema = self._ema(execution, p["execution_ema_length"])
            exec_atr = self._atr(execution, p["execution_atr_length"])
            exec_spike_pct = ((execution[-1].close - execution[-2].close) / max(execution[-2].close, 1e-9)) * 100
            exec_extension = (execution[-1].close - exec_ema[-1]) / max(exec_atr, 1e-9)
            execution_ok = (
                exec_spike_pct <= p["max_execution_spike_pct"]
                and execution[-1].close <= exec_ema[-1] + exec_atr * p["max_trigger_atr_extension"]
                and exec_extension <= p["max_trigger_atr_extension"]
            )
            execution_details = {
                "available": True,
                "spike_pct": round(exec_spike_pct, 6),
                "extension_atr": round(exec_extension, 6),
            }

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
            if regime_class in {"below_200_downtrend", "below_200_recovery"}:
                exit_signal_reason = "daily_trend_bearish"
            elif self._below_ema_consecutive(trend, trend_ema50, p["trend_exit_confirm_bars"]):
                exit_signal_reason = "trend_reversal_confirmed"
            else:
                entry_price = float(position_state.get("entry_price", trigger_close))
                held_hours = max(
                    0.0,
                    (context.as_of - datetime.fromisoformat(str(position_state.get("entry_time")))).total_seconds() / 3600,
                )
                unrealized_pnl_pct = ((trigger_close - entry_price) / max(entry_price, 1e-9)) * 100
                if held_hours >= p["time_stop_hours"] and unrealized_pnl_pct < p["time_stop_min_profit_pct"]:
                    exit_signal_reason = "time_stop"

        reject_reason: str | None = None
        if not regime_gate_ok:
            if regime_class == "below_200_downtrend":
                reject_reason = "regime_below_200_downtrend"
            elif regime_class == "above_200_weak":
                reject_reason = "regime_above_200_but_weak"
            elif regime_class == "below_200_recovery":
                reject_reason = "regime_recovery_not_confirmed"
            else:
                reject_reason = "regime_filter_blocked"
        elif not trend_ok:
            reject_reason = "higher_timeframe_trend_weak"
        elif not setup_pullback_ok:
            reject_reason = "setup_not_pullback"
        elif p["setup_reject_lower_low"] and setup_lower_low_break:
            reject_reason = "setup_lower_low_break"
        elif not setup_rsi_ok:
            reject_reason = "setup_rsi_out_of_range"
        elif not trigger_reclaim:
            reject_reason = "no_trigger_reclaim"
        elif not local_high_ok:
            reject_reason = "no_local_high_break"
        elif not trigger_volume_ok:
            reject_reason = "trigger_volume_not_confirmed"
        elif not chase_ok:
            reject_reason = "chase_filter_blocked"
        elif not execution_ok:
            reject_reason = "execution_overextended"
        elif stop_distance_pct < p["min_stop_pct"]:
            reject_reason = "stop_too_tight"
        elif stop_distance_pct > p["max_stop_pct"]:
            reject_reason = "risk_too_wide"
        elif in_cooldown:
            reject_reason = "cooldown_after_stop"

        score_breakdown = {
            "regime": 30.0 if regime_gate_ok else 0.0,
            "trend": 25.0 if trend_ok else 0.0,
            "setup": 20.0 if setup_ok else 0.0,
            "confirmation": 10.0 if confirmation_ok else 0.0,
            "trigger": 10.0 if trigger_ok else 0.0,
            "execution": 5.0 if execution_ok else 0.0,
        }
        score = sum(score_breakdown.values())
        if reject_reason is None and score < p["entry_score_threshold"]:
            reject_reason = "score_below_threshold"

        entry_allowed = reject_reason is None
        regime_label = regime_class
        if exit_signal_reason:
            regime_label = "bearish"

        debug_info = {
            "timeframe_mapping": context.timeframe_mapping,
            "score_breakdown": score_breakdown,
            "daily_ma200": round(ma200_now, 6),
            "daily_ma200_slope": round(ma200_slope, 8),
            "daily_close": round(daily_close, 6),
            "daily_ema20": round(regime_ema20[-1], 6),
            "daily_ema50": round(regime_ema50[-1], 6),
            "daily_ema200": round(regime_ema200[-1], 6),
            "is_regime_bullish": regime_gate_ok,
            "regime_classification": regime_class,
            "regime_above_sma200": daily_above_ma200,
            "trend_close": round(trend_close, 6),
            "trend_ema20": round(trend_ema20[-1], 6),
            "trend_ema50": round(trend_ema50[-1], 6),
            "trend_structure_ok": trend_structure_ok,
            "trend_primary_ok": trend_primary_ok,
            "trend_alt_ok": trend_alt_ok,
            "trend_ema20_slope": round(trend_ema20_slope, 8),
            "setup_close": round(setup_close, 6),
            "setup_ema20": round(setup_ema20[-1], 6),
            "setup_ema50": round(setup_ema50[-1], 6),
            "setup_rsi": round(setup_rsi[-1], 6),
            "setup_lower_low_break": setup_lower_low_break,
            "confirmation": confirmation_details,
            "trigger_close": round(trigger_close, 6),
            "trigger_ema20": round(trigger_ema[-1], 6),
            "prev_local_high": round(prev_local_high, 6),
            "trigger_local_high_ok": local_high_ok,
            "trigger_bullish_close": trigger_bullish_close,
            "trigger_bullish_body_ratio": round(trigger_body_ratio, 6),
            "trigger_volume": round(trigger[-1].volume, 6),
            "trigger_volume_sma": round(trigger_vol_sma, 6),
            "trigger_atr": round(trigger_atr, 8),
            "chase_distance_pct": round(chase_distance_pct, 6),
            "trigger_atr_extension_ok": trigger_atr_extension_ok,
            "execution": execution_details,
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
            take_profit=round(trigger_close + trigger_atr * 6.0, 6),
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
                pass
        return {
            "last_exit_reason": last_exit_reason,
            "last_exit_time": last_exit_time_raw,
            "consecutive_stop_losses": consecutive_stop_losses,
            "cooldown_hours": cooldown_hours,
            "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
            "in_cooldown": in_cooldown,
        }

    def _higher_structure(self, candles: list[Candle], lookback: int, tolerance_pct: float = 0.0) -> bool:
        if len(candles) < lookback * 2 + 1:
            return False
        recent = candles[-lookback:]
        prev = candles[-(lookback * 2) : -lookback]
        tol = max(0.0, float(tolerance_pct)) / 100.0
        recent_low = min(c.low for c in recent)
        prev_low = min(c.low for c in prev)
        recent_high = max(c.high for c in recent)
        prev_high = max(c.high for c in prev)
        return recent_low >= prev_low * (1 - tol) and recent_high >= prev_high * (1 - tol)

    def _below_ema_consecutive(self, candles: list[Candle], ema: list[float], bars: int) -> bool:
        bars = max(1, bars)
        if len(candles) < bars or len(ema) < bars:
            return False
        for idx in range(1, bars + 1):
            if candles[-idx].close >= ema[-idx]:
                return False
        return True

    def _sma_series(self, values: list[float], window: int) -> list[float]:
        if len(values) < window:
            return []
        out: list[float] = []
        for idx in range(window - 1, len(values)):
            out.append(mean(values[idx - window + 1 : idx + 1]))
        return out

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

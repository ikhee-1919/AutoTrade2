from statistics import mean
from typing import Any

from app.models.candle import Candle
from app.strategy.base import BaseStrategy, StrategyContext, StrategyDecision, StrategyMetadata


class TrendMomentumVolumeScoreV2Strategy(BaseStrategy):
    """Short-term trend strategy with momentum/quality guards."""

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="trend_momentum_volume_score_v2",
            name="Trend Momentum Volume Score v2",
            version="2.0.0",
            description=(
                "1h trend alignment + 5m pullback reclaim + RSI/MACD + volume/candle quality + "
                "extension/volatility regime filters."
            ),
            mode="multi_timeframe",
            required_roles=["trend", "entry"],
            optional_roles=["setup", "confirmation"],
        )

    def uses_context(self) -> bool:
        return True

    def required_timeframe_roles(self) -> list[str]:
        return ["trend", "entry"]

    def default_timeframe_mapping(self) -> dict[str, str]:
        return {"trend": "60m", "entry": "5m"}

    def default_params(self) -> dict[str, Any]:
        return {
            "threshold": 0.72,
            "max_extension_atr": 1.5,
            "min_atr_pct": 0.0015,
            "max_atr_pct": 0.03,
            "volume_surge_ratio": 1.5,
            "volume_strong_ratio": 2.5,
            "require_h1_trend_alignment": True,
            "require_pullback_reclaim": True,
            "require_volume_surge": True,
            "require_rsi_or_macd": True,
            "require_not_extended": True,
            "require_vol_regime": True,
        }

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        p = self.default_params() | params
        for key in ("threshold", "max_extension_atr", "min_atr_pct", "max_atr_pct", "volume_surge_ratio", "volume_strong_ratio"):
            p[key] = float(p[key])
            if p[key] <= 0:
                raise ValueError(f"{key} must be positive")
        if p["threshold"] > 1.2:
            raise ValueError("threshold must be <= 1.2")
        if p["min_atr_pct"] >= p["max_atr_pct"]:
            raise ValueError("min_atr_pct must be smaller than max_atr_pct")
        if p["volume_surge_ratio"] > p["volume_strong_ratio"]:
            raise ValueError("volume_surge_ratio must be <= volume_strong_ratio")

        for key in (
            "require_h1_trend_alignment",
            "require_pullback_reclaim",
            "require_volume_surge",
            "require_rsi_or_macd",
            "require_not_extended",
            "require_vol_regime",
        ):
            p[key] = bool(p[key])
        return p

    def warmup_candles(self, params: dict[str, Any]) -> int:
        _ = self.validate_params(params)
        return 60

    def evaluate(self, candles: list[Candle], params: dict[str, Any]) -> StrategyDecision:
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
        reason_tags: list[str] = []

        if len(trend) < 55:
            return self._reject("insufficient_trend_history", reason_tags, context, None)
        if len(entry) < 40:
            return self._reject("insufficient_entry_history", reason_tags, context, None)

        trend_ema20 = self._ema(trend, 20)
        trend_ema50 = self._ema(trend, 50)
        trend_slope = trend_ema20[-1] - trend_ema20[-3]
        trend_ok = trend_ema20[-1] > trend_ema50[-1] and trend_slope > 0 and trend[-1].close > trend_ema20[-1]

        entry_ema20 = self._ema(entry, 20)
        reclaim_window = entry[-5:] if len(entry) >= 5 else entry
        touched_ema20 = any(c.low <= entry_ema20[len(entry) - len(reclaim_window) + i] for i, c in enumerate(reclaim_window))
        pullback_reclaim_ok = touched_ema20 and entry[-1].close > entry_ema20[-1]

        rsi = self._rsi(entry, 14)
        rsi_cross_50 = len(rsi) >= 2 and rsi[-2] < 50 <= rsi[-1]
        rsi_rising_zone = len(rsi) >= 3 and 40 <= rsi[-1] <= 65 and rsi[-1] > rsi[-2] > rsi[-3]
        rsi_ok = rsi_cross_50 or rsi_rising_zone

        macd_hist = self._macd_hist(entry)
        macd_cross = len(macd_hist) >= 2 and macd_hist[-2] < 0 <= macd_hist[-1]
        macd_improve = len(macd_hist) >= 4 and macd_hist[-1] > 0 and macd_hist[-1] > macd_hist[-2] > macd_hist[-3]
        macd_ok = macd_cross or macd_improve
        momentum_ok = rsi_ok or macd_ok

        volumes = [c.volume for c in entry]
        vol_ma20 = mean(volumes[-20:])
        vol_ratio = entry[-1].volume / max(vol_ma20, 1e-9)
        volume_ok = vol_ratio >= p["volume_surge_ratio"]
        volume_strong = vol_ratio >= p["volume_strong_ratio"]

        last = entry[-1]
        rng = max(last.high - last.low, 1e-9)
        body = abs(last.close - last.open)
        bullish = last.close > last.open
        body_ratio = body / rng
        candle_quality_ok = bullish and body_ratio >= 0.5

        atr = self._atr(entry, 14)
        atr_last = atr[-1]
        extension_atr = (last.close - entry_ema20[-1]) / max(atr_last, 1e-9)
        not_extended = extension_atr < p["max_extension_atr"]

        atr_pct = atr_last / max(last.close, 1e-9)
        vol_regime_ok = p["min_atr_pct"] <= atr_pct <= p["max_atr_pct"]

        gate_checks = [
            ("h1_trend_not_aligned", p["require_h1_trend_alignment"], trend_ok),
            ("pullback_reclaim_missing", p["require_pullback_reclaim"], pullback_reclaim_ok),
            ("rsi_macd_not_positive", p["require_rsi_or_macd"], momentum_ok),
            ("volume_surge_missing", p["require_volume_surge"], volume_ok),
            ("overextended_by_atr", p["require_not_extended"], not_extended),
            ("volatility_regime_out_of_range", p["require_vol_regime"], vol_regime_ok),
        ]
        for reason, required, ok in gate_checks:
            if required and not ok:
                reason_tags.append(reason)

        score = 0.0
        score += 0.28 if trend_ok else 0.0
        score += 0.2 if pullback_reclaim_ok else 0.0
        score += 0.18 if momentum_ok else 0.0
        score += 0.16 if volume_ok else 0.0
        score += 0.05 if volume_strong else 0.0
        score += 0.08 if candle_quality_ok else 0.0
        score += 0.03 if not_extended else 0.0
        score += 0.02 if vol_regime_ok else 0.0

        entry_allowed = len(reason_tags) == 0 and score >= p["threshold"] and candle_quality_ok
        if not entry_allowed and not reason_tags:
            reason_tags.append("score_below_threshold_or_low_quality")

        stop_loss = last.close - atr_last * 1.4
        take_profit = last.close + atr_last * 2.2
        regime = "bullish_aligned" if trend_ok else "not_aligned"
        return StrategyDecision(
            strategy_name=self.metadata().name,
            strategy_version=self.metadata().version,
            regime=regime,
            entry_allowed=entry_allowed,
            score=round(score, 4),
            reject_reason=None if entry_allowed else reason_tags[0],
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            reason_tags=reason_tags,
            debug_info={
                "timeframe_mapping": context.timeframe_mapping,
                "regime_by_role": {
                    "trend": "bullish" if trend_ok else "not_bullish",
                    "entry": "reclaim_ok" if pullback_reclaim_ok else "reclaim_fail",
                },
                "signals": {
                    "trend_ok": trend_ok,
                    "pullback_reclaim_ok": pullback_reclaim_ok,
                    "rsi_ok": rsi_ok,
                    "macd_ok": macd_ok,
                    "momentum_ok": momentum_ok,
                    "volume_ok": volume_ok,
                    "volume_strong": volume_strong,
                    "candle_quality_ok": candle_quality_ok,
                    "not_extended": not_extended,
                    "vol_regime_ok": vol_regime_ok,
                },
                "metrics": {
                    "trend_ema20": round(trend_ema20[-1], 6),
                    "trend_ema50": round(trend_ema50[-1], 6),
                    "trend_slope": round(trend_slope, 6),
                    "entry_ema20": round(entry_ema20[-1], 6),
                    "rsi": round(rsi[-1], 4),
                    "macd_hist": round(macd_hist[-1], 6),
                    "volume_ratio": round(vol_ratio, 4),
                    "body_ratio": round(body_ratio, 4),
                    "extension_atr": round(extension_atr, 4),
                    "atr_pct": round(atr_pct, 6),
                },
                "optional_flow": {
                    "trade_buy_ratio": context.metadata_by_role.get("entry", {}).get("trade_buy_ratio"),
                    "orderbook_imbalance": context.metadata_by_role.get("entry", {}).get("orderbook_imbalance"),
                },
            },
        )

    def _reject(
        self,
        reason: str,
        tags: list[str],
        context: StrategyContext,
        last_price: float | None,
    ) -> StrategyDecision:
        tags = [reason] + tags
        return StrategyDecision(
            strategy_name=self.metadata().name,
            strategy_version=self.metadata().version,
            regime="unknown",
            entry_allowed=False,
            score=0.0,
            reject_reason=reason,
            stop_loss=(last_price * 0.98) if last_price else None,
            take_profit=(last_price * 1.03) if last_price else None,
            reason_tags=tags,
            debug_info={"timeframe_mapping": context.timeframe_mapping},
        )

    def _ema(self, candles: list[Candle], length: int) -> list[float]:
        closes = [c.close for c in candles]
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

    def _macd_hist(self, candles: list[Candle]) -> list[float]:
        ema12 = self._ema(candles, 12)
        ema26 = self._ema(candles, 26)
        macd_line = [a - b for a, b in zip(ema12, ema26)]
        k = 2 / (9 + 1)
        signal = macd_line[0]
        signal_line: list[float] = []
        for value in macd_line:
            signal = value * k + signal * (1 - k)
            signal_line.append(signal)
        return [m - s for m, s in zip(macd_line, signal_line)]

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

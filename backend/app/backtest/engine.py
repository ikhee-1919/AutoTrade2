from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Callable

from app.models.candle import Candle
from app.models.trade import Position
from app.strategy.base import BaseStrategy, StrategyContext


@dataclass(frozen=True)
class ClosedTrade:
    entry_time: str
    exit_time: str
    side: str
    intended_entry_price: float
    filled_entry_price: float
    intended_exit_price: float
    filled_exit_price: float
    gross_pnl: float
    net_pnl: float
    fee_entry: float
    fee_exit: float
    total_fees: float
    slippage_entry_cost: float
    slippage_exit_cost: float
    total_slippage_cost: float
    total_trading_cost: float
    entry_price: float
    exit_price: float
    pnl: float
    reason: str
    gross_pnl_pct: float
    net_pnl_pct: float
    fees: float
    slippage: float
    holding_time: float
    entry_reason: str
    exit_reason: str
    stop_price: float | None
    highest_price_during_trade: float | None
    lowest_price_during_trade: float | None
    r_multiple: float | None
    entry_signal_score: float | None
    exit_signal_score: float | None
    max_favorable_excursion_pct: float | None
    max_adverse_excursion_pct: float | None


@dataclass(frozen=True)
class BacktestExecutionConfig:
    execution_policy: str = "next_open"
    fee_rate: float = 0.0005
    entry_fee_rate: float = 0.0005
    exit_fee_rate: float = 0.0005
    apply_fee_on_entry: bool = True
    apply_fee_on_exit: bool = True
    slippage_rate: float = 0.0003
    entry_slippage_rate: float = 0.0003
    exit_slippage_rate: float = 0.0003
    benchmark_enabled: bool = True


class BacktestCancelledError(Exception):
    """Raised when a running backtest is cancelled."""


class BacktestEngine:
    def run(
        self,
        candles: list[Candle],
        strategy: BaseStrategy,
        params: dict,
        execution: BacktestExecutionConfig,
        timeframe_bundle: dict | None = None,
        trade_start_at: datetime | None = None,
        progress_callback: Callable[[float], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        if not candles:
            raise ValueError("No candles provided")

        validated_params = strategy.validate_params(params)
        warmup = strategy.warmup_candles(validated_params)
        if len(candles) <= warmup:
            raise ValueError(
                "Not enough candles for selected parameters: "
                f"strategy={strategy.metadata().strategy_id}, "
                f"required_more_than={warmup}, got={len(candles)}"
            )
        # Keep MTF context bounded and incremental to avoid O(n^2) slowdowns on long runs.
        context_history_limit = max(warmup + 5, 240)

        reject_reason_counts: Counter[str] = Counter()
        regime_counts: Counter[str] = Counter()
        exit_reason_counts: Counter[str] = Counter()

        position: Position | None = None
        trades: list[ClosedTrade] = []
        open_trade_meta: dict[str, float | int | str | None] | None = None
        runtime_state: dict[str, object | None] = {
            "last_exit_reason": None,
            "last_exit_time": None,
            "consecutive_stop_losses": 0,
            "last_exit_was_profit": None,
            "position": None,
        }

        net_equity = 1.0
        gross_equity = 1.0
        net_equity_curve: list[float] = []
        gross_equity_curve: list[float] = []
        equity_points: list[dict[str, float | str]] = []

        total_fees_paid = 0.0
        total_slippage_cost = 0.0
        execution_start_idx = self._execution_start_idx(
            candles=candles,
            warmup=warmup,
            trade_start_at=trade_start_at,
        )
        total_steps = len(candles) - execution_start_idx
        regime_points: list[dict[str, object | None]] = []
        mtf_bundle_rows: dict[str, list[Candle]] = {}
        mtf_bundle_metadata: dict[str, dict] = {}
        mtf_bundle_mapping: dict[str, str] = {}
        mtf_role_positions: dict[str, int] = {}
        if strategy.uses_context() and timeframe_bundle:
            mtf_bundle_rows = dict(timeframe_bundle.get("candles_by_role", {}))
            mtf_bundle_metadata = dict(timeframe_bundle.get("metadata_by_role", {}))
            mtf_bundle_mapping = dict(timeframe_bundle.get("mapping", {}))
            mtf_role_positions = {role: 0 for role in mtf_bundle_rows}

        for idx in range(execution_start_idx, len(candles)):
            if should_stop and should_stop():
                raise BacktestCancelledError("Backtest cancelled")

            current = candles[idx]
            history = candles[: idx + 1]
            if strategy.uses_context():
                runtime_state["position"] = (
                    {
                        "entry_time": position.entry_time.isoformat(),
                        "entry_price": position.entry_price,
                        "intended_entry_price": position.intended_entry_price,
                        "stop_loss": position.stop_loss,
                        "take_profit": position.take_profit,
                    }
                    if position is not None
                    else None
                )
                context = self._build_context(
                    symbol=(timeframe_bundle or {}).get("symbol", ""),
                    entry_candles=history,
                    as_of=current.timestamp,
                    timeframe_bundle=timeframe_bundle,
                    runtime_state=runtime_state,
                    history_limit=context_history_limit,
                    bundle_rows=mtf_bundle_rows,
                    bundle_metadata=mtf_bundle_metadata,
                    bundle_mapping=mtf_bundle_mapping,
                    role_positions=mtf_role_positions,
                )
                decision = strategy.evaluate_context(context, validated_params)
            else:
                decision = strategy.evaluate(history, validated_params)

            regime_counts[decision.regime] += 1
            if decision.reject_reason:
                reject_reason_counts[decision.reject_reason] += 1
            debug = decision.debug_info or {}
            daily_ma200_raw = debug.get("daily_ma200")
            close_for_regime = debug.get("daily_close", current.close)
            distance_from_sma200_pct = None
            if daily_ma200_raw is not None:
                try:
                    daily_ma200 = float(daily_ma200_raw)
                    close_val = float(close_for_regime)
                    distance_from_sma200_pct = ((close_val - daily_ma200) / max(daily_ma200, 1e-9)) * 100
                except (TypeError, ValueError):
                    daily_ma200 = None
            else:
                daily_ma200 = None
            regime_points.append(
                {
                    "timestamp": current.timestamp.isoformat(),
                    "regime": decision.regime,
                    "close": float(close_for_regime),
                    "sma200": daily_ma200,
                    "distance_from_sma200_pct": distance_from_sma200_pct,
                }
            )

            # Execution timing policy: signal_close (same bar close) or next_open (next bar open).
            fill_idx = idx
            if execution.execution_policy == "next_open":
                fill_idx = min(idx + 1, len(candles) - 1)
            fill_candle = candles[fill_idx]

            if position is None:
                if decision.entry_allowed and decision.stop_loss and decision.take_profit:
                    intended_entry_price = (
                        fill_candle.open
                        if execution.execution_policy == "next_open"
                        else current.close
                    )
                    filled_entry_price = intended_entry_price * (1 + execution.entry_slippage_rate)
                    stop_loss_filled = decision.stop_loss * (filled_entry_price / max(current.close, 1e-9))
                    take_profit_filled = decision.take_profit * (filled_entry_price / max(current.close, 1e-9))
                    position = Position(
                        entry_time=fill_candle.timestamp,
                        intended_entry_price=intended_entry_price,
                        entry_price=filled_entry_price,
                        stop_loss=stop_loss_filled,
                        take_profit=take_profit_filled,
                        reason=f"score={decision.score}",
                    )
                    open_trade_meta = {
                        "entry_idx": fill_idx,
                        "entry_reason": decision.reject_reason or "entry_signal",
                        "entry_score": float(decision.score),
                        "stop_price": float(stop_loss_filled),
                        "highest": float(fill_candle.high),
                        "lowest": float(fill_candle.low),
                    }

                net_equity_curve.append(net_equity)
                gross_equity_curve.append(gross_equity)
                equity_points.append(
                    {
                        "timestamp": current.timestamp.isoformat(),
                        "equity": round(net_equity, 6),
                    }
                )
                if progress_callback:
                    step = idx - execution_start_idx + 1
                    progress_callback(15 + (step / max(total_steps, 1)) * 75)
                continue

            exit_reason: str | None = None
            if current.close <= position.stop_loss:
                exit_reason = "stop_loss"
            elif current.close >= position.take_profit:
                exit_reason = "take_profit"
            elif decision.regime == "bearish":
                exit_reason = (
                    str(decision.debug_info.get("exit_signal_reason"))
                    if decision.debug_info.get("exit_signal_reason")
                    else "regime_reversal"
                )
            elif idx == len(candles) - 1:
                exit_reason = "end_of_test"

            if exit_reason:
                intended_exit_price = (
                    fill_candle.open
                    if execution.execution_policy == "next_open"
                    else current.close
                )
                filled_exit_price = intended_exit_price * (1 - execution.exit_slippage_rate)

                fee_entry = (
                    position.entry_price * execution.entry_fee_rate if execution.apply_fee_on_entry else 0.0
                )
                fee_exit = (
                    filled_exit_price * execution.exit_fee_rate if execution.apply_fee_on_exit else 0.0
                )

                gross_profit_amount = intended_exit_price - position.intended_entry_price
                net_profit_amount = (
                    filled_exit_price - position.entry_price - fee_entry - fee_exit
                )

                gross_return = gross_profit_amount / max(position.intended_entry_price, 1e-9)
                net_return = net_profit_amount / max(position.entry_price, 1e-9)

                entry_idx = int((open_trade_meta or {}).get("entry_idx", fill_idx))
                trade_window = candles[entry_idx : fill_idx + 1]
                trade_high = max((c.high for c in trade_window), default=fill_candle.high)
                trade_low = min((c.low for c in trade_window), default=fill_candle.low)
                if open_trade_meta:
                    trade_high = max(float(open_trade_meta.get("highest", trade_high)), trade_high)
                    trade_low = min(float(open_trade_meta.get("lowest", trade_low)), trade_low)

                stop_price = float((open_trade_meta or {}).get("stop_price", position.stop_loss))
                stop_distance = max(position.entry_price - stop_price, 1e-9)
                r_multiple = net_profit_amount / stop_distance
                holding_hours = (fill_candle.timestamp - position.entry_time).total_seconds() / 3600
                mfe_pct = ((trade_high - position.entry_price) / max(position.entry_price, 1e-9)) * 100
                mae_pct = ((trade_low - position.entry_price) / max(position.entry_price, 1e-9)) * 100

                slippage_entry_cost = max(position.entry_price - position.intended_entry_price, 0.0)
                slippage_exit_cost = max(intended_exit_price - filled_exit_price, 0.0)
                total_slippage = slippage_entry_cost + slippage_exit_cost

                total_fees = fee_entry + fee_exit
                total_cost = total_fees + total_slippage
                exit_reason_counts[exit_reason] += 1

                net_equity *= 1 + net_return
                gross_equity *= 1 + gross_return

                total_fees_paid += total_fees
                total_slippage_cost += total_slippage

                trades.append(
                    ClosedTrade(
                        entry_time=position.entry_time.isoformat(),
                        exit_time=fill_candle.timestamp.isoformat(),
                        side="long",
                        intended_entry_price=round(position.intended_entry_price, 6),
                        filled_entry_price=round(position.entry_price, 6),
                        intended_exit_price=round(intended_exit_price, 6),
                        filled_exit_price=round(filled_exit_price, 6),
                        gross_pnl=round(gross_return * 100, 4),
                        net_pnl=round(net_return * 100, 4),
                        fee_entry=round(fee_entry, 6),
                        fee_exit=round(fee_exit, 6),
                        total_fees=round(total_fees, 6),
                        slippage_entry_cost=round(slippage_entry_cost, 6),
                        slippage_exit_cost=round(slippage_exit_cost, 6),
                        total_slippage_cost=round(total_slippage, 6),
                        total_trading_cost=round(total_cost, 6),
                        entry_price=round(position.entry_price, 4),
                        exit_price=round(filled_exit_price, 4),
                        pnl=round(net_return * 100, 4),
                        reason=exit_reason,
                        gross_pnl_pct=round(gross_return * 100, 4),
                        net_pnl_pct=round(net_return * 100, 4),
                        fees=round(total_fees, 6),
                        slippage=round(total_slippage, 6),
                        holding_time=round(holding_hours, 4),
                        entry_reason=str((open_trade_meta or {}).get("entry_reason", "entry_signal")),
                        exit_reason=exit_reason,
                        stop_price=round(stop_price, 6),
                        highest_price_during_trade=round(trade_high, 6),
                        lowest_price_during_trade=round(trade_low, 6),
                        r_multiple=round(r_multiple, 4),
                        entry_signal_score=float((open_trade_meta or {}).get("entry_score", decision.score)),
                        exit_signal_score=float(decision.score),
                        max_favorable_excursion_pct=round(mfe_pct, 4),
                        max_adverse_excursion_pct=round(mae_pct, 4),
                    )
                )
                runtime_state["last_exit_reason"] = exit_reason
                runtime_state["last_exit_time"] = fill_candle.timestamp.isoformat()
                runtime_state["last_exit_was_profit"] = net_return > 0
                if exit_reason == "stop_loss":
                    runtime_state["consecutive_stop_losses"] = int(runtime_state.get("consecutive_stop_losses", 0) or 0) + 1
                else:
                    runtime_state["consecutive_stop_losses"] = 0
                position = None
                open_trade_meta = None

            else:
                if open_trade_meta:
                    open_trade_meta["highest"] = max(
                        float(open_trade_meta.get("highest", current.high)),
                        float(current.high),
                    )
                    open_trade_meta["lowest"] = min(
                        float(open_trade_meta.get("lowest", current.low)),
                        float(current.low),
                    )
                mark_to_market_net = net_equity * (current.close / max(position.entry_price, 1e-9))
                mark_to_market_gross = gross_equity * (
                    current.close / max(position.intended_entry_price, 1e-9)
                )
                net_equity_curve.append(mark_to_market_net)
                gross_equity_curve.append(mark_to_market_gross)
                equity_points.append(
                    {
                        "timestamp": current.timestamp.isoformat(),
                        "equity": round(mark_to_market_net, 6),
                    }
                )

            if exit_reason:
                net_equity_curve.append(net_equity)
                gross_equity_curve.append(gross_equity)
                equity_points.append(
                    {
                        "timestamp": fill_candle.timestamp.isoformat(),
                        "equity": round(net_equity, 6),
                    }
                )

            if progress_callback:
                step = idx - execution_start_idx + 1
                progress_callback(15 + (step / max(total_steps, 1)) * 75)

        net_pnl_values = [trade.net_pnl for trade in trades]
        wins = [p for p in net_pnl_values if p > 0]
        losses = [p for p in net_pnl_values if p <= 0]

        gross_return_pct = (gross_equity - 1.0) * 100
        net_return_pct = (net_equity - 1.0) * 100
        total_trading_cost = total_fees_paid + total_slippage_cost
        profit_factor = self._profit_factor(wins, losses)
        max_consecutive_losses = self._max_consecutive_losses(net_pnl_values)
        avg_holding_time = mean([trade.holding_time for trade in trades]) if trades else 0.0
        exposure_pct = self._exposure_pct(
            candles[execution_start_idx].timestamp if execution_start_idx < len(candles) else candles[0].timestamp,
            candles[-1].timestamp,
            trades,
        )
        regime_window = self._regime_window_stats(regime_points, reject_reason_counts)

        summary = {
            "total_return_pct": round(net_return_pct, 4),
            "gross_return_pct": round(gross_return_pct, 4),
            "net_return_pct": round(net_return_pct, 4),
            "trade_count": len(trades),
            "win_rate": round((len(wins) / len(trades) * 100), 2) if trades else 0.0,
            "max_drawdown": round(self._max_drawdown(net_equity_curve), 4),
            "avg_profit": round(mean(wins), 4) if wins else 0.0,
            "avg_loss": round(mean(losses), 4) if losses else 0.0,
            "profit_factor": round(profit_factor, 4),
            "avg_win_pct": round(mean(wins), 4) if wins else 0.0,
            "avg_loss_pct": round(mean(losses), 4) if losses else 0.0,
            "expectancy_per_trade": round(mean(net_pnl_values), 4) if net_pnl_values else 0.0,
            "max_consecutive_losses": max_consecutive_losses,
            "avg_holding_time": round(avg_holding_time, 4),
            "exposure_pct": round(exposure_pct, 4),
            "total_fees_paid": round(total_fees_paid, 6),
            "total_slippage_cost": round(total_slippage_cost, 6),
            "total_trading_cost": round(total_trading_cost, 6),
            "fee_total": round(total_fees_paid, 6),
            "slippage_total": round(total_slippage_cost, 6),
            "fee_impact_pct": round((total_fees_paid / max(1.0, abs(gross_return_pct))) * 100, 4),
            "slippage_impact_pct": round((total_slippage_cost / max(1.0, abs(gross_return_pct))) * 100, 4),
            "cost_drag_pct": round(gross_return_pct - net_return_pct, 4),
            "exit_reason_counts": dict(exit_reason_counts),
            "reject_reason_counts": dict(reject_reason_counts),
            "regime_counts": dict(regime_counts),
            "regime_segment_summaries": regime_window["regime_segments"],
            "above_200_days": regime_window["above_200_days"],
            "below_200_days": regime_window["below_200_days"],
            "insufficient_regime_history_count": regime_window["insufficient_regime_history_count"],
            "above_200_return": regime_window["above_200_return"],
            "below_200_return": regime_window["below_200_return"],
        }

        diagnostics = {
            "reject_reason_counts": dict(reject_reason_counts),
            "regime_counts": dict(regime_counts),
            "exit_reason_counts": dict(exit_reason_counts),
            "regime_segment_summaries": regime_window["regime_segments"],
            "above_200_segments": regime_window["above_segments"],
            "below_200_segments": regime_window["below_segments"],
            "above_200_days": regime_window["above_200_days"],
            "below_200_days": regime_window["below_200_days"],
            "insufficient_regime_history_count": regime_window["insufficient_regime_history_count"],
            "above_200_return": regime_window["above_200_return"],
            "below_200_return": regime_window["below_200_return"],
        }

        benchmark = self._benchmark(
            candles,
            execution_start_idx,
            execution.execution_policy,
            execution.benchmark_enabled,
            net_return_pct,
        )
        if benchmark:
            summary["buy_and_hold_return_pct"] = benchmark["benchmark_buy_and_hold_return_pct"]
            summary["excess_return_vs_buy_and_hold"] = benchmark["strategy_excess_return_pct"]
        else:
            summary["buy_and_hold_return_pct"] = 0.0
            summary["excess_return_vs_buy_and_hold"] = 0.0
        summary["monthly_returns"] = self._monthly_returns(
            candles,
            execution_start_idx,
            trades,
            execution.execution_policy,
        )

        return {
            "summary": summary,
            "benchmark": benchmark,
            "trades": [trade.__dict__ for trade in trades],
            "diagnostics": diagnostics,
            "equity_curve": equity_points,
        }

    def _build_context(
        self,
        symbol: str,
        entry_candles: list[Candle],
        as_of,
        timeframe_bundle: dict | None,
        runtime_state: dict[str, object | None] | None = None,
        history_limit: int | None = None,
        bundle_rows: dict[str, list[Candle]] | None = None,
        bundle_metadata: dict[str, dict] | None = None,
        bundle_mapping: dict[str, str] | None = None,
        role_positions: dict[str, int] | None = None,
    ) -> StrategyContext:
        candles_by_role: dict[str, list[Candle]] = {}
        metadata_by_role: dict[str, dict] = {}
        mapping: dict[str, str] = {}
        if timeframe_bundle:
            rows_by_role = bundle_rows if bundle_rows is not None else dict(timeframe_bundle.get("candles_by_role", {}))
            metadata_by_role = bundle_metadata if bundle_metadata is not None else dict(
                timeframe_bundle.get("metadata_by_role", {})
            )
            mapping = bundle_mapping if bundle_mapping is not None else dict(timeframe_bundle.get("mapping", {}))

            if role_positions is None:
                for role, rows in rows_by_role.items():
                    timestamps = [c.timestamp for c in rows]
                    cutoff = bisect_right(timestamps, as_of)
                    start = max(0, cutoff - history_limit) if history_limit is not None else 0
                    candles_by_role[role] = rows[start:cutoff]
            else:
                for role, rows in rows_by_role.items():
                    pos = role_positions.get(role, 0)
                    # As `as_of` moves forward in chronological order, we only advance the cursor.
                    while pos < len(rows) and rows[pos].timestamp <= as_of:
                        pos += 1
                    role_positions[role] = pos
                    start = max(0, pos - history_limit) if history_limit is not None else 0
                    candles_by_role[role] = rows[start:pos]
        entry_role = "entry" if "entry" in candles_by_role else "entry"
        if not candles_by_role:
            candles_by_role = {"entry": entry_candles}
            mapping = {"entry": "unknown"}
        elif "entry" not in candles_by_role:
            candles_by_role["entry"] = entry_candles
        return StrategyContext(
            symbol=symbol,
            timeframe_mapping=mapping,
            candles_by_role=candles_by_role,
            metadata_by_role=metadata_by_role,
            as_of=as_of,
            entry_role=entry_role,
            runtime_state=dict(runtime_state or {}),
        )

    def _benchmark(
        self,
        candles: list[Candle],
        start_idx: int,
        execution_policy: str,
        enabled: bool,
        strategy_return_pct: float,
    ) -> dict | None:
        if not enabled or len(candles) <= start_idx:
            return None

        if execution_policy == "next_open":
            start_idx = min(start_idx + 1, len(candles) - 1)

        start_price = candles[start_idx].open if execution_policy == "next_open" else candles[start_idx].close
        end_price = candles[-1].close
        bh_return_pct = ((end_price - start_price) / max(start_price, 1e-9)) * 100

        curve = []
        for candle in candles[start_idx:]:
            equity = candle.close / max(start_price, 1e-9)
            curve.append({"timestamp": candle.timestamp.isoformat(), "equity": round(equity, 6)})

        return {
            "benchmark_buy_and_hold_return_pct": round(bh_return_pct, 4),
            "strategy_excess_return_pct": round(strategy_return_pct - bh_return_pct, 4),
            "benchmark_start_price": round(start_price, 6),
            "benchmark_end_price": round(end_price, 6),
            "benchmark_curve": curve,
        }

    def _max_drawdown(self, equity_curve: list[float]) -> float:
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            drawdown = (peak - value) / peak if peak else 0.0
            max_dd = max(max_dd, drawdown)
        return max_dd * 100

    def _profit_factor(self, wins: list[float], losses: list[float]) -> float:
        wins_total = sum(wins)
        losses_total = abs(sum(losses))
        if losses_total > 0:
            return wins_total / losses_total
        if wins_total > 0:
            return 999.0
        return 0.0

    def _max_consecutive_losses(self, net_pnl_values: list[float]) -> int:
        max_streak = 0
        streak = 0
        for pnl in net_pnl_values:
            if pnl <= 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        return max_streak

    def _exposure_pct(self, start: datetime, end: datetime, trades: list[ClosedTrade]) -> float:
        window_seconds = max((end - start).total_seconds(), 1.0)
        holding_seconds = 0.0
        for trade in trades:
            try:
                entry_raw = trade.entry_time if hasattr(trade, "entry_time") else trade.get("entry_time")
                exit_raw = trade.exit_time if hasattr(trade, "exit_time") else trade.get("exit_time")
                entry = datetime.fromisoformat(str(entry_raw))
                exit_ = datetime.fromisoformat(str(exit_raw))
            except (ValueError, AttributeError, TypeError):
                continue
            holding_seconds += max((exit_ - entry).total_seconds(), 0.0)
        return (holding_seconds / window_seconds) * 100

    def _monthly_returns(
        self,
        candles: list[Candle],
        start_idx: int,
        trades: list[ClosedTrade],
        execution_policy: str,
    ) -> list[dict]:
        if len(candles) <= start_idx:
            return []

        month_trade_stats: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {
                "gross_equity": 1.0,
                "net_equity": 1.0,
                "trade_count": 0,
            }
        )
        for trade in trades:
            period = trade.exit_time[:7]
            payload = month_trade_stats[period]
            payload["gross_equity"] = float(payload["gross_equity"]) * (1 + (trade.gross_pnl / 100))
            payload["net_equity"] = float(payload["net_equity"]) * (1 + (trade.net_pnl / 100))
            payload["trade_count"] = int(payload["trade_count"]) + 1

        monthly_price_bounds: dict[str, dict[str, float]] = {}
        if execution_policy == "next_open":
            start_idx = min(start_idx + 1, len(candles) - 1)
        for candle in candles[start_idx:]:
            period = candle.timestamp.strftime("%Y-%m")
            if period not in monthly_price_bounds:
                monthly_price_bounds[period] = {
                    "start": candle.open if execution_policy == "next_open" else candle.close,
                    "end": candle.close,
                }
            else:
                monthly_price_bounds[period]["end"] = candle.close

        periods = sorted(set(monthly_price_bounds.keys()) | set(month_trade_stats.keys()))
        result: list[dict] = []
        for period in periods:
            trade_payload = month_trade_stats.get(period, {"gross_equity": 1.0, "net_equity": 1.0, "trade_count": 0})
            gross_return = (float(trade_payload["gross_equity"]) - 1) * 100
            net_return = (float(trade_payload["net_equity"]) - 1) * 100
            price_bounds = monthly_price_bounds.get(period)
            benchmark_return = 0.0
            if price_bounds:
                benchmark_return = (
                    (price_bounds["end"] - price_bounds["start"]) / max(price_bounds["start"], 1e-9)
                ) * 100
            result.append(
                {
                    "period": period,
                    "gross_return_pct": round(gross_return, 4),
                    "net_return_pct": round(net_return, 4),
                    "trade_count": int(trade_payload["trade_count"]),
                    "benchmark_return_pct": round(benchmark_return, 4),
                    "excess_return_pct": round(net_return - benchmark_return, 4),
                }
            )
        return result

    def _execution_start_idx(
        self,
        candles: list[Candle],
        warmup: int,
        trade_start_at: datetime | None,
    ) -> int:
        start_idx = warmup
        if trade_start_at is not None:
            while start_idx < len(candles) and candles[start_idx].timestamp < trade_start_at:
                start_idx += 1
        if start_idx >= len(candles):
            raise ValueError("No candles in trade period after applying warmup/history window")
        return start_idx

    def _regime_window_stats(
        self,
        points: list[dict[str, object | None]],
        reject_reason_counts: Counter[str],
    ) -> dict[str, object]:
        if not points:
            return {
                "regime_segments": [],
                "above_segments": [],
                "below_segments": [],
                "above_200_days": 0,
                "below_200_days": 0,
                "insufficient_regime_history_count": int(reject_reason_counts.get("insufficient_regime_history", 0)),
                "above_200_return": 0.0,
                "below_200_return": 0.0,
            }

        daily_points: list[dict[str, object | None]] = []
        seen_dates: set[str] = set()
        for point in reversed(points):
            ts = str(point.get("timestamp") or "")
            key = ts[:10]
            if key and key not in seen_dates:
                seen_dates.add(key)
                daily_points.append(point)
        daily_points.reverse()

        regime_segments = self._segments_by_label(daily_points, lambda p: str(p.get("regime") or "unknown"))
        comparable = [p for p in daily_points if p.get("sma200") is not None]
        above_points = [p for p in comparable if float(p.get("close") or 0.0) > float(p.get("sma200") or 0.0)]
        below_points = [p for p in comparable if float(p.get("close") or 0.0) <= float(p.get("sma200") or 0.0)]

        above_segments = self._segments_by_label(
            comparable,
            lambda p: "above_200" if float(p.get("close") or 0.0) > float(p.get("sma200") or 0.0) else "below_200",
            include={"above_200"},
        )
        below_segments = self._segments_by_label(
            comparable,
            lambda p: "above_200" if float(p.get("close") or 0.0) > float(p.get("sma200") or 0.0) else "below_200",
            include={"below_200"},
        )

        return {
            "regime_segments": regime_segments,
            "above_segments": above_segments,
            "below_segments": below_segments,
            "above_200_days": len(above_points),
            "below_200_days": len(below_points),
            "insufficient_regime_history_count": int(
                reject_reason_counts.get("insufficient_regime_history", 0)
            ),
            "above_200_return": round(self._compound_segment_returns(above_segments), 4),
            "below_200_return": round(self._compound_segment_returns(below_segments), 4),
        }

    def _segments_by_label(
        self,
        points: list[dict[str, object | None]],
        key_fn,
        include: set[str] | None = None,
    ) -> list[dict[str, object]]:
        if not points:
            return []
        out: list[dict[str, object]] = []
        current_label = key_fn(points[0])
        current_points = [points[0]]
        for point in points[1:]:
            label = key_fn(point)
            prev_ts = datetime.fromisoformat(str(current_points[-1].get("timestamp")))
            cur_ts = datetime.fromisoformat(str(point.get("timestamp")))
            contiguous = (cur_ts.date() - prev_ts.date()) <= timedelta(days=1)
            if label != current_label or not contiguous:
                if include is None or current_label in include:
                    out.append(self._to_segment(current_label, current_points))
                current_label = label
                current_points = [point]
            else:
                current_points.append(point)
        if include is None or current_label in include:
            out.append(self._to_segment(current_label, current_points))
        return out

    def _to_segment(self, label: str, points: list[dict[str, object | None]]) -> dict[str, object]:
        start_close = float(points[0].get("close") or 0.0)
        end_close = float(points[-1].get("close") or 0.0)
        segment_return = ((end_close - start_close) / max(start_close, 1e-9)) * 100
        distances = [
            float(item["distance_from_sma200_pct"])
            for item in points
            if item.get("distance_from_sma200_pct") is not None
        ]
        return {
            "label": label,
            "start_time": str(points[0].get("timestamp")),
            "end_time": str(points[-1].get("timestamp")),
            "days": len(points),
            "start_close": round(start_close, 6),
            "end_close": round(end_close, 6),
            "return_pct": round(segment_return, 4),
            "avg_distance_from_sma200_pct": round(mean(distances), 6) if distances else 0.0,
        }

    def _compound_segment_returns(self, segments: list[dict[str, object]]) -> float:
        if not segments:
            return 0.0
        equity = 1.0
        for segment in segments:
            equity *= 1 + (float(segment.get("return_pct") or 0.0) / 100)
        return (equity - 1) * 100

from collections import Counter
from dataclasses import dataclass
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
        progress_callback: Callable[[float], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        if not candles:
            raise ValueError("No candles provided")

        validated_params = strategy.validate_params(params)
        warmup = strategy.warmup_candles(validated_params)
        if len(candles) <= warmup:
            raise ValueError("Not enough candles for selected parameters")

        reject_reason_counts: Counter[str] = Counter()
        regime_counts: Counter[str] = Counter()

        position: Position | None = None
        trades: list[ClosedTrade] = []

        net_equity = 1.0
        gross_equity = 1.0
        net_equity_curve: list[float] = []
        gross_equity_curve: list[float] = []
        equity_points: list[dict[str, float | str]] = []

        total_fees_paid = 0.0
        total_slippage_cost = 0.0
        total_steps = len(candles) - warmup

        for idx in range(warmup, len(candles)):
            if should_stop and should_stop():
                raise BacktestCancelledError("Backtest cancelled")

            current = candles[idx]
            history = candles[: idx + 1]
            if strategy.uses_context():
                context = self._build_context(
                    symbol=(timeframe_bundle or {}).get("symbol", ""),
                    entry_candles=history,
                    as_of=current.timestamp,
                    timeframe_bundle=timeframe_bundle,
                )
                decision = strategy.evaluate_context(context, validated_params)
            else:
                decision = strategy.evaluate(history, validated_params)

            regime_counts[decision.regime] += 1
            if decision.reject_reason:
                reject_reason_counts[decision.reject_reason] += 1

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

                net_equity_curve.append(net_equity)
                gross_equity_curve.append(gross_equity)
                equity_points.append(
                    {
                        "timestamp": current.timestamp.isoformat(),
                        "equity": round(net_equity, 6),
                    }
                )
                if progress_callback:
                    step = idx - warmup + 1
                    progress_callback(15 + (step / max(total_steps, 1)) * 75)
                continue

            exit_reason: str | None = None
            if current.close <= position.stop_loss:
                exit_reason = "stop_loss"
            elif current.close >= position.take_profit:
                exit_reason = "take_profit"
            elif decision.regime == "bearish":
                exit_reason = "regime_reversal"
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

                slippage_entry_cost = max(position.entry_price - position.intended_entry_price, 0.0)
                slippage_exit_cost = max(intended_exit_price - filled_exit_price, 0.0)
                total_slippage = slippage_entry_cost + slippage_exit_cost

                total_fees = fee_entry + fee_exit
                total_cost = total_fees + total_slippage

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
                    )
                )
                position = None

            else:
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
                step = idx - warmup + 1
                progress_callback(15 + (step / max(total_steps, 1)) * 75)

        net_pnl_values = [trade.net_pnl for trade in trades]
        wins = [p for p in net_pnl_values if p > 0]
        losses = [p for p in net_pnl_values if p <= 0]

        gross_return_pct = (gross_equity - 1.0) * 100
        net_return_pct = (net_equity - 1.0) * 100
        total_trading_cost = total_fees_paid + total_slippage_cost

        summary = {
            "total_return_pct": round(net_return_pct, 4),
            "gross_return_pct": round(gross_return_pct, 4),
            "net_return_pct": round(net_return_pct, 4),
            "trade_count": len(trades),
            "win_rate": round((len(wins) / len(trades) * 100), 2) if trades else 0.0,
            "max_drawdown": round(self._max_drawdown(net_equity_curve), 4),
            "avg_profit": round(mean(wins), 4) if wins else 0.0,
            "avg_loss": round(mean(losses), 4) if losses else 0.0,
            "total_fees_paid": round(total_fees_paid, 6),
            "total_slippage_cost": round(total_slippage_cost, 6),
            "total_trading_cost": round(total_trading_cost, 6),
            "fee_impact_pct": round((total_fees_paid / max(1.0, abs(gross_return_pct))) * 100, 4),
            "slippage_impact_pct": round((total_slippage_cost / max(1.0, abs(gross_return_pct))) * 100, 4),
            "cost_drag_pct": round(gross_return_pct - net_return_pct, 4),
        }

        diagnostics = {
            "reject_reason_counts": dict(reject_reason_counts),
            "regime_counts": dict(regime_counts),
        }

        benchmark = self._benchmark(candles, warmup, execution.execution_policy, execution.benchmark_enabled, net_return_pct)

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
    ) -> StrategyContext:
        candles_by_role: dict[str, list[Candle]] = {}
        metadata_by_role: dict[str, dict] = {}
        mapping: dict[str, str] = {}
        if timeframe_bundle:
            for role, rows in timeframe_bundle.get("candles_by_role", {}).items():
                candles_by_role[role] = [c for c in rows if c.timestamp <= as_of]
            metadata_by_role = dict(timeframe_bundle.get("metadata_by_role", {}))
            mapping = dict(timeframe_bundle.get("mapping", {}))
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
        )

    def _benchmark(
        self,
        candles: list[Candle],
        warmup: int,
        execution_policy: str,
        enabled: bool,
        strategy_return_pct: float,
    ) -> dict | None:
        if not enabled or len(candles) <= warmup:
            return None

        start_idx = warmup
        if execution_policy == "next_open":
            start_idx = min(warmup + 1, len(candles) - 1)

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

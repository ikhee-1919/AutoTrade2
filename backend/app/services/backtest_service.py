from datetime import date, datetime, time, timedelta
import hashlib
import json
import subprocess
from typing import Any, Callable
from uuid import uuid4

from app.backtest.engine import BacktestCancelledError, BacktestEngine, BacktestExecutionConfig
from app.data.providers.csv_provider import CSVDataProvider
from app.repositories.backtest_run_repository import BacktestRunRepository
from app.schemas.backtest import BacktestRunRequest
from app.services.strategy_service import StrategyService


class BacktestService:
    def __init__(
        self,
        strategy_service: StrategyService,
        data_provider: CSVDataProvider,
        run_repository: BacktestRunRepository,
        engine: BacktestEngine,
        project_root: str | None = None,
    ) -> None:
        self._strategy_service = strategy_service
        self._data_provider = data_provider
        self._run_repository = run_repository
        self._engine = engine
        self._project_root = project_root

    def run(
        self,
        request: BacktestRunRequest,
        rerun_of_run_id: str | None = None,
        progress_callback: Callable[[float], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> dict:
        strategy = self._strategy_service.get_strategy(request.strategy_id)
        strategy_meta = strategy.metadata()
        code_version = self._detect_code_version()
        base_params = self._strategy_service.get_effective_params(request.strategy_id)
        param_overrides = request.params or {}
        params = strategy.validate_params(base_params | param_overrides)
        execution_config = self._resolve_execution_config(request)
        timeframe_mapping = self._resolve_timeframe_mapping(strategy, request)
        entry_timeframe = timeframe_mapping.get("entry", request.timeframe)
        trade_start = request.start_date
        trade_end = request.end_date
        indicator_start = self._resolve_indicator_start(
            request=request,
            strategy=strategy,
            params=params,
            timeframe_mapping=timeframe_mapping,
        )
        params_snapshot = {
            "strategy_params": dict(params),
            "execution_config": execution_config,
            "timeframe_mapping": timeframe_mapping,
            "indicator_start": indicator_start.isoformat(),
            "trade_start": trade_start.isoformat(),
            "trade_end": trade_end.isoformat(),
        }
        if progress_callback:
            progress_callback(5)
        if should_cancel and should_cancel():
            raise BacktestCancelledError("Backtest cancelled before data load")

        bundle = self._data_provider.load_timeframe_bundle(
            symbol=request.symbol,
            timeframe_mapping=timeframe_mapping,
            start_date=indicator_start,
            end_date=trade_end,
        )
        candles = bundle["candles_by_role"].get("entry", [])
        selected_datasets_by_role = self._build_selected_datasets_by_role(bundle.get("metadata_by_role", {}), timeframe_mapping)
        if not candles:
            entry_meta = (bundle.get("metadata_by_role", {}) or {}).get("entry", {}) or {}
            source_type = entry_meta.get("source_type", "unknown")
            dataset_id = entry_meta.get("dataset_id", "unknown")
            raise ValueError(
                "No candles found for selected period/symbol/timeframe. "
                f"symbol={request.symbol}, timeframe={entry_timeframe}, "
                f"period={trade_start.isoformat()}~{trade_end.isoformat()}, "
                f"source={source_type}, dataset_id={dataset_id}"
            )

        if progress_callback:
            progress_callback(12)
        if should_cancel and should_cancel():
            raise BacktestCancelledError("Backtest cancelled before engine run")
        result = self._engine.run(
            candles=candles,
            strategy=strategy,
            params=params,
            execution=BacktestExecutionConfig(**execution_config),
            timeframe_bundle=bundle,
            trade_start_at=datetime.combine(trade_start, time.min),
            progress_callback=progress_callback,
            should_stop=should_cancel,
        )
        if progress_callback:
            progress_callback(95)
        params_hash = self._compute_params_hash(
            {"strategy_params": params, "timeframe_mapping": timeframe_mapping}
        )
        provider_meta = bundle.get("metadata_by_role", {}).get("entry")
        data_signature = self._compute_data_signature(candles, provider_meta=provider_meta)

        run_id = uuid4().hex
        run_at = datetime.utcnow()
        response = {
            "run_id": run_id,
            "rerun_of_run_id": rerun_of_run_id,
            "run_at": run_at,
            "strategy_id": request.strategy_id,
            "strategy_version": strategy_meta.version,
            "code_version": code_version,
            "symbol": request.symbol,
            "timeframe": entry_timeframe,
            "timeframe_mapping": timeframe_mapping,
            "indicator_start": indicator_start,
            "warmup_start": indicator_start,
            "warmup_days": request.warmup_days,
            "trade_start": trade_start,
            "trade_end": trade_end,
            "start_date": trade_start,
            "end_date": trade_end,
            "params_used": params,
            "params_snapshot": params_snapshot,
            "params_hash": params_hash,
            "data_signature": data_signature,
            "selected_datasets_by_role": selected_datasets_by_role,
            "execution_config": execution_config,
            "run_tag": request.run_tag,
            "note": request.note,
            **result,
        }

        self._run_repository.save_run(
            {
                "run_id": run_id,
                "rerun_of_run_id": rerun_of_run_id,
                "run_at": run_at.isoformat(),
                "strategy_id": request.strategy_id,
                "strategy_version": strategy_meta.version,
                "code_version": code_version,
                "symbol": request.symbol,
                "timeframe": entry_timeframe,
                "timeframe_mapping": timeframe_mapping,
                "indicator_start": indicator_start.isoformat(),
                "warmup_start": indicator_start.isoformat(),
                "warmup_days": request.warmup_days,
                "trade_start": trade_start.isoformat(),
                "trade_end": trade_end.isoformat(),
                "start_date": trade_start.isoformat(),
                "end_date": trade_end.isoformat(),
                "params_used": params,
                "params_snapshot": params_snapshot,
                "params_hash": params_hash,
                "data_signature": data_signature,
                "selected_datasets_by_role": selected_datasets_by_role,
                "execution_config": execution_config,
                "run_tag": request.run_tag,
                "note": request.note,
                "summary": result["summary"],
                "benchmark": result.get("benchmark"),
                "trades": result["trades"],
                "diagnostics": result["diagnostics"],
                "equity_curve": result.get("equity_curve", []),
            }
        )
        if progress_callback:
            progress_callback(100)
        return response

    def rerun(self, run_id: str) -> dict:
        previous = self._run_repository.get_by_id(run_id)
        if previous is None:
            raise ValueError(f"run_id not found: {run_id}")

        request = BacktestRunRequest(
            strategy_id=previous["strategy_id"],
            symbol=previous["symbol"],
            timeframe=previous["timeframe"],
            timeframe_mapping=previous.get("timeframe_mapping"),
            start_date=datetime.fromisoformat(previous["start_date"]).date(),
            end_date=datetime.fromisoformat(previous["end_date"]).date(),
            indicator_start=(
                datetime.fromisoformat(previous["indicator_start"]).date()
                if previous.get("indicator_start")
                else None
            ),
            warmup_days=previous.get("warmup_days"),
            params=previous.get("params_used", {}),
            run_tag=previous.get("run_tag"),
            note=f"rerun of {run_id}",
            fee_rate=previous.get("execution_config", {}).get("fee_rate", 0.0005),
            entry_fee_rate=previous.get("execution_config", {}).get("entry_fee_rate"),
            exit_fee_rate=previous.get("execution_config", {}).get("exit_fee_rate"),
            apply_fee_on_entry=previous.get("execution_config", {}).get("apply_fee_on_entry", True),
            apply_fee_on_exit=previous.get("execution_config", {}).get("apply_fee_on_exit", True),
            slippage_rate=previous.get("execution_config", {}).get("slippage_rate", 0.0003),
            entry_slippage_rate=previous.get("execution_config", {}).get("entry_slippage_rate"),
            exit_slippage_rate=previous.get("execution_config", {}).get("exit_slippage_rate"),
            execution_policy=previous.get("execution_config", {}).get("execution_policy", "next_open"),
            benchmark_enabled=previous.get("execution_config", {}).get("benchmark_enabled", True),
        )
        response = self.run(request, rerun_of_run_id=run_id)
        return response

    def recent_runs(self, limit: int = 5) -> list[dict]:
        return self._run_repository.get_recent(limit=limit)

    def get_run_detail(self, run_id: str) -> dict:
        run = self._run_repository.get_by_id(run_id)
        if run is None:
            raise ValueError(f"run_id not found: {run_id}")

        return {
            "run_id": run["run_id"],
            "rerun_of_run_id": run.get("rerun_of_run_id"),
            "run_at": datetime.fromisoformat(run["run_at"]),
            "strategy_id": run["strategy_id"],
            "strategy_version": run.get("strategy_version", "unknown"),
            "code_version": run.get("code_version", "unknown"),
            "symbol": run["symbol"],
            "timeframe": run["timeframe"],
            "timeframe_mapping": run.get("timeframe_mapping"),
            "indicator_start": (
                datetime.fromisoformat(run["indicator_start"]).date()
                if run.get("indicator_start")
                else None
            ),
            "warmup_start": (
                datetime.fromisoformat(run["warmup_start"]).date()
                if run.get("warmup_start")
                else None
            ),
            "trade_start": (
                datetime.fromisoformat(run["trade_start"]).date()
                if run.get("trade_start")
                else datetime.fromisoformat(run["start_date"]).date()
            ),
            "trade_end": (
                datetime.fromisoformat(run["trade_end"]).date()
                if run.get("trade_end")
                else datetime.fromisoformat(run["end_date"]).date()
            ),
            "start_date": datetime.fromisoformat(run["start_date"]).date(),
            "end_date": datetime.fromisoformat(run["end_date"]).date(),
            "params_used": run.get("params_used", {}),
            "params_snapshot": run.get("params_snapshot", run.get("params_used", {})),
            "params_hash": run.get("params_hash", ""),
            "data_signature": run.get(
                "data_signature",
                {
                    "source": "csv",
                    "candle_count": 0,
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "candles_hash": "",
                    "dataset_id": None,
                    "dataset_signature": None,
                },
            ),
            "selected_datasets_by_role": run.get("selected_datasets_by_role", {}),
            "execution_config": run.get(
                "execution_config",
                self._default_execution_config(),
            ),
            "run_tag": run.get("run_tag"),
            "note": run.get("note"),
            "summary": run.get(
                "summary",
                {
                    "total_return_pct": 0.0,
                    "gross_return_pct": 0.0,
                    "net_return_pct": 0.0,
                    "buy_and_hold_return_pct": 0.0,
                    "excess_return_vs_buy_and_hold": 0.0,
                    "trade_count": 0,
                    "win_rate": 0.0,
                    "max_drawdown": 0.0,
                    "avg_profit": 0.0,
                    "avg_loss": 0.0,
                    "profit_factor": 0.0,
                    "avg_win_pct": 0.0,
                    "avg_loss_pct": 0.0,
                    "expectancy_per_trade": 0.0,
                    "max_consecutive_losses": 0,
                    "avg_holding_time": 0.0,
                    "exposure_pct": 0.0,
                    "total_fees_paid": 0.0,
                    "total_slippage_cost": 0.0,
                    "total_trading_cost": 0.0,
                    "fee_total": 0.0,
                    "slippage_total": 0.0,
                    "fee_impact_pct": 0.0,
                    "slippage_impact_pct": 0.0,
                    "cost_drag_pct": 0.0,
                    "exit_reason_counts": {},
                    "reject_reason_counts": {},
                    "regime_counts": {},
                    "regime_segment_summaries": [],
                    "above_200_days": 0,
                    "below_200_days": 0,
                    "insufficient_regime_history_count": 0,
                    "above_200_return": 0.0,
                    "below_200_return": 0.0,
                    "monthly_returns": [],
                },
            ),
            "benchmark": run.get(
                "benchmark",
                {
                    "benchmark_buy_and_hold_return_pct": 0.0,
                    "strategy_excess_return_pct": 0.0,
                    "benchmark_start_price": 0.0,
                    "benchmark_end_price": 0.0,
                    "benchmark_curve": [],
                },
            ),
            "trades": run.get("trades", []),
            "diagnostics": run.get(
                "diagnostics",
                {
                    "reject_reason_counts": {},
                    "regime_counts": {},
                    "exit_reason_counts": {},
                    "regime_segment_summaries": [],
                    "above_200_segments": [],
                    "below_200_segments": [],
                    "above_200_days": 0,
                    "below_200_days": 0,
                    "insufficient_regime_history_count": 0,
                    "above_200_return": 0.0,
                    "below_200_return": 0.0,
                },
            ),
            "equity_curve": run.get("equity_curve", []),
        }

    def compare_runs(self, run_ids: list[str]) -> list[dict]:
        if len(run_ids) < 2:
            raise ValueError("At least 2 run_ids are required for comparison")

        runs = self._run_repository.get_by_ids(run_ids)
        if len(runs) < 2:
            raise ValueError("Could not find enough runs for comparison")

        runs_sorted = sorted(
            runs,
            key=lambda item: item.get("summary", {}).get(
                "net_return_pct",
                item.get("summary", {}).get("total_return_pct", 0.0),
            ),
            reverse=True,
        )
        best = runs_sorted[0]
        best_return = best.get("summary", {}).get(
            "net_return_pct",
            best.get("summary", {}).get("total_return_pct", 0.0),
        )
        best_mdd = best["summary"]["max_drawdown"]

        compared: list[dict] = []
        for run in runs_sorted:
            summary = run["summary"]
            compared.append(
                {
                    "run_id": run["run_id"],
                    "run_at": datetime.fromisoformat(run["run_at"]),
                    "strategy_id": run["strategy_id"],
                    "strategy_version": run.get("strategy_version", "unknown"),
                    "code_version": run.get("code_version", "unknown"),
                    "symbol": run["symbol"],
                    "timeframe": run["timeframe"],
                    "timeframe_mapping": run.get("timeframe_mapping"),
                    "timeframe_mapping_summary": self._mapping_summary(run.get("timeframe_mapping")),
                    "indicator_start": run.get("indicator_start"),
                    "warmup_start": run.get("warmup_start"),
                    "trade_start": run.get("trade_start", run.get("start_date")),
                    "trade_end": run.get("trade_end", run.get("end_date")),
                    "start_date": run["start_date"],
                    "end_date": run["end_date"],
                    "summary_avg_profit": summary.get("avg_profit", 0.0),
                    "summary_avg_loss": summary.get("avg_loss", 0.0),
                    "profit_factor": summary.get("profit_factor", 0.0),
                    "avg_win_pct": summary.get("avg_win_pct", summary.get("avg_profit", 0.0)),
                    "avg_loss_pct": summary.get("avg_loss_pct", summary.get("avg_loss", 0.0)),
                    "expectancy_per_trade": summary.get("expectancy_per_trade", 0.0),
                    "max_consecutive_losses": summary.get("max_consecutive_losses", 0),
                    "avg_holding_time": summary.get("avg_holding_time", 0.0),
                    "exposure_pct": summary.get("exposure_pct", 0.0),
                    "gross_return_pct": summary.get("gross_return_pct", summary.get("total_return_pct", 0.0)),
                    "net_return_pct": summary.get("net_return_pct", summary.get("total_return_pct", 0.0)),
                    "total_fees_paid": summary.get("total_fees_paid", 0.0),
                    "total_slippage_cost": summary.get("total_slippage_cost", 0.0),
                    "total_trading_cost": summary.get("total_trading_cost", 0.0),
                    "fee_total": summary.get("fee_total", summary.get("total_fees_paid", 0.0)),
                    "slippage_total": summary.get("slippage_total", summary.get("total_slippage_cost", 0.0)),
                    "cost_drag_pct": summary.get("cost_drag_pct", 0.0),
                    "benchmark_buy_and_hold_return_pct": run.get("benchmark", {}).get("benchmark_buy_and_hold_return_pct", 0.0),
                    "strategy_excess_return_pct": run.get("benchmark", {}).get("strategy_excess_return_pct", 0.0),
                    "exit_reason_counts": summary.get(
                        "exit_reason_counts",
                        run.get("diagnostics", {}).get("exit_reason_counts", {}),
                    ),
                    "reject_reason_counts": summary.get(
                        "reject_reason_counts",
                        run.get("diagnostics", {}).get("reject_reason_counts", {}),
                    ),
                    "regime_counts": summary.get(
                        "regime_counts",
                        run.get("diagnostics", {}).get("regime_counts", {}),
                    ),
                    "above_200_days": summary.get("above_200_days", 0),
                    "below_200_days": summary.get("below_200_days", 0),
                    "insufficient_regime_history_count": summary.get(
                        "insufficient_regime_history_count",
                        run.get("diagnostics", {}).get("insufficient_regime_history_count", 0),
                    ),
                    "above_200_return": summary.get("above_200_return", 0.0),
                    "below_200_return": summary.get("below_200_return", 0.0),
                    "top_reject_reason": self._top_key(
                        run.get("diagnostics", {}).get("reject_reason_counts", {})
                    ),
                    "params_hash": run.get("params_hash", ""),
                    "data_signature": run.get(
                        "data_signature",
                        {
                            "source": "csv",
                            "candle_count": 0,
                            "first_timestamp": None,
                            "last_timestamp": None,
                            "candles_hash": "",
                            "dataset_id": None,
                            "dataset_signature": None,
                        },
                    ),
                    "total_return_pct": summary.get("total_return_pct", summary.get("net_return_pct", 0.0)),
                    "max_drawdown": summary["max_drawdown"],
                    "win_rate": summary["win_rate"],
                    "trade_count": summary["trade_count"],
                    "return_gap_vs_best": round(summary.get("net_return_pct", summary.get("total_return_pct", 0.0)) - best_return, 4),
                    "mdd_gap_vs_best": round(summary["max_drawdown"] - best_mdd, 4),
                    "run_tag": run.get("run_tag"),
                }
            )

        return compared

    def _detect_code_version(self) -> str:
        try:
            cmd = ["git", "rev-parse", "--short", "HEAD"]
            output = subprocess.check_output(
                cmd,
                cwd=self._project_root,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return output.strip() or "unknown-local"
        except Exception:  # noqa: BLE001 - metadata fallback only
            return "unknown-local"

    def _compute_params_hash(self, params: dict) -> str:
        payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _resolve_execution_config(self, request: BacktestRunRequest) -> dict:
        entry_fee = request.entry_fee_rate if request.entry_fee_rate is not None else request.fee_rate
        exit_fee = request.exit_fee_rate if request.exit_fee_rate is not None else request.fee_rate
        entry_slip = (
            request.entry_slippage_rate
            if request.entry_slippage_rate is not None
            else request.slippage_rate
        )
        exit_slip = (
            request.exit_slippage_rate
            if request.exit_slippage_rate is not None
            else request.slippage_rate
        )

        return {
            "execution_policy": request.execution_policy,
            "fee_rate": request.fee_rate,
            "entry_fee_rate": entry_fee,
            "exit_fee_rate": exit_fee,
            "apply_fee_on_entry": request.apply_fee_on_entry,
            "apply_fee_on_exit": request.apply_fee_on_exit,
            "slippage_rate": request.slippage_rate,
            "entry_slippage_rate": entry_slip,
            "exit_slippage_rate": exit_slip,
            "benchmark_enabled": request.benchmark_enabled,
        }

    def _resolve_timeframe_mapping(self, strategy, request: BacktestRunRequest) -> dict[str, str]:
        raw_mapping = dict(request.timeframe_mapping or {})
        if not raw_mapping:
            raw_mapping = dict(strategy.default_timeframe_mapping() or {})
        if not raw_mapping:
            raw_mapping = {"entry": request.timeframe}

        normalized = {
            role: self._data_provider.normalize_timeframe(tf)
            for role, tf in raw_mapping.items()
        }
        required = strategy.required_timeframe_roles()
        missing = [role for role in required if role not in normalized]
        if missing:
            raise ValueError(f"Missing required timeframe roles: {', '.join(missing)}")
        if "entry" not in normalized:
            normalized["entry"] = self._data_provider.normalize_timeframe(request.timeframe)
        return normalized

    def _default_execution_config(self) -> dict:
        return {
            "execution_policy": "next_open",
            "fee_rate": 0.0005,
            "entry_fee_rate": 0.0005,
            "exit_fee_rate": 0.0005,
            "apply_fee_on_entry": True,
            "apply_fee_on_exit": True,
            "slippage_rate": 0.0003,
            "entry_slippage_rate": 0.0003,
            "exit_slippage_rate": 0.0003,
            "benchmark_enabled": True,
        }

    def _compute_data_signature(self, candles: list, provider_meta: dict | None = None) -> dict:
        if not candles:
            return {
                "source": "csv",
                "candle_count": 0,
                "first_timestamp": None,
                "last_timestamp": None,
                "candles_hash": "",
                "dataset_id": provider_meta.get("dataset_id") if provider_meta else None,
                "dataset_signature": provider_meta.get("data_signature") if provider_meta else None,
            }

        compact_rows = [
            [c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume] for c in candles
        ]
        serialized = json.dumps(compact_rows, separators=(",", ":"))
        candles_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return {
            "source": provider_meta.get("source_type", "csv") if provider_meta else "csv",
            "candle_count": len(candles),
            "first_timestamp": candles[0].timestamp.isoformat(),
            "last_timestamp": candles[-1].timestamp.isoformat(),
            "candles_hash": candles_hash,
            "dataset_id": provider_meta.get("dataset_id") if provider_meta else None,
            "dataset_signature": provider_meta.get("data_signature") if provider_meta else None,
        }

    def _top_key(self, payload: dict) -> str | None:
        if not payload:
            return None
        return max(payload, key=payload.get)

    def _build_selected_datasets_by_role(
        self,
        metadata_by_role: dict[str, dict[str, Any]],
        timeframe_mapping: dict[str, str],
    ) -> dict[str, dict[str, Any]]:
        selections: dict[str, dict[str, Any]] = {}
        for role, timeframe in timeframe_mapping.items():
            meta = metadata_by_role.get(role, {})
            selections[role] = {
                "role": role,
                "timeframe": timeframe,
                "source_type": meta.get("source_type", "unknown"),
                "dataset_id": meta.get("dataset_id"),
                "dataset_signature": meta.get("data_signature"),
                "quality_status": meta.get("quality_status"),
            }
        return selections

    def _mapping_summary(self, mapping: dict[str, str] | None) -> str | None:
        if not mapping:
            return None
        return ", ".join(f"{role}:{tf}" for role, tf in sorted(mapping.items()))

    def _resolve_indicator_start(
        self,
        request: BacktestRunRequest,
        strategy,
        params: dict,
        timeframe_mapping: dict[str, str],
    ) -> date:
        if request.indicator_start is not None:
            if request.indicator_start > request.start_date:
                raise ValueError("indicator_start must be <= start_date")
            return request.indicator_start

        explicit_warmup_days = request.warmup_days if request.warmup_days is not None else None
        has_daily_role = any(tf == "1d" for tf in timeframe_mapping.values())
        strategy_warmup = max(0, int(strategy.warmup_candles(params)))
        baseline_days = 30
        if has_daily_role:
            baseline_days = 400
        elif timeframe_mapping.get("entry") in {"1w", "1mo", "1y"}:
            baseline_days = 365
        warmup_days = explicit_warmup_days if explicit_warmup_days is not None else max(baseline_days, strategy_warmup)
        return request.start_date - timedelta(days=warmup_days)

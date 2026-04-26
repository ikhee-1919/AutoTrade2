from datetime import datetime
import hashlib
import itertools
import json
import statistics
import subprocess
from typing import Any, Callable
from uuid import uuid4

from app.repositories.sweep_run_repository import SweepRunRepository
from app.schemas.backtest import BacktestRunRequest
from app.schemas.sweep import SweepRunRequest
from app.services.backtest_service import BacktestService
from app.services.strategy_service import StrategyService


class ParameterSweepService:
    def __init__(
        self,
        strategy_service: StrategyService,
        backtest_service: BacktestService,
        sweep_repository: SweepRunRepository,
        project_root: str | None = None,
    ) -> None:
        self._strategy_service = strategy_service
        self._backtest_service = backtest_service
        self._sweep_repository = sweep_repository
        self._project_root = project_root

    def run(
        self,
        request: SweepRunRequest,
        rerun_of_sweep_run_id: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        strategy = self._strategy_service.get_strategy(request.strategy_id)
        strategy_meta = strategy.metadata()
        code_version = self._detect_code_version()
        execution_config = self._resolve_execution_config(request)
        timeframe_mapping = self._resolve_timeframe_mapping(strategy, request)
        combinations = self._build_combinations(request.sweep_space)

        results: list[dict[str, Any]] = []
        total = len(combinations)
        completed = 0
        failed = 0
        if progress_callback:
            progress_callback(0, total)

        for idx, params in enumerate(combinations):
            try:
                run_result = self._backtest_service.run(
                    BacktestRunRequest(
                        strategy_id=request.strategy_id,
                        symbol=request.symbol,
                        timeframe=timeframe_mapping.get("entry", request.timeframe),
                        timeframe_mapping=timeframe_mapping,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        params=params,
                        fee_rate=request.fee_rate,
                        entry_fee_rate=request.entry_fee_rate,
                        exit_fee_rate=request.exit_fee_rate,
                        apply_fee_on_entry=request.apply_fee_on_entry,
                        apply_fee_on_exit=request.apply_fee_on_exit,
                        slippage_rate=request.slippage_rate,
                        entry_slippage_rate=request.entry_slippage_rate,
                        exit_slippage_rate=request.exit_slippage_rate,
                        execution_policy=request.execution_policy,
                        benchmark_enabled=request.benchmark_enabled,
                        run_tag=request.run_tag,
                        note=request.note,
                    )
                )
                summary = run_result["summary"]
                benchmark = run_result.get("benchmark", {}) or {}
                results.append(
                    {
                        "combination_id": f"combo_{idx + 1}",
                        "params_snapshot": params,
                        "related_run_id": run_result["run_id"],
                        "gross_return_pct": summary.get("gross_return_pct", summary.get("total_return_pct", 0.0)),
                        "net_return_pct": summary.get("net_return_pct", summary.get("total_return_pct", 0.0)),
                        "max_drawdown": summary.get("max_drawdown", 0.0),
                        "trade_count": summary.get("trade_count", 0),
                        "win_rate": summary.get("win_rate", 0.0),
                        "profit_factor": summary.get("profit_factor", 0.0),
                        "avg_win_pct": summary.get("avg_win_pct", 0.0),
                        "avg_loss_pct": summary.get("avg_loss_pct", 0.0),
                        "max_consecutive_losses": summary.get("max_consecutive_losses", 0),
                        "benchmark_buy_and_hold_return_pct": benchmark.get("benchmark_buy_and_hold_return_pct", 0.0),
                        "excess_return_pct": benchmark.get("strategy_excess_return_pct", 0.0),
                        "status": "completed",
                        "error_summary": None,
                    }
                )
                completed += 1
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "combination_id": f"combo_{idx + 1}",
                        "params_snapshot": params,
                        "related_run_id": None,
                        "gross_return_pct": 0.0,
                        "net_return_pct": 0.0,
                        "max_drawdown": 0.0,
                        "trade_count": 0,
                        "win_rate": 0.0,
                        "profit_factor": 0.0,
                        "avg_win_pct": 0.0,
                        "avg_loss_pct": 0.0,
                        "max_consecutive_losses": 0,
                        "benchmark_buy_and_hold_return_pct": 0.0,
                        "excess_return_pct": 0.0,
                        "status": "failed",
                        "error_summary": str(exc)[:300],
                    }
                )
                failed += 1
            if progress_callback:
                progress_callback(idx + 1, total)

        ranking_summary = self._build_ranking_summary(results)
        created_at = datetime.utcnow()
        sweep_run_id = uuid4().hex
        request_payload = request.model_dump(mode="json")
        request_hash = self._hash_request(request_payload)
        response = {
            "sweep_run_id": sweep_run_id,
            "rerun_of_sweep_run_id": rerun_of_sweep_run_id,
            "request_hash": request_hash,
            "created_at": created_at,
            "strategy_id": request.strategy_id,
            "strategy_version": strategy_meta.version,
            "code_version": code_version,
            "symbol": request.symbol,
            "timeframe": timeframe_mapping.get("entry", request.timeframe),
            "timeframe_mapping": timeframe_mapping,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "execution_config": execution_config,
            "benchmark_enabled": request.benchmark_enabled,
            "sweep_space": request.sweep_space,
            "total_combinations": total,
            "completed_combinations": completed,
            "failed_combinations": failed,
            "run_tag": request.run_tag,
            "note": request.note,
            "ranking_summary": ranking_summary,
            "results": results,
        }
        self._sweep_repository.save_run(
            {
                **response,
                "created_at": created_at.isoformat(),
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
            }
        )
        return response

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        runs = self._sweep_repository.get_recent(limit=limit)
        items: list[dict[str, Any]] = []
        for run in runs:
            ranking = run.get("ranking_summary", {})
            items.append(
                {
                    "sweep_run_id": run["sweep_run_id"],
                    "created_at": datetime.fromisoformat(run["created_at"]),
                    "strategy_id": run["strategy_id"],
                    "strategy_version": run.get("strategy_version", "unknown"),
                    "symbol": run["symbol"],
                    "timeframe": run["timeframe"],
                    "timeframe_mapping": run.get("timeframe_mapping"),
                    "total_combinations": run.get("total_combinations", 0),
                    "completed_combinations": run.get("completed_combinations", 0),
                    "failed_combinations": run.get("failed_combinations", 0),
                    "top_net_return_pct": (ranking.get("best_by_net_return") or {}).get("net_return_pct", 0.0),
                    "average_net_return": ranking.get("average_net_return", 0.0),
                }
            )
        return items

    def get_run_detail(self, sweep_run_id: str) -> dict[str, Any]:
        run = self._sweep_repository.get_by_id(sweep_run_id)
        if run is None:
            raise ValueError(f"sweep_run_id not found: {sweep_run_id}")
        return {
            **run,
            "created_at": datetime.fromisoformat(run["created_at"]),
            "start_date": datetime.fromisoformat(run["start_date"]).date(),
            "end_date": datetime.fromisoformat(run["end_date"]).date(),
        }

    def rerun(self, sweep_run_id: str) -> dict[str, Any]:
        previous = self._sweep_repository.get_by_id(sweep_run_id)
        if previous is None:
            raise ValueError(f"sweep_run_id not found: {sweep_run_id}")
        request = SweepRunRequest(
            strategy_id=previous["strategy_id"],
            symbol=previous["symbol"],
            timeframe=previous["timeframe"],
            timeframe_mapping=previous.get("timeframe_mapping"),
            start_date=datetime.fromisoformat(previous["start_date"]).date(),
            end_date=datetime.fromisoformat(previous["end_date"]).date(),
            sweep_space=previous.get("sweep_space", {}),
            benchmark_enabled=previous.get("benchmark_enabled", True),
            fee_rate=previous.get("execution_config", {}).get("fee_rate", 0.0005),
            entry_fee_rate=previous.get("execution_config", {}).get("entry_fee_rate"),
            exit_fee_rate=previous.get("execution_config", {}).get("exit_fee_rate"),
            apply_fee_on_entry=previous.get("execution_config", {}).get("apply_fee_on_entry", True),
            apply_fee_on_exit=previous.get("execution_config", {}).get("apply_fee_on_exit", True),
            slippage_rate=previous.get("execution_config", {}).get("slippage_rate", 0.0003),
            entry_slippage_rate=previous.get("execution_config", {}).get("entry_slippage_rate"),
            exit_slippage_rate=previous.get("execution_config", {}).get("exit_slippage_rate"),
            execution_policy=previous.get("execution_config", {}).get("execution_policy", "next_open"),
            run_tag=previous.get("run_tag"),
            note=f"rerun of sweep {sweep_run_id}",
            use_job=False,
        )
        return self.run(request, rerun_of_sweep_run_id=sweep_run_id)

    def get_results(self, sweep_run_id: str) -> list[dict[str, Any]]:
        run = self._sweep_repository.get_by_id(sweep_run_id)
        if run is None:
            raise ValueError(f"sweep_run_id not found: {sweep_run_id}")
        return run.get("results", [])

    def get_top(
        self,
        sweep_run_id: str,
        limit: int = 10,
        sort_by: str = "net_return_pct",
    ) -> list[dict[str, Any]]:
        results = self.get_results(sweep_run_id)
        completed = [item for item in results if item.get("status") == "completed"]
        return sorted(completed, key=lambda r: float(r.get(sort_by, 0.0)), reverse=True)[:limit]

    def build_request_hash(self, request: SweepRunRequest) -> str:
        return self._hash_request(request.model_dump(mode="json"))

    def _resolve_execution_config(self, request: SweepRunRequest) -> dict[str, Any]:
        entry_fee = request.entry_fee_rate if request.entry_fee_rate is not None else request.fee_rate
        exit_fee = request.exit_fee_rate if request.exit_fee_rate is not None else request.fee_rate
        entry_slip = request.entry_slippage_rate if request.entry_slippage_rate is not None else request.slippage_rate
        exit_slip = request.exit_slippage_rate if request.exit_slippage_rate is not None else request.slippage_rate
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

    def _resolve_timeframe_mapping(self, strategy, request: SweepRunRequest) -> dict[str, str]:
        mapping = dict(request.timeframe_mapping or strategy.default_timeframe_mapping() or {})
        if not mapping:
            mapping = {"entry": request.timeframe}
        normalized: dict[str, str] = {}
        for role, timeframe in mapping.items():
            normalized[role] = self._backtest_service._data_provider.normalize_timeframe(timeframe)  # noqa: SLF001
        required = strategy.required_timeframe_roles()
        missing = [role for role in required if role not in normalized]
        if missing:
            raise ValueError(f"Missing required timeframe roles: {', '.join(missing)}")
        if "entry" not in normalized:
            normalized["entry"] = self._backtest_service._data_provider.normalize_timeframe(request.timeframe)  # noqa: SLF001
        return normalized

    def _build_combinations(self, sweep_space: dict[str, list[float | int | str]]) -> list[dict[str, Any]]:
        if not sweep_space:
            return [{}]
        keys = sorted(sweep_space.keys())
        values_grid: list[list[float | int | str]] = []
        for key in keys:
            values = sweep_space[key]
            if not isinstance(values, list) or len(values) == 0:
                raise ValueError(f"sweep_space[{key}] must be a non-empty list")
            values_grid.append(values)
        combos: list[dict[str, Any]] = []
        for values in itertools.product(*values_grid):
            combos.append({key: value for key, value in zip(keys, values)})
        return combos

    def _build_ranking_summary(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        completed = [item for item in results if item.get("status") == "completed"]
        if not completed:
            return {
                "best_by_net_return": None,
                "best_by_excess_return": None,
                "lowest_drawdown_group": [],
                "top_n": [],
                "profitable_count": 0,
                "losing_count": 0,
                "average_net_return": 0.0,
                "median_net_return": 0.0,
                "average_max_drawdown": 0.0,
            }
        by_net = sorted(completed, key=lambda r: float(r.get("net_return_pct", 0.0)), reverse=True)
        by_excess = sorted(completed, key=lambda r: float(r.get("excess_return_pct", 0.0)), reverse=True)
        by_mdd = sorted(completed, key=lambda r: float(r.get("max_drawdown", 0.0)))
        net_values = [float(item.get("net_return_pct", 0.0)) for item in completed]
        mdd_values = [float(item.get("max_drawdown", 0.0)) for item in completed]
        profitable_count = sum(1 for value in net_values if value > 0)
        return {
            "best_by_net_return": by_net[0],
            "best_by_excess_return": by_excess[0],
            "lowest_drawdown_group": by_mdd[: min(5, len(by_mdd))],
            "top_n": by_net[: min(10, len(by_net))],
            "profitable_count": profitable_count,
            "losing_count": len(completed) - profitable_count,
            "average_net_return": round(statistics.mean(net_values), 4),
            "median_net_return": round(statistics.median(net_values), 4),
            "average_max_drawdown": round(statistics.mean(mdd_values), 4),
        }

    def _hash_request(self, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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
        except Exception:  # noqa: BLE001
            return "unknown-local"

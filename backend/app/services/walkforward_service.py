from datetime import datetime
import hashlib
import json
from statistics import mean, median
import subprocess
from typing import Callable
from uuid import uuid4

from app.data.providers.csv_provider import CSVDataProvider
from app.repositories.walkforward_run_repository import WalkforwardRunRepository
from app.schemas.backtest import BacktestRunRequest
from app.schemas.walkforward import WalkforwardRunRequest
from app.services.backtest_service import BacktestService
from app.services.strategy_service import StrategyService


class WalkforwardService:
    def __init__(
        self,
        strategy_service: StrategyService,
        data_provider: CSVDataProvider,
        backtest_service: BacktestService,
        walkforward_repository: WalkforwardRunRepository,
        project_root: str | None = None,
    ) -> None:
        self._strategy_service = strategy_service
        self._data_provider = data_provider
        self._backtest_service = backtest_service
        self._walkforward_repository = walkforward_repository
        self._project_root = project_root

    def run(
        self,
        request: WalkforwardRunRequest,
        rerun_of_walkforward_run_id: str | None = None,
        progress_callback: Callable[[int, int, int | None], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> dict:
        strategy = self._strategy_service.get_strategy(request.strategy_id)
        strategy_meta = strategy.metadata()
        code_version = self._detect_code_version()

        base_params = self._strategy_service.get_effective_params(request.strategy_id)
        params = strategy.validate_params(base_params | (request.params or {}))
        execution_config = self._resolve_execution_config(request)
        warmup_needed = strategy.warmup_candles(params)
        timeframe_mapping = self._resolve_timeframe_mapping(strategy, request)
        entry_timeframe = timeframe_mapping.get("entry", request.timeframe)

        candles = self._data_provider.load_ohlcv(
            symbol=request.symbol,
            timeframe=entry_timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        segments = self.build_segments(
            candles,
            train_window_size=request.train_window_size,
            test_window_size=request.test_window_size,
            step_size=request.step_size,
            window_unit=request.window_unit,
            walkforward_mode=request.walkforward_mode,
        )
        if len(segments) < 1:
            raise ValueError("No walk-forward segments generated. Adjust period/window settings.")

        if progress_callback:
            progress_callback(0, len(segments), None)

        segment_results: list[dict] = []
        for idx, seg in enumerate(segments):
            if should_cancel and should_cancel():
                raise ValueError(f"Walk-forward cancelled at segment {idx}")
            warmup_start_idx = max(seg["test_start_idx"] - warmup_needed, 0)
            segment_request = BacktestRunRequest(
                strategy_id=request.strategy_id,
                symbol=request.symbol,
                timeframe=entry_timeframe,
                timeframe_mapping=timeframe_mapping,
                start_date=candles[warmup_start_idx].timestamp.date(),
                end_date=seg["test_end"],
                params=params,
                run_tag=request.run_tag,
                note=f"walk-forward segment {idx}",
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
            )
            run_result = self._backtest_service.run(segment_request)
            segment_summary = run_result["summary"]
            segment_benchmark = run_result.get("benchmark") or {}
            segment_results.append(
                {
                    "segment_index": idx,
                    "train_start": seg["train_start"].isoformat(),
                    "train_end": seg["train_end"].isoformat(),
                    "test_start": seg["test_start"].isoformat(),
                    "test_end": seg["test_end"].isoformat(),
                    "linked_run_id": run_result["run_id"],
                    "status": "completed",
                    "trade_count": segment_summary["trade_count"],
                    "gross_return_pct": segment_summary.get(
                        "gross_return_pct",
                        segment_summary.get("total_return_pct", 0.0),
                    ),
                    "net_return_pct": segment_summary.get(
                        "net_return_pct",
                        segment_summary.get("total_return_pct", 0.0),
                    ),
                    "max_drawdown": segment_summary["max_drawdown"],
                    "win_rate": segment_summary["win_rate"],
                    "benchmark_buy_and_hold_return_pct": segment_benchmark.get(
                        "benchmark_buy_and_hold_return_pct",
                        0.0,
                    ),
                    "excess_return_pct": segment_benchmark.get(
                        "strategy_excess_return_pct",
                        0.0,
                    ),
                    "timeframe_mapping": run_result.get("timeframe_mapping", timeframe_mapping),
                }
            )
            if progress_callback:
                progress_callback(idx + 1, len(segments), idx)

        summary = self._build_summary(segment_results)
        diagnostics = self._build_diagnostics(segment_results)
        interpretation_summary = self._build_interpretation(summary, diagnostics)

        created_at = datetime.utcnow()
        walkforward_run_id = uuid4().hex
        payload = request.model_dump(mode="json")
        request_hash = self._hash_request(payload)

        response = {
            "walkforward_run_id": walkforward_run_id,
            "rerun_of_walkforward_run_id": rerun_of_walkforward_run_id,
            "request_hash": request_hash,
            "created_at": created_at,
            "strategy_id": request.strategy_id,
            "strategy_version": strategy_meta.version,
            "code_version": code_version,
            "symbol": request.symbol,
            "timeframe": entry_timeframe,
            "timeframe_mapping": timeframe_mapping,
            "requested_period": {
                "start_date": request.start_date,
                "end_date": request.end_date,
            },
            "train_window_size": request.train_window_size,
            "test_window_size": request.test_window_size,
            "step_size": request.step_size,
            "window_unit": request.window_unit,
            "walkforward_mode": request.walkforward_mode,
            "execution_config": execution_config,
            "params_snapshot": {
                "strategy_params": params,
                "execution_config": execution_config,
                "timeframe_mapping": timeframe_mapping,
            },
            "benchmark_enabled": request.benchmark_enabled,
            "run_tag": request.run_tag,
            "note": request.note,
            "segments": segment_results,
            "summary": summary,
            "diagnostics": diagnostics,
            "interpretation_summary": interpretation_summary,
        }
        self._walkforward_repository.save_run(
            {
                **response,
                "created_at": created_at.isoformat(),
                "requested_period": {
                    "start_date": request.start_date.isoformat(),
                    "end_date": request.end_date.isoformat(),
                },
            }
        )
        return response

    def rerun(self, walkforward_run_id: str) -> dict:
        previous = self._walkforward_repository.get_by_id(walkforward_run_id)
        if previous is None:
            raise ValueError(f"walkforward_run_id not found: {walkforward_run_id}")

        request = WalkforwardRunRequest(
            strategy_id=previous["strategy_id"],
            symbol=previous["symbol"],
            timeframe=previous["timeframe"],
            timeframe_mapping=previous.get("timeframe_mapping"),
            start_date=datetime.fromisoformat(previous["requested_period"]["start_date"]).date(),
            end_date=datetime.fromisoformat(previous["requested_period"]["end_date"]).date(),
            train_window_size=previous["train_window_size"],
            test_window_size=previous["test_window_size"],
            step_size=previous["step_size"],
            window_unit=previous.get("window_unit", "candles"),
            walkforward_mode=previous.get("walkforward_mode", "rolling"),
            params=previous.get("params_snapshot", {}).get("strategy_params", {}),
            fee_rate=previous.get("execution_config", {}).get("fee_rate", 0.0005),
            entry_fee_rate=previous.get("execution_config", {}).get("entry_fee_rate"),
            exit_fee_rate=previous.get("execution_config", {}).get("exit_fee_rate"),
            apply_fee_on_entry=previous.get("execution_config", {}).get("apply_fee_on_entry", True),
            apply_fee_on_exit=previous.get("execution_config", {}).get("apply_fee_on_exit", True),
            slippage_rate=previous.get("execution_config", {}).get("slippage_rate", 0.0003),
            entry_slippage_rate=previous.get("execution_config", {}).get("entry_slippage_rate"),
            exit_slippage_rate=previous.get("execution_config", {}).get("exit_slippage_rate"),
            execution_policy=previous.get("execution_config", {}).get("execution_policy", "next_open"),
            benchmark_enabled=previous.get("benchmark_enabled", True),
            run_tag=previous.get("run_tag"),
            note=f"rerun of walkforward {walkforward_run_id}",
        )
        return self.run(request, rerun_of_walkforward_run_id=walkforward_run_id)

    def list_runs(self, limit: int = 20) -> list[dict]:
        return self._walkforward_repository.get_recent(limit=limit)

    def get_run_detail(self, walkforward_run_id: str) -> dict:
        run = self._walkforward_repository.get_by_id(walkforward_run_id)
        if run is None:
            raise ValueError(f"walkforward_run_id not found: {walkforward_run_id}")

        return {
            **run,
            "created_at": datetime.fromisoformat(run["created_at"]),
            "requested_period": {
                "start_date": datetime.fromisoformat(run["requested_period"]["start_date"]).date(),
                "end_date": datetime.fromisoformat(run["requested_period"]["end_date"]).date(),
            },
            "segments": [
                {
                    **seg,
                    "train_start": datetime.fromisoformat(seg["train_start"]).date(),
                    "train_end": datetime.fromisoformat(seg["train_end"]).date(),
                    "test_start": datetime.fromisoformat(seg["test_start"]).date(),
                    "test_end": datetime.fromisoformat(seg["test_end"]).date(),
                }
                for seg in run.get("segments", [])
            ],
        }

    def compare_runs(self, walkforward_run_ids: list[str]) -> list[dict]:
        if len(walkforward_run_ids) < 2:
            raise ValueError("At least 2 walkforward_run_ids are required")
        runs = self._walkforward_repository.get_by_ids(walkforward_run_ids)
        if len(runs) < 2:
            raise ValueError("Could not find enough walk-forward runs for comparison")

        sorted_runs = sorted(
            runs,
            key=lambda r: r.get("summary", {}).get("total_net_return_pct", 0.0),
            reverse=True,
        )
        return [
            {
                "walkforward_run_id": run["walkforward_run_id"],
                "created_at": datetime.fromisoformat(run["created_at"]),
                "strategy_id": run["strategy_id"],
                "symbol": run["symbol"],
                "timeframe_mapping": run.get("timeframe_mapping"),
                "timeframe_mapping_summary": self._mapping_summary(run.get("timeframe_mapping")),
                "walkforward_mode": run.get("walkforward_mode", "rolling"),
                "segment_count": run["summary"]["segment_count"],
                "total_net_return_pct": run["summary"]["total_net_return_pct"],
                "average_segment_return_pct": run["summary"]["average_segment_return_pct"],
                "worst_segment_return_pct": run["summary"]["worst_segment_return_pct"],
                "best_segment_return_pct": run["summary"]["best_segment_return_pct"],
                "segments_beating_benchmark": run["diagnostics"]["segments_beating_benchmark"],
                "profitable_segments": run["diagnostics"]["profitable_segments"],
            }
            for run in sorted_runs
        ]

    def build_segments(
        self,
        candles: list,
        train_window_size: int,
        test_window_size: int,
        step_size: int,
        window_unit: str,
        walkforward_mode: str = "rolling",
    ) -> list[dict]:
        if window_unit not in {"candles", "days"}:
            raise ValueError(f"Unsupported window_unit={window_unit}")
        if walkforward_mode not in {"rolling", "anchored"}:
            raise ValueError(f"Unsupported walkforward_mode={walkforward_mode}")
        if train_window_size <= 0 or test_window_size <= 0 or step_size <= 0:
            raise ValueError("Window sizes and step must be positive")
        if len(candles) < train_window_size + test_window_size:
            return []

        # NOTE: For phase-1 skeleton, "days" follows candle-count stepping.
        # TODO: add true calendar-based stepping for intraday data.
        segments: list[dict] = []
        cursor = 0
        last_idx = len(candles) - 1
        while True:
            if walkforward_mode == "anchored":
                train_start_idx = 0
                train_end_idx = (train_window_size - 1) + cursor
            else:
                train_start_idx = cursor
                train_end_idx = cursor + train_window_size - 1
            test_start_idx = train_end_idx + 1
            test_end_idx = test_start_idx + test_window_size - 1
            if test_end_idx > last_idx:
                break
            segments.append(
                {
                    "train_start": candles[train_start_idx].timestamp.date(),
                    "train_end": candles[train_end_idx].timestamp.date(),
                    "test_start": candles[test_start_idx].timestamp.date(),
                    "test_end": candles[test_end_idx].timestamp.date(),
                    "train_start_idx": train_start_idx,
                    "train_end_idx": train_end_idx,
                    "test_start_idx": test_start_idx,
                    "test_end_idx": test_end_idx,
                }
            )
            cursor += step_size
        return segments

    def _resolve_execution_config(self, request: WalkforwardRunRequest) -> dict:
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

    def _resolve_timeframe_mapping(self, strategy, request: WalkforwardRunRequest) -> dict[str, str]:
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

    def _build_summary(self, segments: list[dict]) -> dict:
        returns = [float(seg["net_return_pct"]) for seg in segments]
        mdds = [float(seg["max_drawdown"]) for seg in segments]
        trades = [int(seg["trade_count"]) for seg in segments]

        compounded_equity = 1.0
        for value in returns:
            compounded_equity *= 1 + (value / 100)
        total_net_return_pct = (compounded_equity - 1.0) * 100

        beating = sum(1 for seg in segments if seg["excess_return_pct"] > 0)
        benchmark_summary = (
            f"{beating}/{len(segments)} segments beat benchmark" if segments else "no segments"
        )
        return {
            "segment_count": len(segments),
            "completed_segment_count": len(segments),
            "total_net_return_pct": round(total_net_return_pct, 4),
            "average_segment_return_pct": round(mean(returns), 4) if returns else 0.0,
            "median_segment_return_pct": round(median(returns), 4) if returns else 0.0,
            "worst_segment_return_pct": round(min(returns), 4) if returns else 0.0,
            "best_segment_return_pct": round(max(returns), 4) if returns else 0.0,
            "average_max_drawdown": round(mean(mdds), 4) if mdds else 0.0,
            "total_trade_count": sum(trades),
            "benchmark_comparison_summary": benchmark_summary,
        }

    def _build_diagnostics(self, segments: list[dict]) -> dict:
        profitable = sum(1 for seg in segments if seg["net_return_pct"] > 0)
        losing = sum(1 for seg in segments if seg["net_return_pct"] <= 0)
        beating = sum(1 for seg in segments if seg["excess_return_pct"] > 0)
        underperforming = sum(1 for seg in segments if seg["excess_return_pct"] <= 0)
        return {
            "profitable_segments": profitable,
            "losing_segments": losing,
            "segments_beating_benchmark": beating,
            "segments_underperforming_benchmark": underperforming,
        }

    def _build_interpretation(self, summary: dict, diagnostics: dict) -> str:
        segment_count = max(summary.get("segment_count", 0), 1)
        if diagnostics["segments_beating_benchmark"] <= segment_count // 3:
            return "세그먼트 대부분이 벤치마크를 하회해 일관성이 낮습니다."
        if diagnostics["losing_segments"] > diagnostics["profitable_segments"]:
            return "손실 구간 비중이 높아 파라미터/시장 적합성 재검토가 필요합니다."
        if summary["average_segment_return_pct"] > 0 and summary["average_max_drawdown"] > 15:
            return "평균 수익은 양수지만 구간별 낙폭이 커 리스크 관리 강화가 필요합니다."
        if (
            summary["best_segment_return_pct"] - summary["worst_segment_return_pct"]
            > 20
        ):
            return "세그먼트 편차가 커 성과 일관성이 낮습니다."
        return "세그먼트 전반에서 비교적 안정적인 성과 흐름을 보였습니다."

    def _hash_request(self, payload: dict) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _mapping_summary(self, mapping: dict[str, str] | None) -> str | None:
        if not mapping:
            return None
        return ", ".join(f"{role}:{tf}" for role, tf in sorted(mapping.items()))

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

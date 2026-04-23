from datetime import date, datetime, timedelta
import hashlib
import json
import subprocess
from typing import Callable
from uuid import uuid4

from app.data_collectors.base import HistoricalCandleCollector
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.market_data import MarketDataBatchRequest, MarketDataCollectRequest, MarketDataUpdateRequest


class MarketDataService:
    def __init__(
        self,
        collector: HistoricalCandleCollector,
        repository: MarketDataRepository,
        project_root: str | None = None,
    ) -> None:
        self._collector = collector
        self._repository = repository
        self._project_root = project_root

    def collect(
        self,
        request: MarketDataCollectRequest,
        progress_callback: Callable[[float], None] | None = None,
    ) -> dict:
        timeframe = self.normalize_timeframe(request.timeframe)
        if request.dry_run:
            dataset_id = self._repository.dataset_id(request.source, request.symbol, timeframe)
            return {
                "dataset_id": dataset_id,
                "source": request.source,
                "symbol": request.symbol,
                "timeframe": timeframe,
                "requested_period": {"start_date": request.start_date, "end_date": request.end_date},
                "fetched_count": 0,
                "saved_count": 0,
                "duplicate_removed_count": 0,
                "actual_range": {"start_at": None, "end_at": None},
                "dataset_path": str(self._repository.dataset_paths(request.source, request.symbol, timeframe)["csv"]),
                "data_signature": "",
                "quality_status": "warning",
            }

        if progress_callback:
            progress_callback(5)
        fetched = self._collector.fetch_ohlcv(
            symbol=request.symbol,
            timeframe=timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            progress_callback=progress_callback,
        )

        fetched_rows = [
            {
                "timestamp": candle.timestamp.isoformat(),
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": float(candle.volume),
            }
            for candle in fetched
        ]
        existing_rows = []
        if not request.overwrite:
            existing_rows = self._repository.load_rows(request.source, request.symbol, timeframe)

        merged, duplicate_removed = self._merge_rows(existing_rows, fetched_rows)
        quality = self.validate_rows(merged, timeframe)
        signature = self._compute_signature(merged)

        if progress_callback:
            progress_callback(92)
        csv_path = self._repository.save_rows(request.source, request.symbol, timeframe, merged)
        now = datetime.utcnow().isoformat()
        dataset_id = self._repository.dataset_id(request.source, request.symbol, timeframe)
        manifest = {
            "dataset_id": dataset_id,
            "source": request.source,
            "exchange": request.source,
            "symbol": request.symbol,
            "timeframe": timeframe,
            "start_at": merged[0]["timestamp"] if merged else None,
            "end_at": merged[-1]["timestamp"] if merged else None,
            "row_count": len(merged),
            "created_at": now,
            "updated_at": now,
            "data_signature": signature,
            "quality_status": quality["status"],
            "quality_report_summary": quality["summary_message"],
            "quality_report": quality,
            "collector_version": "upbit-v1",
            "code_version": self._detect_code_version(),
            "last_checked_at": now,
            "path": str(csv_path),
            "notes": None,
        }
        self._repository.save_manifest(request.source, request.symbol, timeframe, manifest)
        if progress_callback:
            progress_callback(100)

        return {
            "dataset_id": dataset_id,
            "source": request.source,
            "symbol": request.symbol,
            "timeframe": timeframe,
            "requested_period": {"start_date": request.start_date, "end_date": request.end_date},
            "fetched_count": len(fetched_rows),
            "saved_count": len(merged),
            "duplicate_removed_count": duplicate_removed,
            "actual_range": {
                "start_at": merged[0]["timestamp"] if merged else None,
                "end_at": merged[-1]["timestamp"] if merged else None,
            },
            "dataset_path": str(csv_path),
            "data_signature": signature,
            "quality_status": quality["status"],
        }

    def update(
        self,
        request: MarketDataUpdateRequest,
        progress_callback: Callable[[float], None] | None = None,
    ) -> dict:
        timeframe = self.normalize_timeframe(request.timeframe)
        manifest = self._repository.load_manifest(request.source, request.symbol, timeframe)
        if manifest is None:
            raise ValueError("dataset not found, run collect first")
        if not manifest.get("end_at"):
            raise ValueError("dataset manifest missing end_at")

        end_ts = datetime.fromisoformat(manifest["end_at"])
        start_date = (end_ts + self._timeframe_delta(timeframe)).date()
        end_date = request.end_date or datetime.utcnow().date()
        if start_date > end_date:
            start_date = end_date
        collect_req = MarketDataCollectRequest(
            source=request.source,
            symbol=request.symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            overwrite=False,
            dry_run=False,
            use_job=False,
        )
        return self.collect(collect_req, progress_callback=progress_callback)

    def collect_batch(
        self,
        request: MarketDataBatchRequest,
        progress_callback: Callable[[int, int, str | None, str | None], None] | None = None,
    ) -> dict:
        combos = self._build_combinations(request.symbols, request.timeframes)
        total = len(combos)
        batch_id = uuid4().hex
        items: list[dict] = []
        created = 0
        updated = 0
        pass_count = 0
        warning_count = 0
        fail_count = 0
        completed = 0
        failed = 0
        skipped = 0

        for idx, (symbol, timeframe) in enumerate(combos):
            if progress_callback:
                progress_callback(idx, total, symbol, timeframe)
            try:
                before_manifest = self._repository.load_manifest(request.source, symbol, timeframe)
                if request.mode == "incremental_update":
                    if before_manifest is None:
                        item = {
                            "source": request.source,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "status": "skipped",
                            "dataset_id": None,
                            "quality_status": None,
                            "fetched_count": 0,
                            "saved_count": 0,
                            "message": "dataset not found for incremental update",
                        }
                        items.append(item)
                        skipped += 1
                        continue
                    result = self.update(
                        MarketDataUpdateRequest(
                            source=request.source,
                            symbol=symbol,
                            timeframe=timeframe,
                            end_date=request.end_date,
                            use_job=False,
                        )
                    )
                else:
                    if request.start_date is None or request.end_date is None:
                        raise ValueError("start_date/end_date are required for full_collect")
                    result = self.collect(
                        MarketDataCollectRequest(
                            source=request.source,
                            symbol=symbol,
                            timeframe=timeframe,
                            start_date=request.start_date,
                            end_date=request.end_date,
                            overwrite=request.overwrite,
                            dry_run=request.dry_run,
                            use_job=False,
                        )
                    )

                dataset_id = result["dataset_id"]
                if request.validate_after_collect and not request.dry_run:
                    self.validate_dataset(dataset_id)
                manifest = self._repository.get_by_dataset_id(dataset_id) or {}
                quality_status = manifest.get("quality_status", result.get("quality_status"))
                if quality_status == "pass":
                    pass_count += 1
                elif quality_status == "warning":
                    warning_count += 1
                elif quality_status == "fail":
                    fail_count += 1

                if before_manifest is None:
                    created += 1
                else:
                    updated += 1
                completed += 1
                items.append(
                    {
                        "source": request.source,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "status": "completed",
                        "dataset_id": dataset_id,
                        "quality_status": quality_status,
                        "fetched_count": result.get("fetched_count", 0),
                        "saved_count": result.get("saved_count", 0),
                        "message": None,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                items.append(
                    {
                        "source": request.source,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "status": "failed",
                        "dataset_id": None,
                        "quality_status": None,
                        "fetched_count": 0,
                        "saved_count": 0,
                        "message": str(exc)[:240],
                    }
                )

        if progress_callback:
            progress_callback(total, total, None, None)
        return {
            "mode": "sync",
            "batch_id": batch_id,
            "total_requested_combinations": total,
            "completed_combinations": completed,
            "failed_combinations": failed,
            "skipped_combinations": skipped,
            "created_datasets": created,
            "updated_datasets": updated,
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "items": items,
            "message": None,
        }

    def list_datasets(
        self,
        source: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        quality_status: str | None = None,
    ) -> list[dict]:
        return self._repository.list_datasets(
            source=source,
            symbol=symbol,
            timeframe=self.normalize_timeframe(timeframe) if timeframe else None,
            quality_status=quality_status,
        )

    def summary(self, source: str | None = None) -> dict:
        items = self._repository.list_datasets(source=source)
        symbols = sorted({item.get("symbol") for item in items if item.get("symbol")})
        timeframes = sorted({item.get("timeframe") for item in items if item.get("timeframe")}, key=self._timeframe_sort_key)
        pass_count = sum(1 for item in items if item.get("quality_status") == "pass")
        warning_count = sum(1 for item in items if item.get("quality_status") == "warning")
        fail_count = sum(1 for item in items if item.get("quality_status") == "fail")
        latest = max((item.get("updated_at", "") for item in items), default="") or None

        by_symbol: dict[str, dict] = {}
        for symbol in symbols:
            symbol_items = [i for i in items if i.get("symbol") == symbol]
            tf_map = {
                i.get("timeframe"): {
                    "dataset_id": i.get("dataset_id"),
                    "quality_status": i.get("quality_status"),
                    "updated_at": i.get("updated_at"),
                    "row_count": i.get("row_count"),
                }
                for i in sorted(symbol_items, key=lambda x: self._timeframe_sort_key(x.get("timeframe", "")))
            }
            by_symbol[symbol] = {
                "timeframes": tf_map,
                "pass_count": sum(1 for i in symbol_items if i.get("quality_status") == "pass"),
                "warning_count": sum(1 for i in symbol_items if i.get("quality_status") == "warning"),
                "fail_count": sum(1 for i in symbol_items if i.get("quality_status") == "fail"),
            }
        return {
            "total_datasets": len(items),
            "available_symbols": symbols,
            "available_timeframes": timeframes,
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "latest_updated_at": latest,
            "by_symbol": by_symbol,
        }

    def get_dataset(self, dataset_id: str) -> dict:
        manifest = self._repository.get_by_dataset_id(dataset_id)
        if manifest is None:
            raise ValueError(f"dataset not found: {dataset_id}")
        quality = manifest.get("quality_report")
        if quality is None:
            rows = self._repository.load_rows(manifest["source"], manifest["symbol"], manifest["timeframe"])
            quality = self.validate_rows(rows, manifest["timeframe"])
        return {"manifest": manifest, "quality_report": quality}

    def validate_dataset(
        self,
        dataset_id: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> dict:
        manifest = self._repository.get_by_dataset_id(dataset_id)
        if manifest is None:
            raise ValueError(f"dataset not found: {dataset_id}")
        if progress_callback:
            progress_callback(20)
        rows = self._repository.load_rows(manifest["source"], manifest["symbol"], manifest["timeframe"])
        if progress_callback:
            progress_callback(70)
        quality = self.validate_rows(rows, manifest["timeframe"])
        manifest["quality_status"] = quality["status"]
        manifest["quality_report_summary"] = quality["summary_message"]
        manifest["quality_report"] = quality
        manifest["last_checked_at"] = datetime.utcnow().isoformat()
        manifest["updated_at"] = datetime.utcnow().isoformat()
        self._repository.save_manifest(manifest["source"], manifest["symbol"], manifest["timeframe"], manifest)
        if progress_callback:
            progress_callback(100)
        return {"manifest": manifest, "quality_report": quality}

    def preview_dataset(self, dataset_id: str, limit: int = 20, tail: bool = True) -> dict:
        manifest = self._repository.get_by_dataset_id(dataset_id)
        if manifest is None:
            raise ValueError(f"dataset not found: {dataset_id}")
        rows = self._repository.load_rows(manifest["source"], manifest["symbol"], manifest["timeframe"])
        sliced = rows[-limit:] if tail else rows[:limit]
        return {
            "dataset_id": dataset_id,
            "timeframe": manifest["timeframe"],
            "total_rows": len(rows),
            "rows": sliced,
        }

    def normalize_timeframe(self, timeframe: str) -> str:
        tf = timeframe.lower().strip()
        alias = {"1h": "60m", "4h": "240m"}
        tf = alias.get(tf, tf)
        allowed = {"1m", "3m", "5m", "10m", "15m", "30m", "60m", "240m", "1d"}
        if tf not in allowed:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        return tf

    def validate_rows(self, rows: list[dict], timeframe: str) -> dict:
        detail_messages: list[str] = []
        row_count = len(rows)
        null_count = 0
        invalid_ohlc = 0
        suspicious_gap = 0

        timestamps = [row.get("timestamp") for row in rows]
        parsed_ts = [datetime.fromisoformat(ts) for ts in timestamps if ts]
        sorted_ok = parsed_ts == sorted(parsed_ts)
        if not sorted_ok:
            detail_messages.append("timestamps are not sorted ascending")

        duplicate_count = 0
        if timestamps:
            duplicate_count = len(timestamps) - len(set(timestamps))
            if duplicate_count > 0:
                detail_messages.append(f"duplicate timestamps found: {duplicate_count}")

        delta = self._timeframe_delta(timeframe)
        missing_interval_count = 0
        for idx in range(1, len(parsed_ts)):
            gap = parsed_ts[idx] - parsed_ts[idx - 1]
            if gap > delta:
                steps = int(gap.total_seconds() // delta.total_seconds()) - 1
                if steps > 0:
                    missing_interval_count += steps
            if gap.total_seconds() > delta.total_seconds() * 10:
                suspicious_gap += 1
        if missing_interval_count > 0:
            detail_messages.append(f"missing intervals detected: {missing_interval_count}")

        for row in rows:
            for col in ("timestamp", "open", "high", "low", "close", "volume"):
                if row.get(col) is None or row.get(col) == "":
                    null_count += 1
            try:
                o = float(row["open"])
                h = float(row["high"])
                l = float(row["low"])
                c = float(row["close"])
                v = float(row["volume"])
                if h < l or o < l or o > h or c < l or c > h or min(o, h, l, c) < 0 or v < 0:
                    invalid_ohlc += 1
            except Exception:
                invalid_ohlc += 1

        status = "pass"
        if null_count > 0 or invalid_ohlc > 0 or not sorted_ok:
            status = "fail"
        elif duplicate_count > 0 or missing_interval_count > 0 or suspicious_gap > 0:
            status = "warning"

        summary = (
            f"rows={row_count}, dup={duplicate_count}, missing={missing_interval_count}, "
            f"null={null_count}, invalid={invalid_ohlc}, suspicious={suspicious_gap}"
        )
        return {
            "status": status,
            "row_count": row_count,
            "duplicate_count": duplicate_count,
            "missing_interval_count": missing_interval_count,
            "null_count": null_count,
            "invalid_ohlc_count": invalid_ohlc,
            "suspicious_gap_count": suspicious_gap,
            "summary_message": summary,
            "detail_messages": detail_messages,
        }

    def _merge_rows(self, existing_rows: list[dict], fetched_rows: list[dict]) -> tuple[list[dict], int]:
        merged: dict[str, dict] = {}
        duplicates = 0
        for row in existing_rows + fetched_rows:
            ts = row["timestamp"]
            if ts in merged:
                duplicates += 1
            merged[ts] = row
        sorted_rows = sorted(merged.values(), key=lambda r: r["timestamp"])
        return sorted_rows, duplicates

    def _build_combinations(self, symbols: list[str], timeframes: list[str]) -> list[tuple[str, str]]:
        combos = []
        for symbol in symbols:
            for tf in timeframes:
                combos.append((symbol, self.normalize_timeframe(tf)))
        return combos

    def _compute_signature(self, rows: list[dict]) -> str:
        compact = [
            [r["timestamp"], r["open"], r["high"], r["low"], r["close"], r["volume"]]
            for r in rows
        ]
        payload = json.dumps(compact, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _timeframe_delta(self, timeframe: str) -> timedelta:
        timeframe = self.normalize_timeframe(timeframe)
        if timeframe == "1d":
            return timedelta(days=1)
        if timeframe.endswith("m"):
            return timedelta(minutes=int(timeframe[:-1]))
        return timedelta(days=1)

    def _timeframe_sort_key(self, timeframe: str) -> int:
        tf = timeframe or ""
        if tf == "1d":
            return 1440
        if tf.endswith("m"):
            try:
                return int(tf[:-1])
            except ValueError:
                return 999999
        return 999999

    def _detect_code_version(self) -> str:
        try:
            output = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self._project_root,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return output.strip() or "unknown-local"
        except Exception:  # noqa: BLE001
            return "unknown-local"

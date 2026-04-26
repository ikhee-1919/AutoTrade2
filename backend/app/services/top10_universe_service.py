from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import json
from typing import Callable
from uuid import uuid4

from app.data_collectors.base import HistoricalCandleCollector
from app.schemas.market_data import MarketDataBatchRequest
from app.services.market_cap_provider import CoinGeckoMarketCapProvider, RankedCoin
from app.services.market_data_service import MarketDataService
from app.repositories.top10_universe_repository import Top10UniverseRepository


class Top10UniverseService:
    BASE_TIMEFRAMES = ["1m", "3m", "5m", "10m", "15m", "30m", "60m", "240m", "1d", "1w", "1mo", "1y"]
    SECOND_TIMEFRAMES = ["1s"]

    def __init__(
        self,
        collector: HistoricalCandleCollector,
        market_data_service: MarketDataService,
        repository: Top10UniverseRepository,
        market_cap_provider: CoinGeckoMarketCapProvider,
    ) -> None:
        self._collector = collector
        self._market_data_service = market_data_service
        self._repository = repository
        self._market_cap_provider = market_cap_provider

    def refresh_universe(
        self,
        market_scope: str = "KRW",
        top_n: int = 10,
    ) -> dict:
        market_scope = market_scope.upper().strip()
        if market_scope not in {"KRW", "BTC", "USDT"}:
            raise ValueError("market_scope must be one of KRW/BTC/USDT")
        if top_n <= 0:
            raise ValueError("top_n must be positive")

        upbit_markets = self._fetch_upbit_markets()
        scoped_markets = [m for m in upbit_markets if m.startswith(f"{market_scope}-")]

        ranked = self._market_cap_provider.fetch_ranked_coins(max_items=500)
        best_by_symbol = self._best_ranked_by_symbol(ranked)

        selected_rows: list[dict] = []
        unmatched_symbols: list[str] = []

        for market in scoped_markets:
            _, symbol = market.split("-", 1)
            hit = best_by_symbol.get(symbol.upper())
            if not hit:
                unmatched_symbols.append(symbol.upper())
                continue
            selected_rows.append(
                {
                    "market": market,
                    "symbol": symbol.upper(),
                    "coin_id": hit.coin_id,
                    "name": hit.name,
                    "market_cap": hit.market_cap,
                    "market_cap_rank": hit.rank,
                }
            )

        selected_rows.sort(key=lambda x: x["market_cap"], reverse=True)
        selected_rows = selected_rows[:top_n]

        if not selected_rows:
            raise ValueError("No upbit markets matched market cap ranking source")

        generated_at = datetime.utcnow().isoformat()
        universe_id = f"upbit_{market_scope.lower()}_top{top_n}_{generated_at[:19].replace(':', '').replace('-', '')}"

        payload = {
            "universe_id": universe_id,
            "generated_at": generated_at,
            "source_exchange": "upbit",
            "market_scope": market_scope,
            "ranking_source": "coingecko_coins_markets_usd",
            "selected_count": len(selected_rows),
            "selected_markets": [r["market"] for r in selected_rows],
            "selected_symbols": [r["symbol"] for r in selected_rows],
            "selected_rows": selected_rows,
            "market_cap_snapshot": {
                "snapshot_count": len(ranked),
                "top_preview": [
                    {
                        "coin_id": r.coin_id,
                        "symbol": r.symbol,
                        "market_cap": r.market_cap,
                        "rank": r.rank,
                    }
                    for r in ranked[:25]
                ],
                "unmatched_upbit_symbols": sorted(set(unmatched_symbols))[:120],
            },
            "collection_policy": {
                "all_supported_historical_candles": True,
                "include_seconds": False,
                "base_timeframes": list(self.BASE_TIMEFRAMES),
                "second_timeframes": list(self.SECOND_TIMEFRAMES),
            },
            "notes": "dynamic top universe generated at runtime",
        }
        return self._repository.save(payload)

    def get_current_universe(self) -> dict:
        current = self._repository.get_current()
        if not current:
            raise ValueError("top10 universe is not initialized. Run refresh first.")
        return current

    def collect_all(
        self,
        include_seconds: bool = False,
        validate_after_collect: bool = True,
        overwrite_existing: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
        progress_callback: Callable[[int, int, str | None, str | None], None] | None = None,
    ) -> dict:
        universe = self.get_current_universe()
        symbols = universe.get("selected_markets") or []
        if not symbols:
            raise ValueError("selected_markets missing in universe")

        end = end_date or datetime.utcnow().date()
        start = start_date or date(2017, 1, 1)
        base_timeframes = list(self.BASE_TIMEFRAMES)
        all_batches: list[dict] = []

        base_result = self._market_data_service.collect_batch(
            MarketDataBatchRequest(
                source="upbit",
                symbols=symbols,
                timeframes=base_timeframes,
                start_date=start,
                end_date=end,
                mode="full_collect",
                validate_after_collect=validate_after_collect,
                overwrite=overwrite_existing,
                dry_run=False,
                use_job=False,
            ),
            progress_callback=progress_callback,
        )
        all_batches.append(base_result)

        if include_seconds:
            seconds_start = max(start, self.seconds_allowed_start(end))
            seconds_result = self._market_data_service.collect_batch(
                MarketDataBatchRequest(
                    source="upbit",
                    symbols=symbols,
                    timeframes=list(self.SECOND_TIMEFRAMES),
                    start_date=seconds_start,
                    end_date=end,
                    mode="full_collect",
                    validate_after_collect=validate_after_collect,
                    overwrite=overwrite_existing,
                    dry_run=False,
                    use_job=False,
                ),
                progress_callback=progress_callback,
            )
            all_batches.append(seconds_result)

        merged = self._merge_batch_results(all_batches)
        return {
            **merged,
            "universe_id": universe.get("universe_id"),
            "included_timeframes": self._timeframes(include_seconds=include_seconds),
            "include_seconds": include_seconds,
        }

    def update_all(
        self,
        include_seconds: bool = False,
        validate_after_collect: bool = True,
        end_date: date | None = None,
        progress_callback: Callable[[int, int, str | None, str | None], None] | None = None,
    ) -> dict:
        universe = self.get_current_universe()
        symbols = universe.get("selected_markets") or []
        if not symbols:
            raise ValueError("selected_markets missing in universe")

        end = end_date or datetime.utcnow().date()
        result = self._market_data_service.collect_batch(
            MarketDataBatchRequest(
                source="upbit",
                symbols=symbols,
                timeframes=self._timeframes(include_seconds=include_seconds),
                start_date=None,
                end_date=end,
                mode="incremental_update",
                validate_after_collect=validate_after_collect,
                overwrite=False,
                dry_run=False,
                use_job=False,
            ),
            progress_callback=progress_callback,
        )
        return {
            **result,
            "universe_id": universe.get("universe_id"),
            "included_timeframes": self._timeframes(include_seconds=include_seconds),
            "include_seconds": include_seconds,
        }

    def summary(self, include_seconds: bool = False) -> dict:
        universe = self.get_current_universe()
        symbols = universe.get("selected_markets") or []
        expected_timeframes = self._timeframes(include_seconds=include_seconds)

        datasets = self._market_data_service.list_datasets(source="upbit")
        by_pair_tf = {(d.get("symbol"), d.get("timeframe")): d for d in datasets}

        pass_count = 0
        warning_count = 0
        fail_count = 0
        missing_count = 0
        failed_dataset_count = 0
        total_rows = 0
        latest_updated_at: str | None = None

        coverage_by_symbol: dict[str, dict] = {}
        for symbol in symbols:
            tf_map: dict[str, dict] = {}
            symbol_missing = 0
            symbol_failed = 0
            for tf in expected_timeframes:
                item = by_pair_tf.get((symbol, tf))
                if item is None:
                    missing_count += 1
                    symbol_missing += 1
                    tf_map[tf] = {
                        "dataset_id": None,
                        "quality_status": None,
                        "updated_at": None,
                        "row_count": 0,
                        "status": "missing",
                    }
                    continue

                quality = item.get("quality_status")
                if quality == "pass":
                    pass_count += 1
                elif quality == "warning":
                    warning_count += 1
                elif quality == "fail":
                    fail_count += 1
                    failed_dataset_count += 1
                    symbol_failed += 1
                rows = int(item.get("row_count") or 0)
                total_rows += rows
                updated_at = item.get("updated_at")
                if updated_at and (latest_updated_at is None or updated_at > latest_updated_at):
                    latest_updated_at = updated_at

                tf_map[tf] = {
                    "dataset_id": item.get("dataset_id"),
                    "quality_status": quality,
                    "updated_at": updated_at,
                    "row_count": rows,
                    "status": "available",
                }

            coverage_by_symbol[symbol] = {
                "timeframes": tf_map,
                "missing_count": symbol_missing,
                "failed_count": symbol_failed,
            }

        total_combinations = len(symbols) * len(expected_timeframes)

        return {
            "universe_id": universe.get("universe_id"),
            "generated_at": universe.get("generated_at"),
            "market_scope": universe.get("market_scope"),
            "selected_markets": symbols,
            "selected_symbols": universe.get("selected_symbols") or [],
            "included_timeframes": expected_timeframes,
            "include_seconds": include_seconds,
            "total_combinations": total_combinations,
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "missing_dataset_count": missing_count,
            "failed_dataset_count": failed_dataset_count,
            "latest_updated_at": latest_updated_at,
            "total_row_count": total_rows,
            "coverage_by_symbol": coverage_by_symbol,
        }

    def missing(self, include_seconds: bool = False) -> dict:
        summary = self.summary(include_seconds=include_seconds)
        items: list[dict[str, str]] = []
        coverage_by_symbol = summary.get("coverage_by_symbol") or {}
        for symbol, row in coverage_by_symbol.items():
            for timeframe, tf_meta in (row.get("timeframes") or {}).items():
                if tf_meta.get("status") == "missing":
                    items.append({"symbol": symbol, "timeframe": timeframe})
        return {
            "universe_id": summary.get("universe_id"),
            "include_seconds": include_seconds,
            "total_missing": len(items),
            "items": items,
        }

    def retry_missing(
        self,
        include_seconds: bool = False,
        validate_after_collect: bool = True,
        overwrite_existing: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
        progress_callback: Callable[[int, int, str | None, str | None], None] | None = None,
    ) -> dict:
        miss = self.missing(include_seconds=include_seconds)
        pairs = miss.get("items") or []
        if not pairs:
            return {
                "mode": "sync",
                "batch_id": uuid4().hex,
                "total_requested_combinations": 0,
                "completed_combinations": 0,
                "failed_combinations": 0,
                "skipped_combinations": 0,
                "created_datasets": 0,
                "updated_datasets": 0,
                "pass_count": 0,
                "warning_count": 0,
                "fail_count": 0,
                "items": [],
                "message": "no missing combinations",
                "universe_id": miss.get("universe_id"),
                "included_timeframes": self._timeframes(include_seconds=include_seconds),
                "include_seconds": include_seconds,
            }

        end = end_date or datetime.utcnow().date()
        start = start_date or date(2017, 1, 1)
        seconds_start: date | None = None
        if include_seconds:
            seconds_start = self.seconds_allowed_start(end)
        results: list[dict] = []
        total = len(pairs)
        completed = 0
        failed = 0
        skipped = 0
        created = 0
        updated = 0
        pass_count = 0
        warning_count = 0
        fail_count = 0

        for idx, pair in enumerate(pairs):
            symbol = pair["symbol"]
            timeframe = pair["timeframe"]
            if progress_callback:
                progress_callback(idx, total, symbol, timeframe)
            try:
                req_start = start
                if timeframe == "1s" and seconds_start is not None:
                    req_start = max(start, seconds_start)
                outcome = self._market_data_service.collect_batch(
                    MarketDataBatchRequest(
                        source="upbit",
                        symbols=[symbol],
                        timeframes=[timeframe],
                        start_date=req_start,
                        end_date=end,
                        mode="full_collect",
                        validate_after_collect=validate_after_collect,
                        overwrite=overwrite_existing,
                        dry_run=False,
                        use_job=False,
                    )
                )
                completed += int(outcome.get("completed_combinations") or 0)
                failed += int(outcome.get("failed_combinations") or 0)
                skipped += int(outcome.get("skipped_combinations") or 0)
                created += int(outcome.get("created_datasets") or 0)
                updated += int(outcome.get("updated_datasets") or 0)
                pass_count += int(outcome.get("pass_count") or 0)
                warning_count += int(outcome.get("warning_count") or 0)
                fail_count += int(outcome.get("fail_count") or 0)
                results.extend(outcome.get("items") or [])
            except Exception as exc:  # noqa: BLE001
                failed += 1
                results.append(
                    {
                        "source": "upbit",
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
            "batch_id": uuid4().hex,
            "total_requested_combinations": total,
            "completed_combinations": completed,
            "failed_combinations": failed,
            "skipped_combinations": skipped,
            "created_datasets": created,
            "updated_datasets": updated,
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "items": results,
            "message": None,
            "universe_id": miss.get("universe_id"),
            "included_timeframes": self._timeframes(include_seconds=include_seconds),
            "include_seconds": include_seconds,
        }

    def _fetch_upbit_markets(self) -> list[str]:
        if not hasattr(self._collector, "fetch_markets"):
            raise ValueError("collector does not support market listing")
        markets = self._collector.fetch_markets()  # type: ignore[attr-defined]
        deduped = sorted({str(m).upper() for m in markets if isinstance(m, str) and "-" in m})
        return deduped

    def _best_ranked_by_symbol(self, ranked: list[RankedCoin]) -> dict[str, RankedCoin]:
        out: dict[str, RankedCoin] = {}
        for item in ranked:
            symbol = item.symbol.upper()
            prev = out.get(symbol)
            if prev is None or item.market_cap > prev.market_cap:
                out[symbol] = item
        return out

    def _timeframes(self, include_seconds: bool) -> list[str]:
        tfs = list(self.BASE_TIMEFRAMES)
        if include_seconds:
            tfs.extend(self.SECOND_TIMEFRAMES)
        return tfs

    def request_hash(self, payload: dict) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def next_universe_id(self) -> str:
        return uuid4().hex

    def seconds_allowed_start(self, end_date: date | None = None) -> date:
        end = end_date or datetime.utcnow().date()
        return end - timedelta(days=90)

    def _merge_batch_results(self, batches: list[dict]) -> dict:
        merged_items: list[dict] = []
        out = {
            "mode": "sync",
            "batch_id": uuid4().hex,
            "total_requested_combinations": 0,
            "completed_combinations": 0,
            "failed_combinations": 0,
            "skipped_combinations": 0,
            "created_datasets": 0,
            "updated_datasets": 0,
            "pass_count": 0,
            "warning_count": 0,
            "fail_count": 0,
            "items": merged_items,
            "message": None,
        }
        for batch in batches:
            out["total_requested_combinations"] += int(batch.get("total_requested_combinations") or 0)
            out["completed_combinations"] += int(batch.get("completed_combinations") or 0)
            out["failed_combinations"] += int(batch.get("failed_combinations") or 0)
            out["skipped_combinations"] += int(batch.get("skipped_combinations") or 0)
            out["created_datasets"] += int(batch.get("created_datasets") or 0)
            out["updated_datasets"] += int(batch.get("updated_datasets") or 0)
            out["pass_count"] += int(batch.get("pass_count") or 0)
            out["warning_count"] += int(batch.get("warning_count") or 0)
            out["fail_count"] += int(batch.get("fail_count") or 0)
            merged_items.extend(batch.get("items") or [])
        return out

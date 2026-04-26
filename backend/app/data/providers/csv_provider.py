import csv
from datetime import date, datetime
import json
from pathlib import Path

from app.data.providers.base import BaseDataProvider
from app.models.candle import Candle


class CSVDataProvider(BaseDataProvider):
    def __init__(self, sample_data_dir: Path, collected_data_dir: Path | None = None):
        self._sample_data_dir = sample_data_dir
        self._collected_data_dir = collected_data_dir
        self._last_dataset_meta: dict | None = None

    def load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
    ) -> list[Candle]:
        normalized_timeframe = self.normalize_timeframe(timeframe)
        candles, selected_meta = self._load_ohlcv_with_meta(symbol, normalized_timeframe, start_date, end_date)
        self._last_dataset_meta = selected_meta
        return candles

    def load_timeframe_bundle(
        self,
        symbol: str,
        timeframe_mapping: dict[str, str],
        start_date: date,
        end_date: date,
    ) -> dict:
        candles_by_role: dict[str, list[Candle]] = {}
        metadata_by_role: dict[str, dict] = {}
        normalized_mapping: dict[str, str] = {}
        for role, timeframe in timeframe_mapping.items():
            normalized = self.normalize_timeframe(timeframe)
            candles, meta = self._load_ohlcv_with_meta(symbol, normalized, start_date, end_date)
            normalized_mapping[role] = normalized
            candles_by_role[role] = candles
            metadata_by_role[role] = meta
        return {
            "symbol": symbol,
            "mapping": normalized_mapping,
            "candles_by_role": candles_by_role,
            "metadata_by_role": metadata_by_role,
        }

    def normalize_timeframe(self, timeframe: str) -> str:
        tf = timeframe.lower().strip()
        tf = {"1h": "60m", "4h": "240m"}.get(tf, tf)
        allowed = {"1s", "1m", "3m", "5m", "10m", "15m", "30m", "60m", "240m", "1d", "1w", "1mo", "1y"}
        if tf not in allowed:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        return tf

    def _load_ohlcv_with_meta(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
    ) -> tuple[list[Candle], dict | None]:
        file_path, selected_meta = self._resolve_data_path(symbol, timeframe)
        if file_path is None:
            raise FileNotFoundError(f"Missing data file for {symbol}/{timeframe}")
        candles: list[Candle] = []
        with file_path.open("r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                timestamp = datetime.fromisoformat(row["timestamp"])
                day = timestamp.date()
                if day < start_date or day > end_date:
                    continue

                candles.append(
                    Candle(
                        timestamp=timestamp,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )
        return candles, selected_meta

    def list_symbols(self, timeframe: str = "1d") -> list[str]:
        timeframe = self.normalize_timeframe(timeframe)
        symbols: set[str] = set()
        pattern = f"*_{timeframe}.csv"
        for file_path in sorted(self._sample_data_dir.glob(pattern)):
            symbol = file_path.stem.replace(f"_{timeframe}", "")
            symbols.add(symbol)

        if self._collected_data_dir:
            root = self._collected_data_dir / "upbit"
            if root.exists():
                for manifest_path in root.glob(f"*/{timeframe}/manifest.json"):
                    try:
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        if manifest.get("quality_status") != "fail":
                            symbols.add(str(manifest.get("symbol")))
                    except Exception:  # noqa: BLE001
                        continue
        return sorted(symbols)

    def get_last_dataset_meta(self) -> dict | None:
        return self._last_dataset_meta

    def _resolve_data_path(self, symbol: str, timeframe: str) -> tuple[Path | None, dict | None]:
        collected = self._find_collected_data_path(symbol, timeframe)
        if collected is not None and collected[0].exists():
            return collected
        sample = self._sample_data_dir / f"{symbol}_{timeframe}.csv"
        if sample.exists():
            return sample, {
                "source_type": "sample",
                "dataset_id": f"sample__{symbol}__{timeframe}",
                "symbol": symbol,
                "timeframe": timeframe,
                "data_signature": None,
                "quality_status": "pass",
                "path": str(sample),
            }
        for alias in self._symbol_aliases(symbol):
            alias_sample = self._sample_data_dir / f"{alias}_{timeframe}.csv"
            if alias_sample.exists():
                return alias_sample, {
                    "source_type": "sample",
                    "dataset_id": f"sample__{alias}__{timeframe}",
                    "symbol": alias,
                    "timeframe": timeframe,
                    "data_signature": None,
                    "quality_status": "pass",
                    "path": str(alias_sample),
                }
        return None, None

    def _find_collected_data_path(self, symbol: str, timeframe: str) -> tuple[Path, dict] | None:
        if not self._collected_data_dir:
            return None
        root = self._collected_data_dir / "upbit"
        if not root.exists():
            return None
        candidates: list[tuple[str, Path, dict]] = []
        for alias in self._symbol_aliases(symbol):
            manifest = root / alias / timeframe / "manifest.json"
            csv_path = root / alias / timeframe / "candles.csv"
            if manifest.exists() and csv_path.exists():
                try:
                    payload = json.loads(manifest.read_text(encoding="utf-8"))
                    if payload.get("quality_status") == "fail":
                        continue
                    candidates.append((str(payload.get("updated_at", "")), csv_path, payload))
                except Exception:  # noqa: BLE001
                    continue
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        selected = candidates[0]
        payload = selected[2]
        return selected[1], {
            "source_type": "collected",
            "dataset_id": payload.get("dataset_id"),
            "symbol": payload.get("symbol"),
            "timeframe": payload.get("timeframe"),
            "data_signature": payload.get("data_signature"),
            "quality_status": payload.get("quality_status"),
            "path": str(selected[1]),
            "updated_at": payload.get("updated_at"),
        }

    def _symbol_aliases(self, symbol: str) -> list[str]:
        aliases = [symbol]
        if "-" in symbol:
            a, b = symbol.split("-", 1)
            aliases.append(f"{b}-{a}")
        return aliases

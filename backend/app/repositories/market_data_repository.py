import csv
import json
from pathlib import Path
from typing import Any


class MarketDataRepository:
    def __init__(self, index_file: Path, market_root: Path) -> None:
        self._index_file = index_file
        self._market_root = market_root
        self._index_file.parent.mkdir(parents=True, exist_ok=True)
        self._market_root.mkdir(parents=True, exist_ok=True)
        if not self._index_file.exists():
            self._index_file.write_text("[]", encoding="utf-8")

    def dataset_id(self, source: str, symbol: str, timeframe: str) -> str:
        sanitized = symbol.replace("/", "-").replace(":", "-")
        return f"{source}__{sanitized}__{timeframe}"

    def dataset_paths(self, source: str, symbol: str, timeframe: str) -> dict[str, Path]:
        dataset_dir = self._market_root / source / symbol / timeframe
        return {
            "dir": dataset_dir,
            "csv": dataset_dir / "candles.csv",
            "manifest": dataset_dir / "manifest.json",
        }

    def save_rows(self, source: str, symbol: str, timeframe: str, rows: list[dict[str, Any]]) -> Path:
        paths = self.dataset_paths(source, symbol, timeframe)
        paths["dir"].mkdir(parents=True, exist_ok=True)
        with paths["csv"].open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "timestamp": row["timestamp"],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                    }
                )
        return paths["csv"]

    def load_rows(self, source: str, symbol: str, timeframe: str) -> list[dict[str, Any]]:
        paths = self.dataset_paths(source, symbol, timeframe)
        if not paths["csv"].exists():
            return []
        rows: list[dict[str, Any]] = []
        with paths["csv"].open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    {
                        "timestamp": row["timestamp"],
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                    }
                )
        return rows

    def save_manifest(self, source: str, symbol: str, timeframe: str, manifest: dict[str, Any]) -> None:
        paths = self.dataset_paths(source, symbol, timeframe)
        paths["dir"].mkdir(parents=True, exist_ok=True)
        paths["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self._upsert_index(manifest)

    def load_manifest(self, source: str, symbol: str, timeframe: str) -> dict[str, Any] | None:
        paths = self.dataset_paths(source, symbol, timeframe)
        if not paths["manifest"].exists():
            return None
        raw = paths["manifest"].read_text(encoding="utf-8")
        return json.loads(raw)

    def get_by_dataset_id(self, dataset_id: str) -> dict[str, Any] | None:
        for item in self._load_index():
            if item.get("dataset_id") == dataset_id:
                return item
        return None

    def list_datasets(
        self,
        source: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        quality_status: str | None = None,
    ) -> list[dict[str, Any]]:
        items = self._load_index()
        if source:
            items = [i for i in items if i.get("source") == source]
        if symbol:
            items = [i for i in items if i.get("symbol") == symbol]
        if timeframe:
            items = [i for i in items if i.get("timeframe") == timeframe]
        if quality_status:
            items = [i for i in items if i.get("quality_status") == quality_status]
        return items

    def _upsert_index(self, manifest: dict[str, Any]) -> None:
        items = self._load_index()
        updated = False
        for idx, item in enumerate(items):
            if item.get("dataset_id") == manifest["dataset_id"]:
                items[idx] = manifest
                updated = True
                break
        if not updated:
            items.insert(0, manifest)
        items = sorted(items, key=lambda x: x.get("updated_at", ""), reverse=True)
        self._save_index(items[:500])

    def _load_index(self) -> list[dict[str, Any]]:
        raw = self._index_file.read_text(encoding="utf-8")
        return json.loads(raw)

    def _save_index(self, payload: list[dict[str, Any]]) -> None:
        self._index_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


class Top10UniverseRepository:
    def __init__(self, current_file: Path, snapshots_dir: Path) -> None:
        self._current_file = current_file
        self._snapshots_dir = snapshots_dir
        self._current_file.parent.mkdir(parents=True, exist_ok=True)
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self._current_file.exists():
            self._current_file.write_text("{}", encoding="utf-8")

    def get_current(self) -> dict[str, Any] | None:
        raw = self._current_file.read_text(encoding="utf-8")
        if not raw.strip():
            return None
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or not data:
                return None
            return data
        except json.JSONDecodeError:
            return None

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["updated_at"] = datetime.utcnow().isoformat()
        self._current_file.write_text(json.dumps(normalized, indent=2), encoding="utf-8")

        snapshot_name = f"{normalized.get('generated_at', normalized['updated_at']).replace(':', '-')}__{normalized.get('universe_id', 'unknown')}.json"
        snapshot_path = self._snapshots_dir / snapshot_name
        snapshot_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        return normalized

    def list_snapshots(self, limit: int = 20) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        files = sorted(self._snapshots_dir.glob("*.json"), reverse=True)
        for p in files[:limit]:
            try:
                items.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                continue
        return items

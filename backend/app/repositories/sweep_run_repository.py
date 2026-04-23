import json
from pathlib import Path
from typing import Any


class SweepRunRepository:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists():
            self._file_path.write_text("[]", encoding="utf-8")

    def save_run(self, run_data: dict[str, Any]) -> None:
        runs = self._load()
        runs.insert(0, run_data)
        self._save(runs[:100])

    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._load()[:limit]

    def get_by_id(self, sweep_run_id: str) -> dict[str, Any] | None:
        for run in self._load():
            if run.get("sweep_run_id") == sweep_run_id:
                return run
        return None

    def _load(self) -> list[dict[str, Any]]:
        raw = self._file_path.read_text(encoding="utf-8")
        return json.loads(raw)

    def _save(self, payload: list[dict[str, Any]]) -> None:
        self._file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

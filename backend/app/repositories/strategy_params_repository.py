import json
from pathlib import Path
from typing import Any


class StrategyParamsRepository:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._file_path.exists():
            self._file_path.write_text("{}", encoding="utf-8")

    def get(self, strategy_id: str) -> dict[str, Any] | None:
        all_params = self._load()
        return all_params.get(strategy_id)

    def save(self, strategy_id: str, params: dict[str, Any]) -> dict[str, Any]:
        all_params = self._load()
        all_params[strategy_id] = params
        self._save(all_params)
        return params

    def _load(self) -> dict[str, dict[str, Any]]:
        raw = self._file_path.read_text(encoding="utf-8")
        return json.loads(raw)

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self._file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

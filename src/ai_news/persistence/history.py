import json
import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from ai_news.models import DailyRunState, HistoryEntry, RunKind

HISTORY_RETENTION_DAYS = 30


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class StateStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.state_path = directory / "state.json"
        self.history_path = directory / "history.json"

    def load_state(self, digest_date_local: date, run_kind: RunKind, run_id: str) -> DailyRunState:
        if not self.state_path.exists():
            return DailyRunState(
                digest_date_local=digest_date_local.isoformat(),
                run_kind=run_kind,
                run_id=run_id,
            )
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            if raw == {}:
                return DailyRunState(
                    digest_date_local=digest_date_local.isoformat(),
                    run_kind=run_kind,
                    run_id=run_id,
                )
            state = DailyRunState.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"invalid state file: {exc}") from exc
        if state.digest_date_local != digest_date_local.isoformat():
            return DailyRunState(
                digest_date_local=digest_date_local.isoformat(),
                run_kind=run_kind,
                run_id=run_id,
            )
        return state

    def save_state(self, state: DailyRunState) -> None:
        atomic_write_json(self.state_path, state.model_dump(mode="json"))

    def load_history(self) -> list[HistoryEntry]:
        if not self.history_path.exists():
            return []
        try:
            return TypeAdapter(list[HistoryEntry]).validate_json(
                self.history_path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            raise ValueError(f"invalid history file: {exc}") from exc

    def append_history(self, entry: HistoryEntry, today: date) -> list[HistoryEntry]:
        cutoff = today - timedelta(days=HISTORY_RETENTION_DAYS - 1)
        retained = [
            item for item in self.load_history() if date.fromisoformat(item.digest_date_local) >= cutoff
        ]
        retained = [item for item in retained if item.digest_date_local != entry.digest_date_local]
        retained.append(entry)
        retained.sort(key=lambda item: item.digest_date_local)
        atomic_write_json(self.history_path, [item.model_dump(mode="json") for item in retained])
        return retained

    def initialize(self) -> None:
        if not self.state_path.exists():
            atomic_write_json(self.state_path, {})
        if not self.history_path.exists():
            atomic_write_json(self.history_path, [])


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.astimezone(UTC).isoformat() if isinstance(value, datetime) else value.isoformat()
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")

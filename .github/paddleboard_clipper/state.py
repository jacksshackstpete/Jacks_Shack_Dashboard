from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TERMINAL_STATUSES = {"done", "failed"}


@dataclass
class JobRecord:
    source_file: str
    status: str  # uploading | processing | done | failed
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    clips: list[dict[str, Any]] = field(default_factory=list)


class StateStore:
    """Small JSON-backed store so the CLI agent and the Streamlit page agree
    on what's been processed, without needing a database for a folder watcher."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        tmp.replace(self.path)

    def is_processed(self, source_file: str) -> bool:
        record = self._read().get(source_file)
        return bool(record and record.get("status") in _TERMINAL_STATUSES)

    def upsert(self, record: JobRecord) -> None:
        with self._lock:
            data = self._read()
            data[record.source_file] = asdict(record)
            self._write(data)

    def all_records(self) -> list[dict[str, Any]]:
        return sorted(self._read().values(), key=lambda r: r.get("started_at", ""), reverse=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

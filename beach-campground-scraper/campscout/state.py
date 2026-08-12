"""Remembering what we already told you about.

Without this, polling every 10 minutes means the same open pair pages you every
10 minutes until someone books it.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)


class AlertState:
    def __init__(self, path: Path, cooldown_hours: float = 12.0) -> None:
        self.path = Path(path)
        self.cooldown_seconds = cooldown_hours * 3600.0
        self._sent: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._sent = {str(k): float(v) for k, v in (data.get("sent") or {}).items()}
        except (OSError, ValueError, TypeError) as exc:
            # A corrupt state file should degrade to "notify again", never crash
            # the watcher.
            log.warning("could not read state file %s (%s); starting fresh", self.path, exc)
            self._sent = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump({"sent": self._sent}, fh, indent=2, sort_keys=True)
        tmp.replace(self.path)

    def should_notify(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        last = self._sent.get(key)
        return last is None or (now - last) >= self.cooldown_seconds

    def mark_notified(self, keys: Iterable[str], now: float | None = None) -> None:
        now = time.time() if now is None else now
        for key in keys:
            self._sent[key] = now

    def prune(self, keep_seconds: float = 90 * 24 * 3600, now: float | None = None) -> int:
        """Drop entries older than `keep_seconds` so the file cannot grow forever."""
        now = time.time() if now is None else now
        stale = [k for k, ts in self._sent.items() if (now - ts) > keep_seconds]
        for key in stale:
            del self._sent[key]
        return len(stale)

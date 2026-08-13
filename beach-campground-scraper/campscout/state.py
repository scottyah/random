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
        self.runs: dict[str, object] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._sent = {str(k): float(v) for k, v in (data.get("sent") or {}).items()}
            self.runs = dict(data.get("runs") or {})
        except (OSError, ValueError, TypeError) as exc:
            # A corrupt state file should degrade to "notify again", never crash
            # the watcher.
            log.warning("could not read state file %s (%s); starting fresh", self.path, exc)
            self._sent = {}
            self.runs = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump({"sent": self._sent, "runs": self.runs}, fh, indent=2, sort_keys=True)
        tmp.replace(self.path)

    # ---- heartbeat -----------------------------------------------------
    #
    # Without this, "no alerts" is ambiguous: it could mean nothing is
    # available, or it could mean the scraper has been dead for a month. The
    # heartbeat makes the difference observable.

    def record_run(
        self,
        ok: bool,
        pairs_found: int = 0,
        sites_checked: int = 0,
        error: str = "",
        now: float | None = None,
    ) -> None:
        now = time.time() if now is None else now
        self.runs["last_attempt"] = now
        self.runs["total_scans"] = int(self.runs.get("total_scans", 0) or 0) + 1
        if ok:
            self.runs["last_success"] = now
            self.runs["last_pairs_found"] = pairs_found
            self.runs["last_sites_checked"] = sites_checked
            self.runs["last_error"] = ""
        else:
            self.runs["last_error"] = error[:500]
            self.runs["last_failure"] = now

    def record_alert(self, count: int, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self.runs["last_alert"] = now
        self.runs["total_alerts"] = int(self.runs.get("total_alerts", 0) or 0) + count

    @property
    def last_success(self) -> float | None:
        value = self.runs.get("last_success")
        return float(value) if value else None

    def seconds_since_success(self, now: float | None = None) -> float | None:
        now = time.time() if now is None else now
        last = self.last_success
        return None if last is None else now - last

    def _seconds_since(self, key: str, now: float | None = None) -> float | None:
        now = time.time() if now is None else now
        value = self.runs.get(key)
        return (now - float(value)) if value else None

    def seconds_since_attempt(self, now: float | None = None) -> float | None:
        return self._seconds_since("last_attempt", now)

    def seconds_since_alert(self, now: float | None = None) -> float | None:
        return self._seconds_since("last_alert", now)

    def is_stale(self, max_age_hours: float, now: float | None = None) -> bool:
        """True when we have not completed a successful scan recently.

        A never-run watcher counts as stale: that is precisely the state where
        you would wrongly read silence as "nothing available".
        """
        age = self.seconds_since_success(now)
        return age is None or age > (max_age_hours * 3600.0)

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

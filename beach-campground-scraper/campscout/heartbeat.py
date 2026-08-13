"""External dead-man's switch.

A watcher cannot reliably alert you that it has stopped running -- if it is
dead, it is also not sending you that alert. The fix is to invert it: ping an
outside service after every successful scan, and let *that* service alert you
when the pings stop.

Works with healthchecks.io, Better Uptime, Cronitor, or any URL that treats a
GET as "still alive". healthchecks.io has a free tier and needs no client
library:

    heartbeat:
      url: https://hc-ping.com/<your-uuid>
      fail_url: https://hc-ping.com/<your-uuid>/fail   # optional
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)


class Heartbeat:
    def __init__(self, url: str = "", fail_url: str = "", timeout: float = 10.0) -> None:
        self.url = url
        self.fail_url = fail_url or (f"{url.rstrip('/')}/fail" if url else "")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def _ping(self, url: str, label: str) -> bool:
        if not url:
            return False
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                resp.read()
            log.debug("heartbeat %s ping ok", label)
            return True
        except (urllib.error.URLError, OSError) as exc:
            # A failed heartbeat must never take down the scan it is reporting on.
            log.warning("heartbeat %s ping failed: %s", label, exc)
            return False

    def success(self) -> bool:
        return self._ping(self.url, "success")

    def failure(self) -> bool:
        return self._ping(self.fail_url, "failure")


def build_heartbeat(cfg: Optional[dict]) -> Heartbeat:
    cfg = cfg or {}
    return Heartbeat(
        url=str(cfg.get("url", "") or ""),
        fail_url=str(cfg.get("fail_url", "") or ""),
        timeout=float(cfg.get("timeout", 10.0)),
    )

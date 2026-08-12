"""Notification sinks. Config picks which ones are active.

Deliberately no auto-booking here -- see README "About auto-booking".
"""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Iterable, Protocol

from .models import PairHit

log = logging.getLogger(__name__)


def format_subject(hits: list[PairHit]) -> str:
    if len(hits) == 1:
        hit = hits[0]
        return (
            f"🏕 {hit.campground_name}: sites {hit.site_a.label} + {hit.site_b.label} "
            f"open {hit.stay.checkin:%a %b %d}"
        )
    parks = sorted({h.campground_name for h in hits})
    where = parks[0] if len(parks) == 1 else f"{len(parks)} parks"
    return f"🏕 {len(hits)} adjacent site pairs open at {where}"


def format_body(hits: list[PairHit], limit: int = 25) -> str:
    lines: list[str] = []
    for hit in hits[:limit]:
        lines.append(
            f"{hit.campground_name}\n"
            f"  Sites : {hit.site_a.label} + {hit.site_b.label}\n"
            f"  Dates : {hit.stay}\n"
            f"  Why   : {hit.reason_a} / {hit.reason_b} (score {hit.min_score})\n"
            f"  Book  : {hit.booking_url}"
        )
    if len(hits) > limit:
        lines.append(f"...and {len(hits) - limit} more.")
    lines.append("\nBook fast — these go in minutes on a cancellation.")
    return "\n\n".join(lines)


class Notifier(Protocol):
    name: str

    def send(self, subject: str, body: str, hits: list[PairHit]) -> None: ...


class ConsoleNotifier:
    name = "console"

    def send(self, subject: str, body: str, hits: list[PairHit]) -> None:
        print("=" * 72)
        print(subject)
        print("=" * 72)
        print(body)


class NtfyNotifier:
    """ntfy.sh — no account needed, good for phone push."""

    name = "ntfy"

    def __init__(self, topic: str, server: str = "https://ntfy.sh", token: str = "", priority: str = "high"):
        if not topic:
            raise ValueError("ntfy notifier requires a `topic`")
        self.topic = topic
        self.server = server.rstrip("/")
        self.token = token
        self.priority = priority

    def send(self, subject: str, body: str, hits: list[PairHit]) -> None:
        url = f"{self.server}/{self.topic}"
        headers = {
            "Title": subject.encode("ascii", "ignore").decode() or "Campsite alert",
            "Priority": self.priority,
            "Tags": "tent",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if hits and hits[0].booking_url:
            headers["Actions"] = f"view, Open ReserveCalifornia, {hits[0].booking_url}"

        req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
        except (urllib.error.URLError, OSError) as exc:
            log.error("ntfy notification failed: %s", exc)
            raise


class EmailNotifier:
    name = "email"

    def __init__(
        self,
        host: str,
        port: int = 587,
        username: str = "",
        password: str = "",
        sender: str = "",
        recipients: Iterable[str] = (),
        use_tls: bool = True,
    ):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.sender = sender or username
        self.recipients = [r for r in recipients if r]
        self.use_tls = use_tls
        if not self.host or not self.recipients:
            raise ValueError("email notifier requires `host` and at least one recipient")

    def send(self, subject: str, body: str, hits: list[PairHit]) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                if self.use_tls:
                    server.starttls(context=ssl.create_default_context())
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            log.error("email notification failed: %s", exc)
            raise


class WebhookNotifier:
    """Generic JSON POST — Slack/Discord incoming webhooks work as-is."""

    name = "webhook"

    def __init__(self, url: str, template: str = "slack"):
        if not url:
            raise ValueError("webhook notifier requires a `url`")
        self.url = url
        self.template = template

    def send(self, subject: str, body: str, hits: list[PairHit]) -> None:
        if self.template == "discord":
            payload = {"content": f"**{subject}**\n```\n{body}\n```"}
        else:
            payload = {"text": f"*{subject}*\n```\n{body}\n```"}
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
        except (urllib.error.URLError, OSError) as exc:
            log.error("webhook notification failed: %s", exc)
            raise


_REGISTRY = {
    "console": ConsoleNotifier,
    "ntfy": NtfyNotifier,
    "email": EmailNotifier,
    "webhook": WebhookNotifier,
}


def build_notifiers(specs: list[dict]) -> list[Notifier]:
    notifiers: list[Notifier] = []
    for spec in specs:
        spec = dict(spec)
        if not spec.pop("enabled", True):
            continue
        kind = str(spec.pop("type", "")).lower()
        cls = _REGISTRY.get(kind)
        if cls is None:
            log.error("unknown notifier type %r (known: %s)", kind, ", ".join(sorted(_REGISTRY)))
            continue
        try:
            notifiers.append(cls(**spec))
        except (TypeError, ValueError) as exc:
            log.error("could not configure %r notifier: %s", kind, exc)
    if not notifiers:
        log.warning("no notifiers configured; falling back to console")
        notifiers.append(ConsoleNotifier())
    return notifiers


def dispatch(notifiers: list[Notifier], hits: list[PairHit]) -> int:
    """Send to every notifier. One failing sink must not silence the others."""
    if not hits:
        return 0
    subject = format_subject(hits)
    body = format_body(hits)
    delivered = 0
    for notifier in notifiers:
        try:
            notifier.send(subject, body, hits)
            delivered += 1
            log.info("notified via %s", notifier.name)
        except Exception as exc:  # noqa: BLE001 - never let a sink kill the run
            log.error("notifier %s failed: %s", notifier.name, exc)
    return delivered

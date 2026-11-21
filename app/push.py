"""Notifications on the phone without Home Assistant, through ntfy (ntfy.sh or your own server).

Set NTFY_URL to the full address of a topic, e.g. https://ntfy.sh/ladecockpit-7f3k9q (the topic name is
the secret on a public server: make it long and random), and subscribe to the same topic in the ntfy
app. NTFY_TOKEN is for a server that needs an access token. Ladecockpit then sends:

* every new invoice (place, kWh, amount, price per kWh) – like the Home Assistant event,
* a problem (Tesla sign-in expired, syncing fails) and when it is solved again,
* the monthly report on the first of the month.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx

from .config import Settings
from .db import DB

log = logging.getLogger("ladecockpit.push")

KV_SINCE = "ntfy_since"     # sessions that started before this are never sent
KV_SENT = "ntfy_sent"       # ids of the sessions sent lately (JSON list)
KEEP_SENT = 200


def split_url(url: str) -> tuple[str, str] | None:
    """"https://ntfy.sh/my-topic" → ("https://ntfy.sh", "my-topic"); None if it is no topic address."""
    parts = urlsplit((url or "").strip())
    path = parts.path.strip("/")
    if parts.scheme not in ("http", "https") or not parts.netloc or not path or "/" in path:
        return None
    return f"{parts.scheme}://{parts.netloc}", path


class Ntfy:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.s = settings
        self.target = split_url(settings.ntfy_url)
        self.last_error: str | None = None
        self._transport = transport

    @property
    def configured(self) -> bool:
        return self.target is not None

    @property
    def topic_host(self) -> str | None:
        """Where the messages go, without the topic (the topic is the secret)."""
        return urlsplit(self.target[0]).netloc if self.target else None

    async def send(self, title: str, message: str, tags: list[str] | None = None, priority: int = 3) -> bool:
        if not self.target:
            return False
        server, topic = self.target
        headers = {"Content-Type": "application/json"}
        if self.s.ntfy_token:
            headers["Authorization"] = f"Bearer {self.s.ntfy_token}"
        body = {"topic": topic, "title": title[:250], "message": message[:4000], "priority": priority}
        if tags:
            body["tags"] = tags
        try:
            async with httpx.AsyncClient(timeout=15, transport=self._transport) as http:
                r = await http.post(server, content=json.dumps(body), headers=headers)
        except httpx.HTTPError as e:
            self.last_error = f"ntfy not reachable ({e.__class__.__name__})"
            log.warning(self.last_error)
            return False
        if r.status_code >= 400:
            self.last_error = f"ntfy rejected the message (HTTP {r.status_code})"
            log.warning(self.last_error)
            return False
        self.last_error = None
        return True


def pending(db: DB, sessions: list[dict], now: datetime, max_age: timedelta) -> list[dict]:
    """New sessions with a final invoice that were not sent yet. The first call only remembers the
    moment, so the existing history is never sent."""
    since = db.kv_get(KV_SINCE)
    if not since:
        db.kv_set(KV_SINCE, now.isoformat(timespec="seconds"))
        return []
    sent = set(json.loads(db.kv_get(KV_SENT) or "[]"))
    out = []
    for s in sessions:
        if s["session_id"] in sent or not s.get("start_ts") or s.get("kwh") is None or s.get("total") is None:
            continue
        started = datetime.fromisoformat(s["start_ts"])
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started < datetime.fromisoformat(since) or now - started > max_age:
            continue
        out.append(s)
    return sorted(out, key=lambda s: s["start_ts"])


def mark_sent(db: DB, session_id: str) -> None:
    sent = json.loads(db.kv_get(KV_SENT) or "[]")
    sent.append(session_id)
    db.kv_set(KV_SENT, json.dumps(sent[-KEEP_SENT:]))

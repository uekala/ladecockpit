"""Benachrichtigungen aufs Handy ohne Home Assistant, über ntfy (ntfy.sh oder ein eigener Server).

NTFY_URL auf die volle Adresse eines Topics setzen, z. B. https://ntfy.sh/ladecockpit-7f3k9q (auf einem
öffentlichen Server ist der Topic-Name das Geheimnis: lang und zufällig wählen), und in der ntfy-App
dasselbe Topic abonnieren. NTFY_TOKEN ist für einen Server, der einen Zugangstoken verlangt. Ladecockpit
sendet dann:

* jede neue Rechnung (Ort, kWh, Betrag, Preis pro kWh) – wie das Event in Home Assistant,
* ein Problem (Tesla-Anmeldung abgelaufen, Abgleich schlägt fehl) und wenn es wieder behoben ist,
* den Monatsbericht am Monatsersten.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx

from .config import Settings
from .db import DB

log = logging.getLogger("ladecockpit.push")

KV_SINCE = "ntfy_since"     # Ladungen, die davor begannen, werden nie gesendet
KV_SENT = "ntfy_sent"       # IDs der zuletzt gesendeten Ladungen (JSON-Liste)
KEEP_SENT = 200


def split_url(url: str) -> tuple[str, str] | None:
    """„https://ntfy.sh/my-topic“ → ("https://ntfy.sh", "my-topic"); None, wenn es keine Topic-Adresse ist."""
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
        """Wohin die Nachrichten gehen, ohne das Topic (das Topic ist das Geheimnis)."""
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
    """Neue Ladungen mit endgültiger Rechnung, die noch nicht gesendet wurden. Der erste Aufruf merkt sich
    nur den Zeitpunkt, die vorhandene Historie wird also nie gesendet."""
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
            started = started.replace(tzinfo=UTC)
        if started < datetime.fromisoformat(since) or now - started > max_age:
            continue
        out.append(s)
    return sorted(out, key=lambda s: s["start_ts"])


def mark_sent(db: DB, session_id: str) -> None:
    sent = json.loads(db.kv_get(KV_SENT) or "[]")
    sent.append(session_id)
    db.kv_set(KV_SENT, json.dumps(sent[-KEEP_SENT:]))

import asyncio
import dataclasses
import json
from datetime import UTC, datetime, timedelta

import httpx

from app.push import KV_SINCE, Ntfy, mark_sent, pending, split_url
from app.reports import MonthReporter
from app.sync import SyncService

NOW = datetime(2026, 11, 21, 12, tzinfo=UTC)


def test_topic_address():
    assert split_url("https://ntfy.sh/ladecockpit-7f3k9q") == ("https://ntfy.sh", "ladecockpit-7f3k9q")
    assert split_url(" http://192.168.1.5:8090/lc/ ") == ("http://192.168.1.5:8090", "lc")
    for bad in ("", "ntfy.sh/topic", "https://ntfy.sh", "https://ntfy.sh/a/b", "ftp://x/y"):
        assert split_url(bad) is None


def _ntfy(settings, seen, status=200, token=""):
    def handler(request):
        seen.append((str(request.url), request.headers.get("authorization"), json.loads(request.content)))
        return httpx.Response(status)
    s = dataclasses.replace(settings, ntfy_url="https://ntfy.example.org/ladecockpit-abc", ntfy_token=token)
    return Ntfy(s, transport=httpx.MockTransport(handler))


def test_send_posts_json_to_the_server_with_the_token(settings):
    seen = []
    push = _ntfy(settings, seen, token="tk_secret")
    assert push.configured and push.topic_host == "ntfy.example.org"
    assert asyncio.run(push.send("⚡ Neue Rechnung", "38,2 kWh · 14,20 €", tags=["zap"]))
    url, auth, body = seen[0]
    assert url == "https://ntfy.example.org" and auth == "Bearer tk_secret"
    assert body == {"topic": "ladecockpit-abc", "title": "⚡ Neue Rechnung", "message": "38,2 kWh · 14,20 €",
                    "priority": 3, "tags": ["zap"]}
    failing = _ntfy(settings, [], status=403)
    assert not asyncio.run(failing.send("t", "m")) and "403" in failing.last_error
    assert not Ntfy(dataclasses.replace(settings, ntfy_url="")).configured


def _session(sid, hours_ago, kwh=30.0, total=12.0):
    return {"session_id": sid, "start_ts": (NOW - timedelta(hours=hours_ago)).isoformat(), "kwh": kwh, "total": total}


def test_only_new_final_sessions_are_sent_once(db):
    sessions = [_session("old", 50), _session("new", 2), _session("open", 1, kwh=None)]
    assert pending(db, sessions, NOW - timedelta(hours=10), timedelta(hours=72)) == []   # first call: remember
    assert db.kv_get(KV_SINCE)
    assert [s["session_id"] for s in pending(db, sessions, NOW, timedelta(hours=72))] == ["new"]
    mark_sent(db, "new")
    assert pending(db, sessions, NOW, timedelta(hours=72)) == []
    assert pending(db, [_session("late", 80)], NOW, timedelta(hours=72)) == []          # too old


class _NoHA:
    configured = False


def test_sync_sends_new_invoices_and_problems_to_the_phone(settings, db):
    seen = []
    push = _ntfy(settings, seen)
    service = SyncService(dataclasses.replace(settings, lang="de", notify_problems=True), db, None, _NoHA(), push)
    db.kv_set(KV_SINCE, (datetime.now(UTC) - timedelta(days=1)).isoformat())
    service.event_payload = lambda s: {"site": "Moers, Germany", "text": "30,0 kWh · 12,00 €", "slow": False}
    db.sessions = lambda: [{**_session("a", 0), "start_ts": (datetime.now(UTC) - timedelta(hours=2)).isoformat()}]
    assert asyncio.run(service.push_phone()) == 1
    assert seen[-1][2]["title"] == "⚡ Neue Rechnung · Moers, Germany"
    assert asyncio.run(service.push_phone()) == 0
    asyncio.run(service.report("auth"))
    assert "Tesla-Anmeldung" in seen[-1][2]["message"] and seen[-1][2]["priority"] == 4
    asyncio.run(service.report(None))
    assert seen[-1][2]["message"].startswith("Wieder alles in Ordnung")


def test_monthly_report_goes_to_the_phone_without_home_assistant(settings, db):
    seen = []
    push = _ntfy(settings, seen)

    async def build():
        return {"setup": {}, "monthly": [{"key": "2026-10", "label": "Okt", "sessions": 3, "kwh": 90.0, "cost": 36.0,
                                         "avg_price": 0.4, "distance": 600, "per_100": 6.0}]}

    reporter = MonthReporter(dataclasses.replace(settings, lang="de", month_report=True), db, _NoHA(), build, push)
    db.kv_set("report_month", "2026-10")
    report = asyncio.run(reporter.check(now=datetime(2026, 11, 1, 9, tzinfo=UTC)))
    assert report and seen and seen[-1][2]["title"] == report["title"]

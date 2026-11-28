"""TeslaClient gegen eine nachgebildete Fleet API: abgelaufene Tokens, der Zeitfilter, Seiten und das Budget."""
import asyncio
import dataclasses
import time
from datetime import UTC, datetime

import httpx
import pytest

from app import tesla as tesla_mod
from app.homeassistant import HAClient
from app.sync import SyncService
from app.tesla import PAGE_SIZE, BudgetExceeded, TeslaClient, TeslaError


def _client(settings, db, handler, **changes):
    s = dataclasses.replace(settings, **changes) if changes else settings
    client = TeslaClient(s, db, transport=httpx.MockTransport(handler))
    db.kv_set("tesla_access_token", "old-access")
    db.kv_set("tesla_refresh_token", "r1")
    db.kv_set("tesla_access_expires", str(time.time() + 3600))
    return client


def _page(ids, total=None):
    body = {"data": [{"sessionId": i} for i in ids]}
    if total is not None:
        body["totalResults"] = total
    return httpx.Response(200, json={"response": body})


def test_expired_access_token_is_refreshed_once_and_the_request_repeated(settings, db):
    seen = []

    def handler(request):
        if request.url.path.endswith("/token"):
            seen.append(("token", None))
            return httpx.Response(200, json={"access_token": "new-access", "refresh_token": "r2", "expires_in": 3600})
        seen.append(("data", request.headers["authorization"]))
        if request.headers["authorization"] == "Bearer old-access":
            return httpx.Response(401)
        return _page(["s1"], total=1)

    client = _client(settings, db, handler)
    items = asyncio.run(client.charging_history())
    assert [i["sessionId"] for i in items] == ["s1"]
    assert seen == [("data", "Bearer old-access"), ("token", None), ("data", "Bearer new-access")]
    assert db.kv_get("tesla_refresh_token") == "r2"                   # einmalig: Der neueste wird behalten
    assert client.calls_used() == 2                                    # both data requests count


def test_second_401_after_a_refresh_gives_up(settings, db):
    def handler(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "new-access", "expires_in": 3600})
        return httpx.Response(401)

    client = _client(settings, db, handler)
    with pytest.raises(TeslaError, match="HTTP 401"):
        asyncio.run(client.charging_history())
    assert db.kv_get("tesla_refresh_token") == "r1"                   # kein neuer geschickt: Der alte bleibt


def test_rejected_time_filter_is_asked_again_without_it(settings, db):
    params = []

    def handler(request):
        params.append(dict(request.url.params))
        if "startTime" in request.url.params:
            return httpx.Response(400, text="invalid startTime")
        return _page(["s1", "s2"], total=2)

    client = _client(settings, db, handler, tesla_vin="5YJ3E7EB0KF000000")
    start = datetime(2026, 11, 18, 10, tzinfo=UTC)
    items = asyncio.run(client.charging_history(start))
    assert len(items) == 2
    assert params[0]["startTime"] == "2026-11-18T10:00:00+00:00"
    assert "startTime" not in params[1]
    assert params[1]["vin"] == "5YJ3E7EB0KF000000" and params[1]["pageSize"] == str(PAGE_SIZE)


def test_other_errors_with_a_time_filter_are_not_hidden(settings, db):
    client = _client(settings, db, lambda request: httpx.Response(500, text="boom"))
    with pytest.raises(TeslaError, match="HTTP 500"):
        asyncio.run(client.charging_history(datetime(2026, 11, 18, tzinfo=UTC)))
    assert client.calls_used() == 1


def test_pages_are_fetched_until_the_total_and_duplicates_dropped(settings, db):
    first = [f"a{i}" for i in range(PAGE_SIZE)]
    pages = {
        None: _page(first, total=PAGE_SIZE + 3),
        "1": _page([*first[-2:], "b1", "b2", "b3"]),         # Tesla counting from 0: page 1 overlaps
    }
    asked = []

    def handler(request):
        no = request.url.params.get("pageNo")
        asked.append(no)
        return pages[no]

    client = _client(settings, db, handler)
    items = asyncio.run(client.charging_history())
    ids = [i["sessionId"] for i in items]
    assert len(ids) == PAGE_SIZE + 3 and len(set(ids)) == len(ids)
    assert asked == [None, "1"]                                        # die kurze Seite beendet es


def test_paging_without_a_total_stops_at_a_page_with_nothing_new(settings, db):
    full = [f"a{i}" for i in range(PAGE_SIZE)]
    asked = []

    def handler(request):
        no = request.url.params.get("pageNo")
        asked.append(no)
        if no in (None, "1"):
            return _page(full)                  # page 1 repeats page 0
        if no == "2":
            return _page([f"b{i}" for i in range(PAGE_SIZE)])
        return _page(full)                      # page 3 only repeats: stop

    client = _client(settings, db, handler)
    items = asyncio.run(client.charging_history())
    assert len(items) == 2 * PAGE_SIZE
    assert asked == [None, "1", "2", "3"]


def test_paging_stops_after_max_pages(settings, db, monkeypatch):
    monkeypatch.setattr(tesla_mod, "MAX_PAGES", 2)
    counter = {"n": 0}

    def handler(request):
        counter["n"] += 1
        return _page([f"p{counter['n']}-{i}" for i in range(PAGE_SIZE)], total=10_000)

    client = _client(settings, db, handler)
    items = asyncio.run(client.charging_history())
    assert counter["n"] == 3                                           # first page + pages 1 and 2
    assert len(items) == 3 * PAGE_SIZE


def test_budget_reached_asks_tesla_no_more(settings, db):
    calls = []
    client = _client(settings, db, lambda request: calls.append(1) or _page([], total=0), api_budget=2)
    for _ in range(2):
        asyncio.run(client.charging_history())
    with pytest.raises(BudgetExceeded):
        asyncio.run(client.invoice_pdf("c1"))
    assert len(calls) == 2


def test_sync_reports_the_budget_and_does_not_count_it_as_failure(settings, db):
    client = _client(settings, db, lambda request: _page([], total=0), api_budget=0)
    sync = SyncService(settings, db, client, HAClient(dataclasses.replace(settings, ha_url="", ha_token="")))
    asyncio.run(sync.tick())
    assert sync.failures == 0
    assert "budget" in sync.last_error.lower()
    assert db.kv_get("problem_kind") == "budget"


def test_sync_without_tesla_does_nothing(settings, db):
    calls = []
    client = TeslaClient(settings, db, transport=httpx.MockTransport(lambda request: calls.append(1)))
    sync = SyncService(settings, db, client, HAClient(dataclasses.replace(settings, ha_url="", ha_token="")))
    asyncio.run(sync.tick())
    assert calls == [] and sync.last_sync is None and sync.failures == 0

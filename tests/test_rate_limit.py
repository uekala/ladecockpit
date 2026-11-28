"""HTTP 429 von Tesla: so lange warten, wie Tesla verlangt, statt sofort erneut zu fragen."""
import asyncio
import dataclasses
import time
from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest

from app.homeassistant import HAClient
from app.sync import SyncService
from app.tesla import (
    HISTORY_PATH,
    RATE_LIMIT_DEFAULT_S,
    RATE_LIMIT_MAX_S,
    RateLimited,
    TeslaClient,
    retry_after_seconds,
)


def _tesla(settings, db, handler):
    client = TeslaClient(settings, db, transport=httpx.MockTransport(handler))
    db.kv_set("tesla_access_token", "test-access-token")
    db.kv_set("tesla_refresh_token", "test-refresh-token")
    db.kv_set("tesla_access_expires", str(time.time() + 3600))
    return client


def test_retry_after_in_seconds_or_as_date():
    now = datetime(2026, 11, 21, 12, tzinfo=UTC).timestamp()
    assert retry_after_seconds("120", now) == 120
    assert retry_after_seconds(" 30 ", now) == 30
    assert retry_after_seconds(format_datetime(datetime(2026, 11, 21, 12, 10, tzinfo=UTC), usegmt=True),
                               now) == 600
    assert retry_after_seconds("Fri, 20 Nov 2026 12:00:00 GMT", now) == 0        # already over
    for missing in (None, "", "soon", "nan"):
        assert retry_after_seconds(missing, now) == RATE_LIMIT_DEFAULT_S
    assert retry_after_seconds("9999999", now) == RATE_LIMIT_MAX_S


def test_429_pauses_requests_until_retry_after(settings, db):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "120"}, text="Too Many Requests")
        return httpx.Response(200, json={"response": {"data": [], "totalResults": 0}})

    client = _tesla(settings, db, handler)
    with pytest.raises(RateLimited):
        asyncio.run(client.charging_history())
    assert calls == [HISTORY_PATH]
    retry_at = float(db.kv_get("tesla_retry_at"))
    assert 110 < retry_at - time.time() <= 120

    with pytest.raises(RateLimited):                  # noch in der Pause: Tesla wird nicht gefragt
        asyncio.run(client.invoice_pdf("invoice-1"))
    assert len(calls) == 1

    db.kv_set("tesla_retry_at", str(time.time() - 1))  # pause over
    assert asyncio.run(client.charging_history()) == []
    assert len(calls) == 2


def test_429_is_logged_as_a_call(settings, db):
    client = _tesla(settings, db, lambda request: httpx.Response(429))
    with pytest.raises(RateLimited):
        asyncio.run(client.charging_history())
    assert client.calls_used() == 1
    assert 290 < float(db.kv_get("tesla_retry_at")) - time.time() <= RATE_LIMIT_DEFAULT_S


def test_sync_counts_a_rate_limit_as_failure_without_traceback(settings, db, caplog):
    client = _tesla(settings, db, lambda request: httpx.Response(429, headers={"Retry-After": "60"}))
    ha = HAClient(dataclasses.replace(settings, ha_url="", ha_token=""))
    sync = SyncService(settings, db, client, ha)
    with caplog.at_level("WARNING"):
        asyncio.run(sync.tick())
    assert sync.failures == 1
    assert "HTTP 429" in sync.last_error
    assert "Sync paused" in caplog.text
    assert not any(r.exc_info for r in caplog.records)
    for _ in range(2):
        asyncio.run(sync.tick())
    assert sync.failures == 3
    assert db.kv_get("problem_kind") == "sync"

import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone

from app.sync import SyncService


def raw_session(sid, start, kwh=20.0, rate=0.4, fees=True):
    return {
        "sessionId": sid,
        "siteLocationName": f"Site {sid}",
        "chargeStartDateTime": start.isoformat(),
        "chargeStopDateTime": (start + timedelta(minutes=20)).isoformat(),
        "fees": [{"feeType": "CHARGING", "currencyCode": "EUR", "uom": "kwh",
                  "usageBase": kwh, "totalDue": round(kwh * rate, 2)}] if fees else [],
        "invoices": [],
    }


class FakeTesla:
    connected = True
    auth_error = None

    def __init__(self):
        self.items = []

    async def charging_history(self, start_time=None):
        return list(self.items)


class FakeHA:
    configured = True

    def __init__(self):
        self.events = []

    async def fire_event(self, event_type, data):
        self.events.append((event_type, data))
        return True


def make(settings, db):
    tesla, ha = FakeTesla(), FakeHA()
    return SyncService(settings, db, tesla, ha), tesla, ha


def test_first_sync_imports_without_sending(settings, db):
    sync, tesla, ha = make(settings, db)
    old = datetime.now(timezone.utc) - timedelta(days=3)
    tesla.items = [raw_session(1, old), raw_session(2, old + timedelta(hours=5))]
    assert asyncio.run(sync.sync_once()) == 2
    assert ha.events == []
    assert {s["push_state"] for s in db.sessions()} == {"backfill"}


def test_new_session_is_sent_once(settings, db):
    sync, tesla, ha = make(settings, db)
    asyncio.run(sync.sync_once())  # sets push_since
    tesla.items = [raw_session(7, datetime.now(timezone.utc) + timedelta(seconds=5), kwh=22.5, rate=0.52)]
    asyncio.run(sync.sync_once())
    asyncio.run(sync.sync_once())
    assert len(ha.events) == 1
    event_type, data = ha.events[0]
    assert event_type == settings.ha_event
    assert data["kwh"] == 22.5 and data["total"] == 11.7 and data["price_per_kwh"] == 0.52
    assert data["site"] == "Site 7"
    assert "22.5 kWh" in data["text"] and "€11.70" in data["text"]


def test_pending_billing_is_sent_when_final(settings, db):
    sync, tesla, ha = make(settings, db)
    asyncio.run(sync.sync_once())
    start = datetime.now(timezone.utc) + timedelta(seconds=5)
    tesla.items = [raw_session(8, start, fees=False)]
    asyncio.run(sync.sync_once())
    assert ha.events == []
    tesla.items = [raw_session(8, start)]
    asyncio.run(sync.sync_once())
    assert len(ha.events) == 1


def test_old_unsent_session_goes_stale(settings, db):
    sync, tesla, ha = make(dataclasses.replace(settings, push_max_age_h=24), db)
    db.kv_set("push_since", (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(timespec="seconds"))
    tesla.items = [raw_session(9, datetime.now(timezone.utc) - timedelta(days=4))]
    asyncio.run(sync.sync_once())
    assert ha.events == []
    assert db.session("9")["push_state"] == "stale"


def test_german_event_text(settings, db):
    sync, tesla, ha = make(dataclasses.replace(settings, lang="de"), db)
    asyncio.run(sync.sync_once())
    tesla.items = [raw_session(10, datetime.now(timezone.utc) + timedelta(seconds=5), kwh=18.0, rate=0.37)]
    asyncio.run(sync.sync_once())
    assert ha.events[0][1]["text"].startswith("18,0 kWh · 6,66 € · 0,37 €/kWh")

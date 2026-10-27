import dataclasses
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.demo import build_demo
from app.vehicle import _until, live_charge, soc_rate
from app.watcher import FAST_POLL_SECONDS, Watcher

NOW = datetime(2026, 10, 27, 14, tzinfo=timezone.utc)


def test_time_to_full_as_timestamp_or_duration():
    at = NOW + timedelta(minutes=25)
    assert _until(at.isoformat(), None, None, NOW) == at
    assert _until("2026-10-27T13:00:00+00:00", None, None, NOW) is None        # already passed
    assert _until("2026-10-27T15:00:00", None, None, NOW) is None              # no time zone: unclear
    assert _until("0.5", 0.5, "h", NOW) == NOW + timedelta(minutes=30)
    assert _until("45", 45.0, "min", NOW) == NOW + timedelta(minutes=45)
    assert _until("1.5", 1.5, None, NOW) == NOW + timedelta(hours=1.5)        # bare number: hours
    assert _until("0", 0.0, "h", NOW) is None
    assert _until("90", 90.0, "h", NOW) is None                                # more than two days: stale
    assert _until("unavailable", None, None, NOW) is None


def test_rate_from_the_rising_battery_level():
    soc = [(NOW - timedelta(minutes=50), 60.0), (NOW - timedelta(minutes=30), 31.0),
           (NOW - timedelta(minutes=20), 40.0), (NOW - timedelta(minutes=10), 49.0)]
    # the run starts after the drop: 31 → 58 % in 30 minutes
    assert soc_rate(soc, 58.0, NOW) == 54.0
    assert soc_rate(soc[-1:], 49.0, NOW) is None                               # one reading only
    assert soc_rate([(NOW - timedelta(minutes=5), 48.0)], 50.0, NOW) is None   # too short


def charge(**kw):
    base = dict(raw={"charging": "Charging"}, values={}, units={}, charging_value="charging", soc=50.0,
                target=80, soc_readings=[], kwh_pct=None, now=NOW)
    return live_charge(**{**base, **kw})


def test_live_charge():
    assert charge(raw={}) == {"charging": None}
    assert charge(raw={"charging": "unavailable"}) == {"charging": None}
    assert charge(raw={"charging": "complete"}) == {"charging": False}
    c = charge(values={"charge_power": 11000.0}, units={"charge_power": "W"}, kwh_pct=0.75)
    # 30 % × 0.75 kWh at 11 kW ≈ 2 h 03 min
    assert c["charging"] is True and c["power"] == 11.0
    assert c["finish"] == (NOW + timedelta(hours=30 * 0.75 / 11)).isoformat(timespec="seconds")
    at = NOW + timedelta(minutes=40)
    c = charge(raw={"charging": "charging", "time_to_full": at.isoformat()}, values={"charge_power": 104.0}, kwh_pct=0.75)
    assert c["finish"] == at.isoformat(timespec="seconds")                     # the car's own value wins
    c = charge(soc_readings=[(NOW - timedelta(minutes=30), 35.0)])
    assert c["rate"] == 30.0 and c["finish"] == (NOW + timedelta(hours=1)).isoformat(timespec="seconds")
    assert charge(soc=85.0)["finish"] is None                                   # above the limit already


def test_demo_charges_and_counts_the_next_stop_from_the_limit(settings):
    d = build_demo(dataclasses.replace(settings, soc_target=80))
    st = d["status"]
    assert st["charging"] is True and st["soc_source"] == "live" and st["power"] == 104.0
    assert st["finish"] and st["rate"]
    assert d["forecast"]["date_label"]


class FakeSync:
    def __init__(self):
        self.bursts = 0

    def trigger_burst(self):
        self.bursts += 1


class FakeHA:
    def __init__(self, state):
        self.state = state

    async def live(self):
        return {"available": True, "values": {}, "raw": {"charging": self.state}, "units": {}}


def test_watcher_polls_faster_while_charging(settings, db):
    import asyncio
    sync = FakeSync()
    w = Watcher(dataclasses.replace(settings, ha_poll_seconds=60, charging_value="charging"), db, FakeHA("charging"), sync)
    assert w.interval() == 60
    asyncio.run(w.poll_once(now=NOW))
    assert w.interval() == FAST_POLL_SECONDS
    w.ha = FakeHA("complete")
    asyncio.run(w.poll_once(now=NOW + timedelta(minutes=1)))
    assert w.interval() == 60 and sync.bursts == 1                              # and the invoice is looked for


def test_old_look_name_still_works():
    from app.main import app, db as app_db
    with TestClient(app) as client:
        app_db.kv_set("ui_look", "modern")                                       # saved by 0.9 or 0.10
        assert client.get("/api/dashboard").json()["look"] == "dynamic"
        app_db.kv_set("ui_look", "classic")

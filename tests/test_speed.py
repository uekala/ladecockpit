import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone

from app import vehicle
from app.demo import build_demo
from app.entities import build_states
from app.sync import SyncService

T0 = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


def _s(sid, day, kwh, minutes, site="Willich, Germany"):
    start = T0 + timedelta(days=day)
    return {"session_id": sid, "site": site, "start_ts": start.isoformat(),
            "stop_ts": (start + timedelta(minutes=minutes)).isoformat(), "kwh": kwh}


WILLICH = [
    _s("a", 0, 51.1, 25),   # ~123 kW
    _s("b", 1, 55.8, 27),   # ~124 kW
    _s("c", 2, 37.4, 48),   # ~47 kW – much slower
    _s("d", 3, 53.4, 31),   # ~103 kW
]


def test_slow_against_the_usual_power_at_the_site():
    sessions = WILLICH + [
        _s("e", 4, 6.0, 6),                      # short session: not compared
        _s("f", 5, 40.0, 60, site="Elsewhere"),  # no other sessions there
    ]
    speed = vehicle.charging_speed(sessions, [])
    assert speed["c"] == {"kw": 47, "typical_kw": 123, "slow": True, "start_soc": None}
    assert speed["a"]["typical_kw"] == 103 and not speed["a"]["slow"]
    assert not any(speed[k]["slow"] for k in "abdef")
    assert speed["e"]["typical_kw"] is None and speed["f"]["typical_kw"] is None


def test_needs_two_other_sessions_and_a_duration():
    speed = vehicle.charging_speed(WILLICH[1:3] + [{**_s("x", 9, 30.0, 20), "stop_ts": None}], [])
    assert speed["c"]["typical_kw"] is None and not speed["c"]["slow"]
    assert "x" not in speed


def test_full_battery_at_the_start_is_not_slow():
    start_c = datetime.fromisoformat(WILLICH[2]["start_ts"])
    soc = [(start_c - timedelta(minutes=40), 62.0)]
    speed = vehicle.charging_speed(WILLICH, soc)
    assert speed["c"]["start_soc"] == 62 and not speed["c"]["slow"] and speed["c"]["typical_kw"] == 123
    # ... and still counts for what is usual at the site.
    assert speed["a"]["typical_kw"] == 103
    # A reading from long before the start says nothing about it.
    speed = vehicle.charging_speed(WILLICH, [(start_c - timedelta(hours=5), 62.0)])
    assert speed["c"]["start_soc"] is None and speed["c"]["slow"]


def test_dashboard_entity_and_tip_in_the_demo(settings):
    for lang in ("en", "de"):
        d = build_demo(dataclasses.replace(settings, lang=lang))
        slow = [s for s in d["sessions"] if s["slow"]]
        assert len(slow) == 1 and slow[0]["site"] == "Mainz"
        assert slow[0]["avg_kw"] == 38 and slow[0]["typical_kw"] == 81
        tip = next(i["text"] for i in d["insights"] if i["kind"] == "speed")
        assert "Mainz" in tip and "38" in tip and "81" in tip
        attrs = build_states(d, lang)["sensor.ladecockpit_last_charge"][1]
        assert attrs["slow"] is False and "typical_power_kw" in attrs and "start_soc" in attrs


class _HA:
    configured = True

    def __init__(self):
        self.events = []

    async def fire_event(self, event_type, data):
        self.events.append(data)
        return True


def test_invoice_event_says_whether_the_session_was_slow(settings, db):
    ha = _HA()
    sync = SyncService(settings, db, None, ha)
    for s in WILLICH:
        db.upsert_session({**s, "total": 10.0, "price": 0.45, "currency": "EUR", "invoices": "[]"}, "new")
    db.kv_set("push_since", "2000-01-01T00:00:00+00:00")
    sync.s = dataclasses.replace(settings, push_max_age_h=24 * 3650)
    asyncio.run(sync.push_pending())
    by_kwh = {e["kwh"]: e for e in ha.events}
    assert by_kwh[37.4]["slow"] is True and by_kwh[37.4]["avg_power_kw"] == 47 and by_kwh[37.4]["typical_power_kw"] == 123
    assert by_kwh[51.1]["slow"] is False and by_kwh[51.1]["avg_power_kw"] == 123

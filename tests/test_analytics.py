import dataclasses
from datetime import datetime, timedelta, timezone

from app import i18n
from app.analytics import build_dashboard
from app.demo import build_demo


def test_money_and_numbers():
    assert i18n.money("de", 1234.5, "EUR") == "1.234,50 €"
    assert i18n.money("en", 1234.5, "EUR") == "€1,234.50"
    assert i18n.money("en", 0.37, "USD") == "$0.37"
    assert i18n.money("en", 2, "CHF") == "2.00 CHF"
    assert i18n.num("de", 7.45, 1) == "7,5" or i18n.num("de", 7.45, 1) == "7,4"


def test_demo_dashboard_en_and_de(settings):
    for lang in ("en", "de"):
        d = build_demo(dataclasses.replace(settings, lang=lang))
        assert d["lang"] == lang
        assert d["last_charge"]["kwh"] == 18.0
        assert d["forecast"]["days_to_floor"] is not None
        assert len(d["slots"]) == 5
        # (month-dependent values are not asserted: the demo is relative to "now")
        assert {i["kind"] for i in d["insights"]} >= {"slot", "site", "idle", "network"}
        assert d["reconcile"]["inv_sessions"] == 10
        assert set(d["totals"]["by_network"]) == {"supercharger", "multipass"}


def _session(sid, start, kwh, total):
    return {"session_id": sid, "site": "S", "start_ts": start.isoformat(timespec="seconds"),
            "stop_ts": None, "kwh": kwh, "charge_cost": total, "idle_fee": 0.0, "total": total,
            "currency": "EUR", "price": total / kwh, "invoices": [], "push_state": "pushed"}


def test_cost_per_100_only_counts_sessions_after_first_odometer_reading(settings):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    sessions = [
        _session("a", datetime(2026, 10, 3, 18, tzinfo=timezone.utc), 40, 20.0),   # before tracking
        _session("b", datetime(2026, 10, 15, 18, tzinfo=timezone.utc), 30, 12.0),  # after tracking
    ]
    readings = {
        "soc": [], "soc_last": None, "range_last": None,
        "odometer": [(datetime(2026, 10, 10, tzinfo=timezone.utc), 1000.0),
                     (datetime(2026, 10, 20, tzinfo=timezone.utc), 1200.0)],
    }
    d = build_dashboard(sessions=sessions, live={"values": {}, "units": {"odometer": "km"}},
                        readings=readings, settings=settings, meta={}, now=now)
    assert d["month"]["distance"] == 200
    assert d["month"]["per_100"] == 6.0          # 12 € / 200 km, session "a" left out
    assert d["month"]["cost"] == 32.0
    assert d["reconcile"] is None                  # no HA totals configured


def test_forecast_from_readings(settings):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    soc = [(now - timedelta(days=4 - i), 70 - 8 * i) for i in range(5)]   # 8 %/day over 4 days
    readings = {"soc": soc, "soc_last": soc[-1], "range_last": None, "odometer": []}
    d = build_dashboard(sessions=[], live={"values": {}}, readings=readings,
                        settings=dataclasses.replace(settings, soc_floor=10), meta={}, now=now)
    assert d["status"]["soc"] == 38 and d["status"]["soc_source"] == "last"
    assert d["forecast"]["rate_pct_day"] == 8.0
    assert d["forecast"]["days_to_floor"] == 3.5
    assert d["forecast"]["calendar_days"] == 4   # Oct 20 14:00 + 3.5 d = Oct 24 04:00 local

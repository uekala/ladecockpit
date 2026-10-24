import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone

from app.analytics import build_dashboard
from app.entities import build_states
from app.reports import EVENT, MonthReporter, build_report

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)


def _s(sid, start, kwh, price, site="Hillcrest, Germany", minutes=30):
    total = round(kwh * price, 2)
    return {"session_id": sid, "site": site, "start_ts": start.isoformat(timespec="seconds"),
            "stop_ts": (start + timedelta(minutes=minutes)).isoformat(timespec="seconds"),
            "kwh": kwh, "charge_cost": total, "idle_fee": 0.0, "total": total, "currency": "EUR",
            "price": price, "invoices": [], "push_state": "pushed", "network": "supercharger"}


def _sessions():
    utc = timezone.utc
    return [
        _s("1", datetime(2026, 10, 22, 20, 7, tzinfo=utc), 40.0, 0.22),            # 22:07 local, cheap
        _s("2", datetime(2026, 10, 20, 14, 33, tzinfo=utc), 50.0, 0.37, "Willich, Germany"),
        _s("3", datetime(2026, 10, 15, 16, 58, tzinfo=utc), 50.0, 0.37, "Willich, Germany"),
        _s("4", datetime(2026, 10, 7, 17, 43, tzinfo=utc), 40.0, 0.37, "Willich, Germany"),
        _s("5", datetime(2026, 9, 29, 19, 36, tzinfo=utc), 58.0, 0.22),
    ]


def _readings():
    soc = [(NOW - timedelta(days=6 - i), 90.0 - 10 * i) for i in range(7)]   # 10 % per day
    odo = [(datetime(2026, 9, 28, 8, tzinfo=timezone.utc) + timedelta(days=i), 1000.0 + 50 * i) for i in range(26)]
    return {"soc": soc, "soc_last": soc[-1], "range_last": None, "odometer": odo}


def _dash(settings, values=None):
    live = {"values": {"soc": 30.0, **(values or {})}, "units": {"odometer": "km"}}
    return build_dashboard(sessions=_sessions(), live=live, readings=_readings(),
                           settings=dataclasses.replace(settings, lang="de"), meta={}, now=NOW)


def test_fuel_comparison_and_projection(settings):
    d = _dash(dataclasses.replace(settings, fuel_consumption=8.0, fuel_price=2.0))
    m = d["month"]
    assert d["compare"]["fuel"] == {"consumption": 8.0, "price": 2.0, "per_100": 16.0}
    assert m["fuel_equivalent"] == round(16.0 * m["distance"] / 100, 2)
    assert m["savings"] == round((16.0 - m["per_100"]) * m["distance"] / 100, 2) and m["savings"] > 0
    assert any(i["kind"] == "fuel" for i in d["insights"])
    p = d["projection"]
    assert p["basis_days"] == 25 and p["distance"] == 18200          # 50 km/day
    assert p["savings"] is not None and p["cost"] < p["fuel_cost"]
    # entity values override the fixed ones; without any value there is no comparison
    d2 = _dash(settings, {"fuel_consumption": 6.0, "fuel_price": 1.5})
    assert d2["compare"]["fuel"]["per_100"] == 9.0
    d3 = _dash(settings)
    assert d3["compare"]["fuel"] is None and d3["month"]["savings"] is None
    assert d3["projection"]["savings"] is None


def test_plan_picks_cheapest_site_and_window_before_floor(settings):
    d = _dash(settings)
    f = d["forecast"]
    assert f["days_to_floor"] == 2.0                                   # 30 % → 10 % at 10 %/day
    plan = f["plan"]
    assert plan["site"] == "Hillcrest, Germany" and plan["range"] == "20–24 Uhr"
    assert plan["date"] == "2026-10-24"                                # last evening before the floor
    assert "Hillcrest laden" in plan["text"] and "Germany" not in plan["text"]
    assert plan["saving"] > 0
    states = build_states(d, "de")
    assert states["sensor.ladecockpit_next_charge"][1]["plan"] == plan["text"]


def test_no_plan_when_prices_are_flat(settings):
    sessions = [dict(s, price=0.37, charge_cost=s["kwh"] * 0.37, total=s["kwh"] * 0.37) for s in _sessions()]
    live = {"values": {"soc": 30.0}, "units": {}}
    d = build_dashboard(sessions=sessions, live=live, readings=_readings(), settings=settings, meta={}, now=NOW)
    assert d["forecast"]["plan"] is None


def test_report_text(settings):
    d = _dash(dataclasses.replace(settings, fuel_consumption=8.0, fuel_price=2.0))
    r = build_report(d, "2026-10", "de")
    assert r["label"] == "Oktober 2026" and r["sessions"] == 4
    assert r["text"].startswith("4 Ladungen, 180 kWh") and "gespart" in r["text"]
    assert build_report(d, "2026-08", "de") is None


class EventHA:
    def __init__(self, ok=True):
        self.ok, self.events, self.calls = ok, [], []

    async def fire_event(self, event, data):
        self.events.append((event, data))
        return self.ok

    async def call_service(self, domain, service, data):
        self.calls.append((domain, service, data))
        return True


def test_reporter_once_per_month(settings, db):
    data = _dash(settings)
    data["setup"] = {"ha_ok": True}

    async def build():
        return data

    ha = EventHA()
    rep = MonthReporter(dataclasses.replace(settings, lang="de"), db, ha, build)
    nov = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)

    async def go():
        assert await rep.check(NOW) is None and ha.events == []        # fresh install: only remembers
        assert await rep.check(NOW + timedelta(days=3)) is None         # same month
        report = await rep.check(nov)
        assert report["month"] == "2026-10"
        assert await rep.check(nov + timedelta(hours=1)) is None        # only once
        return report

    report = asyncio.run(go())
    assert [e for e, _ in ha.events] == [EVENT]
    assert ha.calls[0][1] == "create" and ha.calls[0][2]["title"] == "Ladecockpit · Oktober 2026"
    assert report["text"] == ha.calls[0][2]["message"]


def test_reporter_retries_when_ha_is_away(settings, db):
    data = _dash(settings)

    async def build():
        return data

    ha = EventHA(ok=False)
    rep = MonthReporter(dataclasses.replace(settings, month_report=False), db, ha, build)
    db.kv_set("report_month", "2026-10")
    nov = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
    assert asyncio.run(rep.check(nov)) is None and db.kv_get("report_month") == "2026-10"
    ha.ok = True
    assert asyncio.run(rep.check(nov))["month"] == "2026-10"
    assert ha.calls == []                                               # notification switched off

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.analytics import build_dashboard
from app.vehicle import battery_health, consumption_by_temperature, kwh_per_percent
from app.watcher import Watcher

TZ = ZoneInfo("Europe/Berlin")
T0 = datetime(2026, 8, 1, 6, tzinfo=timezone.utc)


def test_battery_health_trend():
    soc, rng = [], []
    for day in range(60):
        ts = T0 + timedelta(days=day)
        soc.append((ts, 80.0))
        rng.append((ts + timedelta(minutes=2), 80.0 * (5.75 - 0.001 * day)))   # slowly falling
        soc.append((ts + timedelta(hours=5), 30.0))                              # below 50 %: ignored
        rng.append((ts + timedelta(hours=5), 30.0 * 6.5))
    h = battery_health(soc, rng, TZ)
    assert h["samples"] == 60 and h["since"] == "2026-08-01"
    assert h["baseline"] == 574 and h["range_at_100"] == 570
    assert h["change_pct"] == -0.8
    assert len(h["weeks"]) >= 8
    assert battery_health(soc[:4], rng[:4], TZ) is None                         # too few readings


def test_health_waits_30_days_for_a_trend():
    soc = [(T0 + timedelta(days=d), 70.0) for d in range(10)]
    rng = [(T0 + timedelta(days=d, minutes=1), 400.0) for d in range(10)]
    h = battery_health(soc, rng, TZ)
    assert h["range_at_100"] == 571 and h["change_pct"] is None


def _day_series(days, temp_of, pct_per_km):
    soc, odo, temp = [], [], []
    level, km = 80.0, 1000.0
    for d in range(days):
        start = T0 + timedelta(days=d, hours=5)
        t = temp_of(d)
        soc.append((start, level)); odo.append((start, km)); temp.append((start, t))
        km += 50
        level -= 50 * pct_per_km(t)
        soc.append((start + timedelta(hours=3), level)); odo.append((start + timedelta(hours=3), km))
        temp.append((start + timedelta(hours=3), t))
        level = 80.0                                                            # charged overnight
    return soc, odo, temp


def test_consumption_by_temperature():
    soc, odo, temp = _day_series(20, lambda d: 5.0 if d % 2 else 15.0,
                                 lambda t: 0.24 if t < 10 else 0.20)
    c = consumption_by_temperature(soc, odo, temp, TZ, kwh_pct=0.8)
    bands = {(b["from"], b["to"]): b for b in c["bands"]}
    assert bands[(0.0, 10.0)]["pct_per_100"] == 24.0 and bands[(0.0, 10.0)]["kwh_per_100"] == 19.2
    assert bands[(10.0, 20.0)]["pct_per_100"] == 20.0 and bands[(10.0, 20.0)]["days"] == 10
    assert consumption_by_temperature(soc, odo, [], TZ, None) is None


def test_kwh_per_percent_from_sessions():
    soc = [(T0, 20.0), (T0 + timedelta(minutes=40), 70.0), (T0 + timedelta(days=2), 30.0),
           (T0 + timedelta(days=2, minutes=35), 80.0)]
    sessions = [
        {"kwh": 40.0, "start_ts": (T0 + timedelta(minutes=5)).isoformat(), "stop_ts": (T0 + timedelta(minutes=35)).isoformat()},
        {"kwh": 41.0, "start_ts": (T0 + timedelta(days=2, minutes=3)).isoformat(),
         "stop_ts": (T0 + timedelta(days=2, minutes=30)).isoformat()},
    ]
    assert kwh_per_percent(sessions, soc) == 0.81
    assert kwh_per_percent(sessions[:1], soc) is None                           # needs two sessions


class MeterHA:
    def __init__(self):
        self.meter, self.price = 1000.0, 0.30

    def entities(self):
        return {"home_energy": "sensor.wallbox_energy", "home_price": "sensor.price"}

    async def live(self):
        return {"values": {"home_energy": self.meter, "home_price": self.price},
                "units": {"home_energy": "kWh"}, "raw": {}}


def test_home_meter_steps_with_price_of_the_moment(settings, db):
    ha = MeterHA()
    w = Watcher(settings, db, ha, sync=None)
    now = T0

    async def poll(meter, price=None):
        nonlocal now
        now += timedelta(minutes=1)
        ha.meter = meter
        if price is not None:
            ha.price = price
        await w.poll_once(now)

    async def go():
        await poll(1000.0)                  # first value: only remembered
        await poll(1011.0)                  # +11 kWh at 0.30
        await poll(1011.02)                 # too small: added up later
        await poll(1022.0, price=0.10)      # +10.98 kWh at 0.10 (cheap hour)
        await poll(5.0)                     # meter replaced: start again
        await poll(9.0)                     # +4 kWh

    asyncio.run(go())
    kwh = db.readings_since("home_kwh", T0)
    cost = db.readings_since("home_cost", T0)
    assert [round(v, 2) for _, v in kwh] == [11.0, 11.0, 4.0]   # the 0.02 step went into the next one
    assert [round(v, 3) for _, v in cost] == [3.3, 1.1, 0.4]


def test_home_charging_in_month_and_per_100(settings):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    odo = [(datetime(2026, 10, 1, 8, tzinfo=timezone.utc), 1000.0), (datetime(2026, 10, 20, 8, tzinfo=timezone.utc), 2000.0)]
    home = [(datetime(2026, 10, 5, 20, tzinfo=timezone.utc), 50.0, 15.0),
            (datetime(2026, 10, 12, 20, tzinfo=timezone.utc), 50.0, 15.0)]
    session = {"session_id": "a", "site": "S", "start_ts": "2026-10-10T17:00:00+00:00", "stop_ts": "2026-10-10T17:30:00+00:00",
               "kwh": 40.0, "charge_cost": 20.0, "idle_fee": 0.0, "total": 20.0, "currency": "EUR", "price": 0.5,
               "invoices": [], "push_state": "pushed"}
    d = build_dashboard(sessions=[session], live={"values": {}, "units": {}},
                        readings={"odometer": odo, "home": home}, settings=settings, meta={}, now=now)
    m = d["month"]
    assert m["home"] == {"kwh": 100.0, "cost": 30.0, "avg_price": 0.3}
    assert m["cost"] == 20.0 and m["total_cost"] == 50.0
    assert m["per_100"] == 5.0 and m["kwh_per_100"] == 14.0                    # (20 + 30) € and (40 + 100) kWh / 1000 km
    assert d["monthly"][-1]["home_cost"] == 30.0

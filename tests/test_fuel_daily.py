import asyncio
import dataclasses
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.analytics import build_dashboard
from app.vehicle import daily_fuel_prices, distance_fuel_price
from app.watcher import Watcher
from tests.test_v04 import _s

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def at(day, hour):
    return datetime(2026, 10, day, hour, tzinfo=TZ).astimezone(timezone.utc)


def test_daily_average_is_weighted_by_how_long_a_price_was_shown():
    # 19. Okt.: 2,00 von Mitternacht bis 18 Uhr, dann 1,80 → (18 × 2,00 + 6 × 1,80) / 24
    points = [(at(19, 0), 2.00), (at(19, 18), 1.80), (at(20, 6), 1.90)]
    daily = daily_fuel_prices(points, TZ, NOW)
    assert daily[date(2026, 10, 19)] == round((18 * 2.00 + 6 * 1.80) / 24, 4)
    # 20. Okt. zählt bis jetzt (14 Uhr Ortszeit): 6 h zu 1,80, 8 h zu 1,90
    assert daily[date(2026, 10, 20)] == round((6 * 1.80 + 8 * 1.90) / 14, 4)


def test_old_or_wrong_prices_do_not_count():
    daily = daily_fuel_prices([(at(10, 12), 1.90), (at(12, 0), 0.0), (at(19, 0), 19.0)], TZ, NOW)
    assert set(daily) == {date(2026, 10, 10), date(2026, 10, 11)}     # held for 36 h at most


def test_every_day_counts_with_its_own_kilometres():
    daily = {date(2026, 10, 18): 2.00, date(2026, 10, 19): 1.80}
    odo = [(at(18, 8), 1000.0), (at(18, 20), 1100.0), (at(19, 8), 1100.0), (at(19, 20), 1400.0)]
    assert distance_fuel_price(odo, daily, TZ) == {"price": round((100 * 2.00 + 300 * 1.80) / 400, 3), "days": 2}
    # ein Tag ohne Preis nimmt den nächsten; weit weg von jedem Preis wird nichts gezählt
    odo2 = [(at(1, 8), 900.0), (at(1, 20), 950.0), (at(20, 8), 950.0), (at(20, 20), 1000.0)]
    assert distance_fuel_price(odo2, daily, TZ) == {"price": 1.80, "days": 0}
    assert distance_fuel_price(odo, {}, TZ) is None


def test_dashboard_uses_the_daily_average_when_switched_on(settings):
    odo = [(NOW - timedelta(days=59 - i), 1000.0 + 50 * i) for i in range(60)]
    prices = [(NOW - timedelta(days=19 - i, hours=1), 1.80 + 0.01 * (i % 3)) for i in range(20)]
    readings = {"soc": [], "soc_last": None, "range_last": None, "odometer": odo, "fuel_price": prices,
                "fuel_cost": [], "fuel_litres": []}
    values = {"fuel_consumption": 8.0, "fuel_price": 1.95, "fuel_cost_total": 945.19, "fuel_litres_total": 441.92}
    live = {"values": values, "units": {"odometer": "km"}}
    sessions = [_s("1", NOW - timedelta(days=3), 40.0, 0.40), _s("2", NOW - timedelta(days=9), 50.0, 0.40),
                _s("3", NOW - timedelta(days=55), 50.0, 0.40)]

    def dash(**kw):
        s = dataclasses.replace(settings, lang="de", ent_fuel_price="sensor.e10", **kw)
        return build_dashboard(sessions=sessions, live=live, readings=readings, settings=s, meta={}, now=NOW)

    paid = dash()
    assert paid["compare"]["fuel"]["source"] == "paid" and "fuel_price" not in paid["month"]
    d = dash(fuel_price_daily=True)
    fuel, m = d["compare"]["fuel"], d["month"]
    assert fuel["source"] == "daily" and 1.80 <= fuel["price"] <= 1.82 and fuel["daily_days"] >= 18
    assert m["fuel_price"] == fuel["price"]
    assert m["fuel_equivalent"] == round(8.0 * m["fuel_price"] * m["distance"] / 100, 2)
    assert any(i["kind"] == "fuel" and "Tagesdurchschnitt" in i["text"] for i in d["insights"])
    # ein Monat ohne Preis-Messwerte behält den bezahlten Preis
    old = next(x for x in d["monthly"] if x["key"] == "2026-08")
    assert "fuel_price" not in old
    assert old["fuel_equivalent"] == round(8.0 * 2.139 * old["distance"] / 100, 2)
    # ohne Preis-Messwerte bleibt es beim bezahlten Preis
    readings["fuel_price"] = []
    assert dash(fuel_price_daily=True)["compare"]["fuel"]["source"] == "paid"


class PriceHA:
    def __init__(self, prices, history=()):
        self.prices = list(prices)
        self._history = list(history)

    def entities(self):
        return {"fuel_price": "sensor.e10"}

    async def history(self, entity, start):
        return self._history if entity == "sensor.e10" else []

    async def live(self):
        return {"available": True, "values": {"fuel_price": self.prices.pop(0)}, "raw": {}, "units": {}}


def test_watcher_keeps_every_price_change_and_takes_the_history_once(settings, db):
    history = [(NOW - timedelta(days=2), 1.899), (NOW - timedelta(days=1), 1.879)]
    watcher = Watcher(dataclasses.replace(settings), db, PriceHA([1.869, 1.869, 1.859], history), None)

    async def go():
        await watcher.seed_from_history(now=NOW)
        for i in range(3):
            await watcher.poll_once(now=NOW + timedelta(minutes=5 * i))

    asyncio.run(go())
    assert [v for _, v in db.readings_since("fuel_price", NOW - timedelta(days=3))] == [1.899, 1.879, 1.869, 1.859]

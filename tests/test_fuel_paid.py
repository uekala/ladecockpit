import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone

from app.vehicle import paid_fuel_price
from app.watcher import Watcher

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


def days_ago(n):
    return NOW - timedelta(days=n)


def test_average_of_the_last_90_days():
    # 120 days ago: 500 € for 280 L; now 945 € for 442 L → 445 € for 162 L in the window
    cost = [(days_ago(120), 500.0), (days_ago(30), 700.0)]
    litres = [(days_ago(120), 280.0), (days_ago(30), 380.0)]
    paid = paid_fuel_price(cost, litres, 945.0, 442.0, NOW)
    assert paid == {"price": round(445 / 162, 3), "litres": 162.0, "days": 90}


def test_all_time_until_there_are_90_days_of_readings():
    cost = [(days_ago(5), 945.19)]
    litres = [(days_ago(5), 441.92)]
    paid = paid_fuel_price(cost, litres, 945.19, 441.92, NOW)
    assert paid == {"price": 2.139, "litres": 441.9, "days": None}


def test_all_time_when_too_little_was_filled_in_the_window_or_totals_were_reset():
    cost = [(days_ago(100), 900.0)]
    litres = [(days_ago(100), 430.0)]
    assert paid_fuel_price(cost, litres, 925.0, 441.0, NOW)["days"] is None      # only 11 L in 90 days
    assert paid_fuel_price(cost, litres, 120.0, 55.0, NOW)["price"] == round(120 / 55, 3)  # reset


def test_nothing_usable():
    assert paid_fuel_price([], [], None, 441.0, NOW) is None
    assert paid_fuel_price([], [], 30.0, 12.0, NOW) is None          # fewer than 20 L so far
    assert paid_fuel_price([], [], 945.0, 4419.2, NOW) is None       # 0.21 €/L: wrong entity or unit
    assert paid_fuel_price([], [], 0.0, 0.0, NOW) is None


class FuelHA:
    def __init__(self, totals):
        self.totals = list(totals)

    async def live(self):
        cost, litres = self.totals.pop(0)
        return {"available": True, "values": {"fuel_cost_total": cost, "fuel_litres_total": litres},
                "raw": {}, "units": {}}


def test_watcher_keeps_the_totals_once_a_day_or_when_they_change(settings, db):
    totals = [(900.0, 420.0)] * 3 + [(985.0, 459.0)] + [(985.0, 459.0)]
    times = [NOW, NOW + timedelta(hours=2), NOW + timedelta(hours=25), NOW + timedelta(hours=26),
             NOW + timedelta(hours=27)]
    watcher = Watcher(dataclasses.replace(settings), db, FuelHA(totals), None)

    async def go():
        for t in times:
            await watcher.poll_once(now=t)

    asyncio.run(go())
    assert [v for _, v in db.readings_since("fuel_cost", NOW - timedelta(days=1))] == [900.0, 900.0, 985.0]
    assert [v for _, v in db.readings_since("fuel_litres", NOW - timedelta(days=1))] == [420.0, 420.0, 459.0]

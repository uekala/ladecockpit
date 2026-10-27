"""Demo data: made-up but realistic sessions, so the app runs without any credentials."""
from __future__ import annotations

import dataclasses
import math
from datetime import datetime, timedelta, timezone

from . import carimage
from .analytics import build_dashboard
from .config import Settings

# Price per time window and per-site surcharge (demo assumptions, not real Tesla prices)
_SLOT_PRICE = [(0, 6, 0.34), (6, 11, 0.45), (11, 16, 0.49), (16, 20, 0.53), (20, 24, 0.37)]
_SITE_ADJ = {"Weiterstadt": 0.0, "Mainz": -0.02, "Frankfurt Flughafen": 0.03, "Wiesbaden": -0.01,
             "Bad Homburg": 0.02, "IONITY Weiskirchen": 0.10, "EnBW Ladepark Darmstadt": 0.12}
# Sites that stand for a third-party charger paid with Tesla MultiPass (operator in the name,
# as in Tesla's history)
_MULTIPASS = {"IONITY Weiskirchen", "EnBW Ladepark Darmstadt"}

# (days ago, hour, minute, site, kWh, duration in min, idle fee)
_PLAN = [
    (26, 19, 40, "Weiterstadt", 41.8, 31, 0.0),
    (24, 19, 5, "Mainz", 33.0, 52, 0.0),        # after a long drive, battery not preconditioned: slow
    (21, 12, 5, "Frankfurt Flughafen", 38.2, 28, 0.0),
    (19, 10, 30, "EnBW Ladepark Darmstadt", 27.3, 25, 0.0),
    (16, 21, 15, "Mainz", 44.6, 33, 0.0),
    (13, 17, 30, "Weiterstadt", 22.4, 17, 2.40),
    (11, 14, 20, "Bad Homburg", 29.7, 22, 0.0),
    (9, 7, 50, "Wiesbaden", 35.9, 27, 0.0),
    (6, 22, 10, "Mainz", 46.1, 34, 0.0),
    (4, 13, 5, "IONITY Weiskirchen", 31.5, 26, 0.0),
    (2, 18, 18, "Weiterstadt", 18.0, 14, 0.0),
]
PACK_KWH = 75.0
LONG_TRIPS = {24: 190.0}  # days ago: km driven in the hours before that day's session
HOME_PRICE = 0.31
KM_PER_DAY = 62.0


def _price(hour: int, site: str) -> float:
    base = next(p for a, b, p in _SLOT_PRICE if a <= hour < b)
    return round(base + _SITE_ADJ.get(site, 0.0), 2)


def demo_sessions(settings: Settings, now: datetime) -> list[dict]:
    today = now.astimezone(settings.tz).replace(second=0, microsecond=0)
    push_since = now - timedelta(days=5)
    out = []
    for i, (days, hh, mm, site, kwh, dur, idle) in enumerate(_PLAN):
        start = (today - timedelta(days=days)).replace(hour=hh, minute=mm)
        stop = start + timedelta(minutes=dur)
        price = _price(hh, site)
        listed = round(kwh * price, 2)
        credit = 10.0 if i == 0 else 0.0              # the first session was partly paid with a Tesla credit
        charge = round(listed - credit, 2)
        start_utc = start.astimezone(timezone.utc)
        out.append({
            "session_id": f"demo-{1000 + i}",
            "vin": "DEMO",
            "site": site,
            "country": "DE",
            "start_ts": start_utc.isoformat(timespec="seconds"),
            "stop_ts": stop.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "unlatch_ts": (stop + timedelta(minutes=12 if idle else 3)).astimezone(timezone.utc).isoformat(timespec="seconds"),
            "kwh": kwh,
            "charge_cost": charge,
            "idle_fee": idle,
            "other_fee": 0.0,
            "total": round(charge + idle, 2),
            "currency": "EUR",
            "price": round(charge / kwh, 4),
            "list_cost": listed,
            "list_price": price,
            "credit": credit,
            "net_total": round((charge + idle) / 1.19, 2),
            "invoices": [{"id": f"demo-inv-{i}", "name": f"invoice-{i}.pdf", "type": "IMMEDIATE"}],
            "push_state": "pushed" if start_utc >= push_since else "backfill",
            "network": "multipass" if site in _MULTIPASS else "supercharger",
        })
    out.sort(key=lambda s: s["start_ts"], reverse=True)
    return out


def _demo_temp(t: datetime, now: datetime) -> float:
    """Autumn: from about 16 °C five weeks ago down to about 3 °C, warmer in the afternoon."""
    days_ago = (now - t).total_seconds() / 86400
    daily = 3.0 + 13.0 * min(days_ago, 35) / 35 + 2.5 * math.sin(days_ago * 1.7)
    return round(daily + 3.0 * math.sin((t.hour - 9) / 24 * 2 * math.pi), 1)


def demo_readings(settings: Settings, sessions: list[dict], now: datetime) -> dict:
    """Simulates 35 days of battery, range, odometer and outside temperature: drives morning and
    evening (more energy when it is cold), Supercharges up to 70 % and charges at home on Saturdays."""
    tz = settings.tz
    start = (now - timedelta(days=35)).astimezone(tz).replace(hour=6, minute=0, second=0, microsecond=0)
    charges = sorted((datetime.fromisoformat(s["start_ts"]), s["kwh"]) for s in sessions)
    trip_days = {(now.astimezone(tz) - timedelta(days=d)).date(): km for d, km in LONG_TRIPS.items()}
    trips = [(w, trip_days[w.astimezone(tz).date()]) for w, _ in charges if w.astimezone(tz).date() in trip_days]
    soc, odo = 55.0, 4180.0
    soc_pts, odo_pts, range_pts, temp_pts, home = [], [], [], [], []
    t = start
    end = now - timedelta(hours=15)  # afterwards the car is offline (parked without reception)
    while t < end:
        t += timedelta(hours=1)
        temp = _demo_temp(t, now)
        utc = t.astimezone(timezone.utc)
        if t.hour % 3 == 0:
            temp_pts.append((utc, temp))
        drove = 0.0
        if t.hour == 8:
            drove = KM_PER_DAY * (0.55 if t.weekday() < 5 else 0.3)
        elif t.hour == 18:
            drove = KM_PER_DAY * (0.45 if t.weekday() < 5 else 0.6)
        drove += sum(km for w, km in trips if w - timedelta(hours=2) < t <= w - timedelta(hours=1))
        per_km = 0.150 * (1 + max(0.0, 15.0 - temp) * 0.015)
        soc -= drove * per_km / PACK_KWH * 100 + 0.03
        odo += drove
        charged = False
        for when, kwh in charges:
            if t - timedelta(hours=1) < when <= t:
                soc = min(70.0, soc + kwh * 0.92 / PACK_KWH * 100)
                charged = True
        if t.weekday() == 5 and t.hour == 10:      # at home: 11 kW for two hours
            home.append((utc, 22.0, round(22.0 * HOME_PRICE, 2)))
            soc = min(80.0, soc + 22.0 * 0.9 / PACK_KWH * 100)
            charged = True
        soc = max(soc, 4.0)
        about_to_charge = any(t < w <= t + timedelta(hours=1) for w, _ in charges)
        if drove or charged or about_to_charge:
            soc_pts.append((utc, round(soc)))
            odo_pts.append((utc, round(odo, 1)))
            age = (now - t).days
            range_pts.append((utc, round(soc * (5.74 - 0.0012 * (35 - age)))))
    since_14 = now - timedelta(days=14)
    return {
        "soc": [p for p in soc_pts if p[0] >= since_14],
        "soc_last": soc_pts[-1],
        "range_last": range_pts[-1],
        "odometer": odo_pts,
        "soc_long": soc_pts,
        "range_long": range_pts,
        "temp": temp_pts,
        "home": home,
    }


def build_demo(settings: Settings) -> dict:
    now = datetime.now(timezone.utc)
    sessions = demo_sessions(settings, now)
    readings = demo_readings(settings, sessions, now)
    inv_total = sum(s["total"] for s in sessions)
    inv_kwh = sum(s["kwh"] for s in sessions)
    demo_settings = dataclasses.replace(settings, ent_cost_total="demo", ent_kwh_total="demo")
    # Right now the car charges at a Supercharger: it arrived with about 30 % less than the last
    # reading (driven since), plugged in 12 minutes ago and gains about 2 % a minute.
    plugged = max(12, readings["soc_last"][1] - 30)
    rising = [(now - timedelta(minutes=12 - m), round(plugged + m * 1.9)) for m in range(0, 12, 2)]
    soc_now = round(plugged + 12 * 1.9)
    readings["soc"] = readings["soc"] + rising
    readings["soc_long"] = readings["soc_long"] + rising
    live = {
        "available": True,
        "raw": {"charging": "charging",
                "time_to_full": (now + timedelta(minutes=max(4, settings.soc_target - plugged - 23) / 1.6)).isoformat(timespec="seconds")},
        "values": {
            "soc": soc_now,
            "range": round(soc_now * 5.7),
            "charge_power": 104.0,
            "cost_total": round(inv_total * 1.07, 2),     # e.g. estimated prices booked by hand
            "kwh_total": round(inv_kwh * 0.93, 2),        # car-reported kWh < billed kWh
            "reference_price": 0.49,
            "fuel_month": 41.30,
            "fuel_consumption": 7.2,                       # comparison car, L/100 km
            "fuel_price": 1.79,                            # per litre
        },
        "units": {"odometer": "km", "range": "km", "charge_power": "kW"},
    }
    meta = {
        "mode": "demo",
        "setup": {
            "tesla_configured": True, "tesla_connected": True, "tesla_auth_error": None,
            "ha_configured": True, "ha_ok": True, "ha_error": None,
            "redirect_uri": settings.tesla_redirect_uri,
            "push_since": (now - timedelta(days=5)).isoformat(timespec="seconds"),
            "entities": ["soc", "range", "odometer", "charging"],
            "addon": False,
        },
        "sync": {
            "last": (now - timedelta(hours=2)).isoformat(timespec="seconds"),
            "next": (now + timedelta(hours=4)).isoformat(timespec="seconds"),
            "error": None, "burst": False,
        },
        "api_calls": {"data": 38},
    }
    d = build_dashboard(sessions=sessions, live=live, readings=readings,
                        settings=demo_settings, meta=meta, now=now)
    d["car"] = carimage.describe(carimage.normalize(None), settings.lang, auto=True)
    return d

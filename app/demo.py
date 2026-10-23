"""Demo data: made-up but realistic sessions, so the app runs without any credentials."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

from .analytics import build_dashboard
from .config import Settings

# Price per time window and per-site surcharge (demo assumptions, not real Tesla prices)
_SLOT_PRICE = [(0, 6, 0.34), (6, 11, 0.45), (11, 16, 0.49), (16, 20, 0.53), (20, 24, 0.37)]
_SITE_ADJ = {"Northgate": 0.0, "Riverside": -0.02, "Airport West": 0.03, "Old Town": -0.01, "Hillcrest": 0.02}

# (days ago, hour, minute, site, kWh, duration in min, idle fee)
_PLAN = [
    (26, 19, 40, "Northgate", 41.8, 31, 0.0),
    (21, 12, 5, "Airport West", 38.2, 28, 0.0),
    (16, 21, 15, "Riverside", 44.6, 33, 0.0),
    (13, 17, 30, "Northgate", 22.4, 17, 2.40),
    (11, 14, 20, "Hillcrest", 29.7, 22, 0.0),
    (9, 7, 50, "Old Town", 35.9, 27, 0.0),
    (6, 22, 10, "Riverside", 46.1, 34, 0.0),
    (2, 18, 18, "Northgate", 18.0, 14, 0.0),
]
PACK_KWH = 75.0
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
        charge = round(kwh * price, 2)
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
            "price": price,
            "invoices": [{"id": f"demo-inv-{i}", "name": f"invoice-{i}.pdf", "type": "IMMEDIATE"}],
            "push_state": "pushed" if start_utc >= push_since else "backfill",
        })
    out.sort(key=lambda s: s["start_ts"], reverse=True)
    return out


def demo_readings(settings: Settings, sessions: list[dict], now: datetime) -> dict:
    """Simulates 35 days of battery and odometer: drives morning/evening, charges up to 70 %."""
    tz = settings.tz
    start = (now - timedelta(days=35)).astimezone(tz).replace(hour=6, minute=0, second=0, microsecond=0)
    charges = sorted((datetime.fromisoformat(s["start_ts"]), s["kwh"]) for s in sessions)
    soc, odo = 55.0, 4180.0
    soc_pts, odo_pts = [], []
    t = start
    end = now - timedelta(hours=15)  # afterwards the car is offline (parked without reception)
    while t < end:
        t += timedelta(hours=1)
        drove = 0.0
        if t.hour == 8:
            drove = KM_PER_DAY * (0.55 if t.weekday() < 5 else 0.3)
        elif t.hour == 18:
            drove = KM_PER_DAY * (0.45 if t.weekday() < 5 else 0.6)
        soc -= drove * 0.155 / PACK_KWH * 100 + 0.03
        odo += drove
        for when, kwh in charges:
            if t - timedelta(hours=1) < when <= t:
                soc = min(70.0, soc + kwh * 0.92 / PACK_KWH * 100)
        soc = max(soc, 4.0)
        if drove or any(t - timedelta(hours=1) < w <= t for w, _ in charges):
            utc = t.astimezone(timezone.utc)
            soc_pts.append((utc, round(soc)))
            odo_pts.append((utc, round(odo, 1)))
    since_14 = now - timedelta(days=14)
    return {
        "soc": [p for p in soc_pts if p[0] >= since_14],
        "soc_last": soc_pts[-1],
        "range_last": (soc_pts[-1][0], round(soc_pts[-1][1] * 6.2)),
        "odometer": odo_pts,
    }


def build_demo(settings: Settings) -> dict:
    now = datetime.now(timezone.utc)
    sessions = demo_sessions(settings, now)
    readings = demo_readings(settings, sessions, now)
    inv_total = sum(s["total"] for s in sessions)
    inv_kwh = sum(s["kwh"] for s in sessions)
    demo_settings = dataclasses.replace(settings, ent_cost_total="demo", ent_kwh_total="demo")
    live = {
        "available": True,
        "values": {
            "soc": None,                                   # car offline right now
            "cost_total": round(inv_total * 1.07, 2),     # e.g. estimated prices booked by hand
            "kwh_total": round(inv_kwh * 0.93, 2),        # car-reported kWh < billed kWh
            "reference_price": 0.49,
            "fuel_month": 41.30,
        },
        "units": {"odometer": "km", "range": "km"},
    }
    meta = {
        "mode": "demo",
        "setup": {
            "tesla_configured": True, "tesla_connected": True, "tesla_auth_error": None,
            "ha_configured": True, "ha_ok": True, "ha_error": None,
            "redirect_uri": settings.tesla_redirect_uri,
            "push_since": (now - timedelta(days=5)).isoformat(timespec="seconds"),
            "entities": ["soc", "range", "odometer", "charging"],
        },
        "sync": {
            "last": (now - timedelta(hours=2)).isoformat(timespec="seconds"),
            "next": (now + timedelta(hours=4)).isoformat(timespec="seconds"),
            "error": None, "burst": False,
        },
        "api_calls": {"data": 38},
    }
    return build_dashboard(sessions=sessions, live=live, readings=readings,
                           settings=demo_settings, meta=meta, now=now)

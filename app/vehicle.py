"""Analyses of the car's own readings: battery health and consumption by outside temperature.

Both work from the readings Ladecockpit keeps anyway (battery level, range, odometer and,
if configured, the outside temperature), so they need no extra Tesla requests.
"""
from __future__ import annotations

from bisect import bisect_left
from datetime import datetime, timedelta
from statistics import median

PAIR_WINDOW = timedelta(minutes=15)   # battery level and range must be this close together
MIN_SOC_FOR_RANGE = 50                # the range estimate is most stable in the upper half
HEALTH_MIN_SAMPLES = 5
HEALTH_MIN_SPAN = timedelta(days=30)  # before that a change is mostly noise

TEMP_BANDS = [(-99.0, 0.0), (0.0, 10.0), (10.0, 20.0), (20.0, 99.0)]
DAY_MIN_DISTANCE = 15.0
BAND_MIN_DAYS = 3
BAND_MIN_DISTANCE = 100.0


def _nearest(points: list[tuple[datetime, float]], times: list[datetime], ts: datetime):
    i = bisect_left(times, ts)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(points):
            gap = abs(points[j][0] - ts)
            if gap <= PAIR_WINDOW and (best is None or gap < best[0]):
                best = (gap, points[j][1])
    return best[1] if best else None


def battery_health(soc: list[tuple[datetime, float]], rng: list[tuple[datetime, float]], tz) -> dict | None:
    """Range at 100 % (the car's own estimate, scaled from the current battery level) over time.
    A slowly falling value is the usual sign of battery ageing."""
    if not soc or not rng:
        return None
    soc_times = [p[0] for p in soc]
    samples = []
    for ts, value in rng:
        level = _nearest(soc, soc_times, ts)
        if level is not None and level >= MIN_SOC_FOR_RANGE and value > 0:
            samples.append((ts, value / level * 100))
    if len(samples) < HEALTH_MIN_SAMPLES:
        return None
    samples.sort()
    first, last = samples[0][0], samples[-1][0]
    head = [v for t, v in samples if t <= first + timedelta(days=14)]
    tail = [v for t, v in samples if t >= last - timedelta(days=14)]
    current, baseline = median(tail), median(head)
    weeks: dict[str, list[float]] = {}
    for ts, value in samples:
        local = ts.astimezone(tz)
        monday = (local - timedelta(days=local.weekday())).date().isoformat()
        weeks.setdefault(monday, []).append(value)
    out = {"range_at_100": round(current), "samples": len(samples),
           "since": first.astimezone(tz).date().isoformat(), "baseline": round(baseline), "change_pct": None,
           "weeks": [{"week": k, "value": round(median(v))} for k, v in sorted(weeks.items())]}
    if last - first >= HEALTH_MIN_SPAN and baseline:
        out["change_pct"] = round((current - baseline) / baseline * 100, 1)
    return out


def _band(temp: float) -> int:
    return next(i for i, (lo, hi) in enumerate(TEMP_BANDS) if lo <= temp < hi)


def kwh_per_percent(sessions: list[dict], soc: list[tuple[datetime, float]]) -> float | None:
    """Billed kWh per 1 % battery, from sessions with a battery reading right before and after.
    Includes charging losses, like the kWh per 100 km the app shows elsewhere."""
    if not soc:
        return None
    times = [p[0] for p in soc]
    ratios = []
    for s in sessions:
        if not (s.get("kwh") and s.get("start_ts") and s.get("stop_ts")):
            continue
        start, stop = datetime.fromisoformat(s["start_ts"]), datetime.fromisoformat(s["stop_ts"])
        i = bisect_left(times, start) - 1
        j = bisect_left(times, stop)
        if i < 0 or j >= len(soc):
            continue
        if start - soc[i][0] > timedelta(hours=2) or soc[j][0] - stop > timedelta(hours=3):
            continue
        gained = soc[j][1] - soc[i][1]
        if gained >= 10:
            ratios.append(s["kwh"] / gained)
    return round(median(ratios), 3) if len(ratios) >= 2 else None


def consumption_by_temperature(soc: list[tuple[datetime, float]], odo: list[tuple[datetime, float]],
                               temp: list[tuple[datetime, float]], tz, kwh_pct: float | None) -> dict | None:
    """Battery use per 100 km/mi per day, grouped by the day's mean outside temperature."""
    if len(temp) < 2 or len(soc) < 2 or len(odo) < 2:
        return None
    days: dict = {}

    def day(ts):
        return days.setdefault(ts.astimezone(tz).date(), {"drop": 0.0, "dist": 0.0, "temps": []})

    for (_, a), (t2, b) in zip(soc, soc[1:]):
        if 0 < a - b < 40:
            day(t2)["drop"] += a - b
    for (_, a), (t2, b) in zip(odo, odo[1:]):
        if 0 < b - a < 1500:
            day(t2)["dist"] += b - a
    for ts, value in temp:
        day(ts)["temps"].append(value)

    bands = [{"from": lo, "to": hi, "days": 0, "distance": 0.0, "drop": 0.0} for lo, hi in TEMP_BANDS]
    for d in days.values():
        if d["dist"] < DAY_MIN_DISTANCE or d["drop"] <= 0 or not d["temps"]:
            continue
        b = bands[_band(sum(d["temps"]) / len(d["temps"]))]
        b["days"] += 1
        b["distance"] += d["dist"]
        b["drop"] += d["drop"]
    out = []
    for b in bands:
        if b["days"] < BAND_MIN_DAYS or b["distance"] < BAND_MIN_DISTANCE:
            continue
        pct = b["drop"] / b["distance"] * 100
        out.append({"from": None if b["from"] < -50 else b["from"], "to": None if b["to"] > 50 else b["to"],
                    "days": b["days"], "distance": round(b["distance"]), "pct_per_100": round(pct, 1),
                    "kwh_per_100": round(pct * kwh_pct, 1) if kwh_pct else None})
    if not out:
        return None
    return {"bands": out, "kwh_per_percent": kwh_pct}

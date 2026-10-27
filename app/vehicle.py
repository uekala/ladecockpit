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


# --- charging speed ---------------------------------------------------------------------------
SLOW_MIN_KWH = 20.0                    # shorter sessions rarely reach full power, so they are not compared
SLOW_SHARE = 0.6                       # slow: below 60 % of the usual average at the same site
SLOW_MAX_START_SOC = 50                # from about here the car charges slower on purpose
SLOW_MIN_PEERS = 2                     # other comparable sessions at the site needed for a "usual" value
START_SOC_WINDOW = timedelta(hours=2)  # a battery reading this close before the start counts


def session_kw(x: dict) -> float | None:
    """Average charging power of a session (billed kWh over start to stop, at least 3 minutes)."""
    if not (x.get("kwh") and x.get("start_ts") and x.get("stop_ts")):
        return None
    hours = (datetime.fromisoformat(x["stop_ts"]) - datetime.fromisoformat(x["start_ts"])).total_seconds() / 3600
    return x["kwh"] / hours if hours >= 0.05 else None


def charging_speed(sessions: list[dict], soc: list[tuple[datetime, float]]) -> dict[str, dict]:
    """Average power of each session compared with what the car usually gets at the same site.

    The usual power is the median of the other sessions there with enough energy (at least two).
    A session is slow when it got less than 60 % of that. Short sessions and sessions that started
    with more than half a battery are never called slow: they charge slower on purpose.
    Typical reasons are a cold battery without preconditioning or a shared or throttled stall.
    Returns {session_id: {"kw", "typical_kw", "slow", "start_soc"}} for sessions with a duration."""
    times = [p[0] for p in soc]

    def start_soc(x: dict) -> float | None:
        start = datetime.fromisoformat(x["start_ts"])
        i = bisect_left(times, start) - 1
        if i < 0 or start - times[i] > START_SOC_WINDOW:
            return None
        return soc[i][1]

    out: dict[str, dict] = {}
    by_site: dict[str, list[tuple[str, float, bool]]] = {}
    for x in sessions:
        kw = session_kw(x)
        if kw is None:
            continue
        level = start_soc(x)
        out[x["session_id"]] = {"kw": round(kw), "typical_kw": None, "slow": False,
                                "start_soc": round(level) if level is not None else None}
        if x["kwh"] >= SLOW_MIN_KWH and x.get("site"):
            low_start = level is None or level < SLOW_MAX_START_SOC
            by_site.setdefault(x["site"], []).append((x["session_id"], kw, low_start))
    for rows in by_site.values():
        for sid, kw, low_start in rows:
            peers = [k for other, k, _ in rows if other != sid]
            if len(peers) < SLOW_MIN_PEERS:
                continue
            typical = median(peers)
            out[sid]["typical_kw"] = round(typical)
            out[sid]["slow"] = low_start and kw < SLOW_SHARE * typical
    return out


# --- fuel price actually paid --------------------------------------------------------------------
PAID_WINDOW = timedelta(days=90)
PAID_MIN_LITRES = 20.0           # less than this in the window: too few fill-ups for an average
PAID_PRICE_RANGE = (0.3, 5.0)    # per litre; anything else is a mix-up of entities or units


def paid_fuel_price(cost: list[tuple[datetime, float]], litres: list[tuple[datetime, float]],
                    cost_now: float | None, litres_now: float | None, now: datetime) -> dict | None:
    """Average price per litre you actually paid, from two totals that grow when you fill up.

    Over the last 90 days when at least 20 litres were bought then (from Ladecockpit's own readings
    of the totals), else over everything the totals hold – right after the setup, or when the totals
    were reset. Returns {"price", "litres", "days"} (days None: all the totals hold) or None."""
    if cost_now is None or litres_now is None:
        return None
    start = now - PAID_WINDOW

    def at_start(series: list[tuple[datetime, float]]) -> float | None:
        before = [v for t, v in series if t <= start]
        return before[-1] if before else None

    c0, l0 = at_start(cost), at_start(litres)
    if c0 is not None and l0 is not None and litres_now - l0 >= PAID_MIN_LITRES and cost_now > c0:
        price, used, days = (cost_now - c0) / (litres_now - l0), litres_now - l0, PAID_WINDOW.days
    elif litres_now >= PAID_MIN_LITRES and cost_now > 0:
        price, used, days = cost_now / litres_now, litres_now, None
    else:
        return None
    if not PAID_PRICE_RANGE[0] <= price <= PAID_PRICE_RANGE[1]:
        return None
    return {"price": round(price, 3), "litres": round(used, 1), "days": days}


# --- While the car charges ------------------------------------------------------------------------
RATE_WINDOW = timedelta(minutes=90)   # battery readings this recent give the charging rate
RATE_MIN_SPAN = timedelta(minutes=8)
RATE_MIN_GAIN = 1.0                    # % – less is rounding noise
FINISH_MAX = timedelta(hours=48)       # anything later is a stale or wrong value


def _until(raw: str | None, value: float | None, unit: str | None, now: datetime) -> datetime | None:
    """Time-to-full as Home Assistant reports it: a timestamp (Tesla Fleet, Teslemetry) or a
    duration with its unit (h, min, s); a bare number counts as hours."""
    if raw and ("T" in raw or ":" in raw) and value is None:
        try:
            at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if at.tzinfo is None:
            return None
        return at if now < at <= now + FINISH_MAX else None
    if value is None or value <= 0:
        return None
    u = (unit or "h").strip().lower()
    factor = {"s": 1 / 3600, "sec": 1 / 3600, "min": 1 / 60, "m": 1 / 60, "d": 24.0}.get(u, 1.0)
    span = timedelta(hours=value * factor)
    return now + span if span <= FINISH_MAX else None


def soc_rate(soc: list[tuple[datetime, float]], soc_now: float | None, now: datetime) -> float | None:
    """Percent per hour the battery gained recently, from the rising run of readings up to now."""
    pts = [p for p in soc if now - RATE_WINDOW <= p[0] <= now]
    if soc_now is not None and (not pts or pts[-1][0] < now):
        pts.append((now, soc_now))
    if len(pts) < 2:
        return None
    start = len(pts) - 1
    while start > 0 and pts[start - 1][1] <= pts[start][1]:
        start -= 1
    (t0, v0), (t1, v1) = pts[start], pts[-1]
    if t1 - t0 < RATE_MIN_SPAN or v1 - v0 < RATE_MIN_GAIN:
        return None
    return round((v1 - v0) / ((t1 - t0).total_seconds() / 3600), 1)


def live_charge(*, raw: dict, values: dict, units: dict, charging_value: str, soc: float | None,
                target: int, soc_readings: list[tuple[datetime, float]], kwh_pct: float | None,
                now: datetime) -> dict:
    """What the car does right now: {"charging", "power", "rate", "finish"}.

    charging is None when the state is unknown (no entity, car asleep or offline). The finish time
    comes from the time-to-full entity, else from the charger power and the kWh one percent takes,
    else from how fast the battery level rose in the last readings."""
    state = (raw.get("charging") or "").strip().lower()
    if not state or state in ("unknown", "unavailable", "none"):
        return {"charging": None}
    if state != charging_value.strip().lower():
        return {"charging": False}
    power = values.get("charge_power")
    if power is not None and (units.get("charge_power") or "kW").strip().lower() == "w":
        power /= 1000
    power = round(power, 1) if power and power > 0 else None
    rate = soc_rate(soc_readings, soc, now)
    finish = _until(raw.get("time_to_full"), values.get("time_to_full"), units.get("time_to_full"), now)
    if finish is None and soc is not None and soc < target:
        if power and kwh_pct:
            finish = now + timedelta(hours=(target - soc) * kwh_pct / power)
        elif rate:
            finish = now + timedelta(hours=(target - soc) / rate)
        if finish is not None and finish - now > FINISH_MAX:
            finish = None
    return {"charging": True, "power": power, "rate": rate,
            "finish": finish.isoformat(timespec="seconds") if finish else None}

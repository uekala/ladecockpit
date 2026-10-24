"""Turns invoices + readings + Home Assistant values into the dashboard JSON."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from . import i18n, networks, vehicle
from .config import Settings
from .networks import MULTIPASS, SUPERCHARGER

SLOT_HOURS = [("night", 0, 6), ("morning", 6, 11), ("midday", 11, 16), ("afternoon", 16, 20), ("evening", 20, 24)]
USD_PER_DATA_CALL = 0.002
MONTHLY_CREDIT_USD = 10.0


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _month_key(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def _stats(items: list[dict]) -> dict:
    """Totals of sessions. avg_price is what you paid per kWh; list_price is the Supercharger's
    own rate before credits – use it whenever prices are compared."""
    kwh = sum(i["kwh"] for i in items)
    charge = sum(i["charge_cost"] or 0.0 for i in items)
    total = sum(i["total"] for i in items)
    idle = sum(i["idle_fee"] or 0.0 for i in items)
    listed = sum(i["list_cost"] if i.get("list_cost") is not None else (i["charge_cost"] or 0.0) for i in items)
    credit = sum(i.get("credit") or 0.0 for i in items)
    return {
        "sessions": len(items),
        "kwh": round(kwh, 1),
        "cost": round(total, 2),
        "charge_cost": round(charge, 2),
        "idle": round(idle, 2),
        "credit": round(credit, 2),
        "avg_price": round(charge / kwh, 4) if kwh else None,
        "list_price": round(listed / kwh, 4) if kwh else None,
    }


def _hours(x: dict) -> float | None:
    """Charging duration in hours (start to stop), only for sessions of at least 3 minutes."""
    if not (x.get("start_ts") and x.get("stop_ts")):
        return None
    h = (datetime.fromisoformat(x["stop_ts"]) - datetime.fromisoformat(x["start_ts"])).total_seconds() / 3600
    return h if h >= 0.05 else None


def _avg_kw(items: list[dict]) -> float | None:
    timed = [(x["kwh"], _hours(x)) for x in items if x.get("kwh")]
    timed = [(k, h) for k, h in timed if h]
    hours = sum(h for _, h in timed)
    return round(sum(k for k, _ in timed) / hours) if hours else None


def _home_sum(home: list, start: datetime | None = None, end: datetime | None = None) -> dict:
    """Home charging in a window: kWh, cost (of the steps that had a price) and avg price."""
    steps = [h for h in home if (start is None or h[0] >= start) and (end is None or h[0] < end)]
    kwh = sum(h[1] for h in steps)
    priced = [h for h in steps if h[2] is not None]
    cost = sum(h[2] for h in priced)
    priced_kwh = sum(h[1] for h in priced)
    return {"kwh": round(kwh, 1), "cost": round(cost, 2) if priced else None,
            "avg_price": round(cost / priced_kwh, 4) if priced_kwh else None}


def _distance(odo: list[tuple[datetime, float]], items: list[dict], home: list | None = None) -> dict:
    """Distance from odometer readings and the cost/energy of all charging in the same window
    (invoices plus charging at home)."""
    out = {"distance": None, "distance_since": None, "per_100": None, "kwh_per_100": None}
    if len(odo) < 2:
        return out
    dist = odo[-1][1] - odo[0][1]
    since = odo[0][0]
    out["distance"] = round(dist)
    out["distance_since"] = since
    covered = [x for x in items if x["_local"] >= since]
    at_home = _home_sum(home or [], since, odo[-1][0] + timedelta(seconds=1))
    if dist >= 50 and (covered or at_home["kwh"]):
        cost = sum(x["total"] for x in covered) + (at_home["cost"] or 0.0)
        kwh = sum(x["kwh"] for x in covered) + at_home["kwh"]
        out["per_100"] = round(cost / dist * 100, 2)
        out["kwh_per_100"] = round(kwh / dist * 100, 1)
    return out


def _month_bounds(key: str, tz) -> tuple[datetime, datetime]:
    y, m = (int(v) for v in key.split("-"))
    start = datetime(y, m, 1, tzinfo=tz)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=tz)
    return start, end


def _per_day(points: list[tuple[datetime, float]], now: datetime) -> float | None:
    if len(points) < 2:
        return None
    span = (now - points[0][0]).total_seconds() / 86400
    if span < 1:
        return None
    return (points[-1][1] - points[0][1]) / span


def _forecast(lang, history, soc, floor, now_utc, tz, odometer_14d) -> dict:
    out = {"rate_pct_day": None, "days_to_floor": None, "calendar_days": None, "date_floor": None,
           "date_label": None, "basis_days": 0.0, "dist_day": None, "text": ""}
    dist = _per_day(odometer_14d, now_utc)
    if dist is not None:
        out["dist_day"] = round(dist, 1)
    if soc is None:
        out["text"] = i18n.t(lang, "fc_no_soc")
        return out
    if len(history) < 2:
        out["text"] = i18n.t(lang, "fc_too_little")
        return out

    span_days = (now_utc - history[0][0]).total_seconds() / 86400
    drops = sum(prev - cur for (_, prev), (_, cur) in zip(history, history[1:]) if 0 < prev - cur < 40)
    out["basis_days"] = round(span_days, 1)
    if span_days < 1:
        out["text"] = i18n.t(lang, "fc_too_little")
        return out
    rate = drops / span_days
    out["rate_pct_day"] = round(rate, 1)
    if rate < 0.2:
        out["text"] = i18n.t(lang, "fc_flat")
        return out

    days = max(0.0, (soc - floor) / rate)
    when = (now_utc + timedelta(days=days)).astimezone(tz)
    cal = (when.date() - now_utc.astimezone(tz).date()).days
    out["days_to_floor"] = round(days, 1)
    out["calendar_days"] = cal
    out["date_floor"] = when.date().isoformat()
    out["date_label"] = i18n.date_label(lang, when)
    if cal <= 0:
        out["text"] = i18n.t(lang, "fc_today", floor=floor)
    elif cal == 1:
        out["text"] = i18n.t(lang, "fc_tomorrow")
    else:
        out["text"] = i18n.t(lang, "fc_latest", date=out["date_label"], days=cal)
    return out


MIN_PRICE_GAP = 0.03       # €/kWh: smaller differences are not worth a tip
PROJECTION_DAYS = 90       # look-back for the yearly projection
PROJECTION_MIN_DAYS = 7
PROJECTION_MIN_DIST = 200


def _projection(odo: list[tuple[datetime, float]], priced: list[dict], now_utc: datetime,
                fuel: dict | None, home: list | None = None) -> dict | None:
    """Cost and distance per year, from the last PROJECTION_DAYS days."""
    window = [p for p in odo if p[0] >= now_utc - timedelta(days=PROJECTION_DAYS)]
    if len(window) < 2:
        return None
    days = (window[-1][0] - window[0][0]).total_seconds() / 86400
    dist = window[-1][1] - window[0][1]
    covered = [x for x in priced if x["_local"] >= window[0][0]]
    at_home = _home_sum(home or [], window[0][0])
    if days < PROJECTION_MIN_DAYS or dist < PROJECTION_MIN_DIST or not (covered or at_home["kwh"]):
        return None
    per_100 = (sum(x["total"] for x in covered) + (at_home["cost"] or 0.0)) / dist * 100
    per_year = dist / days * 365
    out = {"basis_days": round(days), "distance": int(round(per_year, -2)),
           "cost": int(round(per_100 * per_year / 100, -1)), "per_100": round(per_100, 2),
           "fuel_cost": None, "savings": None}
    if fuel:
        out["fuel_cost"] = int(round(fuel["per_100"] * per_year / 100, -1))
        out["savings"] = int(round((fuel["per_100"] - per_100) * per_year / 100, -1))
    return out


def _place(site: str) -> str:
    """"Willich, Germany" → "Willich" for running text."""
    return site.rsplit(", ", 1)[0] if site and site.count(", ") == 1 else site


def _plan(lang: str, forecast: dict, priced: list[dict], overall_price: float | None,
          now_utc: datetime, tz, money) -> dict | None:
    """When and where to charge before the battery reaches the floor: the cheapest
    combination of Supercharger and time window from your own invoices."""
    days = forecast.get("days_to_floor")
    if days is None or not overall_price or len(priced) < 4:
        return None
    pairs: dict[tuple[str, int], list[dict]] = {}
    for x in priced:
        slot = next(i for i, (_, a, b) in enumerate(SLOT_HOURS) if a <= x["_local"].hour < b)
        pairs.setdefault((x.get("site") or "", slot), []).append(x)
    stats = [(k, _stats(v)) for k, v in pairs.items() if k[0]]
    stats = [(k, s) for k, s in stats if s["list_price"]]
    if not stats:
        return None
    (site, slot), best = min(stats, key=lambda kv: kv[1]["list_price"])
    if overall_price - best["list_price"] < MIN_PRICE_GAP:
        return None
    _, a, b = SLOT_HOURS[slot]
    now_local = now_utc.astimezone(tz)
    floor_at = (now_utc + timedelta(days=days)).astimezone(tz)
    chosen = None
    for offset in range(int(days) + 2):
        day = (now_local + timedelta(days=offset)).date()
        start = datetime(day.year, day.month, day.day, a, tzinfo=tz)
        end = start + timedelta(hours=b - a)
        if end > now_local and start < floor_at:
            chosen = max(start, now_local)
    if chosen is None:
        return None
    recent = [x["kwh"] for x in priced[:5]]
    kwh = sorted(recent)[len(recent) // 2]
    saving = (overall_price - best["list_price"]) * kwh
    label, rng = (i18n.SLOTS.get(lang) or i18n.SLOTS["en"])[slot]
    offset = (chosen.date() - now_local.date()).days
    day = i18n.t(lang, "today") if offset == 0 else i18n.t(lang, "tomorrow") if offset == 1 else i18n.date_label(lang, chosen)
    when = f"{day}, {rng}"
    place = _place(site)
    return {
        "date": chosen.date().isoformat(), "when": when, "slot": label, "range": rng, "site": site,
        "price": best["list_price"], "average": overall_price, "kwh": round(kwh), "saving": round(saving, 2),
        "sessions": best["sessions"],
        "text": i18n.t(lang, "plan", when=when, site=place, best=money(best["list_price"]),
                       avg=money(overall_price), saving=money(saving), kwh=round(kwh)),
    }


def _session_view(x: dict, tz, lang: str) -> dict:
    start = datetime.fromisoformat(x["start_ts"]).astimezone(tz) if x.get("start_ts") else None
    stop = datetime.fromisoformat(x["stop_ts"]).astimezone(tz) if x.get("stop_ts") else None
    return {
        "id": x["session_id"],
        "site": x.get("site") or i18n.t(lang, "unknown_site"),
        "start": _iso(start),
        "end": _iso(stop),
        "kwh": x.get("kwh"),
        "cost": x.get("total"),
        "charge_cost": x.get("charge_cost"),
        "idle": x.get("idle_fee") or 0.0,
        "price": x.get("price"),
        "list_price": x.get("list_price") if x.get("list_price") is not None else x.get("price"),
        "credit": x.get("credit") or 0.0,
        "net": x.get("net_total"),
        "duration_min": round((stop - start).total_seconds() / 60) if (start and stop) else None,
        "avg_kw": round(x["kwh"] / _hours(x)) if x.get("kwh") and _hours(x) else None,
        "has_invoice": bool(x.get("invoices")),
        "push_state": x.get("push_state"),
        "currency": x.get("currency") or "EUR",
        "network": x.get("network") or SUPERCHARGER,
    }


MAP_SEARCH = "https://www.google.com/maps/search/?api=1&query="


def map_url(site: str) -> str:
    """A map search for a site name. Only a link: nothing is looked up or sent by Ladecockpit."""
    return MAP_SEARCH + quote(site)


def _multipass(sessions: list[dict], tz, lang: str) -> dict | None:
    """Third-party stations where paying with Tesla MultiPass has worked, from your own invoices:
    per station sessions, energy, avg price, first and last use, plus the operators behind them.
    Nothing is fetched for this – it only regroups the charging history."""
    used = [x for x in sessions if (x.get("network") or SUPERCHARGER) == MULTIPASS and x.get("start_ts")]
    if not used:
        return None
    groups: dict[str, list[dict]] = {}
    for x in used:
        groups.setdefault(x.get("site") or i18n.t(lang, "unknown_station"), []).append(x)
    stations = []
    for site, items in groups.items():
        when = sorted(datetime.fromisoformat(x["start_ts"]).astimezone(tz) for x in items)
        priced = [x for x in items if x.get("kwh") and x.get("total") is not None]
        st = _stats(priced)
        stations.append({
            "site": site, "operator": networks.operator(site), "sessions": len(items),
            "kwh": st["kwh"], "cost": st["cost"], "avg_price": st["list_price"], "avg_kw": _avg_kw(priced),
            "first": when[0].date().isoformat(), "last": _iso(when[-1]),
            "last_label": i18n.day_label(lang, when[-1]), "map_url": map_url(site),
        })
    stations.sort(key=lambda s: s["last"], reverse=True)
    ops: dict[str, dict] = {}
    for s in stations:
        if not s["operator"]:
            continue
        o = ops.setdefault(s["operator"], {"name": s["operator"], "stations": 0, "sessions": 0, "last": s["last"]})
        o["stations"] += 1
        o["sessions"] += s["sessions"]
        o["last"] = max(o["last"], s["last"])
    operators = sorted(ops.values(), key=lambda o: (-o["sessions"], o["name"].lower()))
    total = _stats([x for x in used if x.get("kwh") and x.get("total") is not None])
    names = ", ".join(o["name"] for o in operators)
    key = "mp_summary_one" if len(stations) == 1 else "mp_summary_many"
    text = i18n.t(lang, key, n=len(stations), ops=i18n.t(lang, "mp_operators", names=names) if names else "")
    return {"stations": stations, "operators": operators, "sessions": len(used), "kwh": total["kwh"],
            "cost": total["cost"], "avg_price": total["list_price"], "text": text}


def _by_network(items: list[dict]) -> dict:
    groups: dict[str, list[dict]] = {}
    for x in items:
        groups.setdefault(x.get("network") or SUPERCHARGER, []).append(x)
    return {k: _stats(v) for k, v in groups.items()}


def build_dashboard(*, sessions: list[dict], live: dict, readings: dict, settings: Settings,
                    meta: dict, now: datetime | None = None) -> dict:
    tz, lang = settings.tz, settings.lang
    now_utc = now or datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    values = live.get("values", {})
    units = live.get("units", {})

    priced = [x for x in sessions if x.get("kwh") and x.get("total") is not None and x.get("start_ts")]
    for x in priced:
        x["_local"] = datetime.fromisoformat(x["start_ts"]).astimezone(tz)
    priced.sort(key=lambda x: x["_local"], reverse=True)
    currency = Counter(x.get("currency") or "EUR" for x in priced).most_common(1)[0][0] if priced else "EUR"
    money = lambda v: i18n.money(lang, v, currency)  # noqa: E731
    unit = units.get("odometer") or units.get("range") or "km"
    unit = "mi" if unit.lower().startswith("mi") else "km"

    # --- battery / status ------------------------------------------------------
    soc = range_dist = as_of = source = None
    if values.get("soc") is not None:
        soc, source, as_of = values["soc"], "live", now_utc
        range_dist = values.get("range")
    elif readings.get("soc_last"):
        as_of, soc = readings["soc_last"]
        source = "last"
        last_range = readings.get("range_last")
        range_dist = last_range[1] if last_range else None
    status = {"soc": soc, "soc_source": source, "as_of": _iso(as_of), "range": range_dist,
              "floor": settings.soc_floor, "target": settings.soc_target}

    soc_hist = readings.get("soc") or []
    if len(soc_hist) < 3:
        soc_hist = readings.get("soc_ha") or soc_hist
    odo_all = readings.get("odometer") or []
    odo_14d = [p for p in odo_all if p[0] >= now_utc - timedelta(days=14)]
    forecast = _forecast(lang, soc_hist, soc, settings.soc_floor, now_utc, tz, odo_14d)

    # --- comparison with a combustion car ------------------------------------------------------
    consumption = values.get("fuel_consumption") or settings.fuel_consumption
    fuel_price = values.get("fuel_price") or settings.fuel_price
    fuel = None
    if consumption and fuel_price:
        fuel = {"consumption": round(consumption, 1), "price": round(fuel_price, 3),
                "per_100": round(consumption * fuel_price, 2)}

    def with_fuel(entry: dict) -> dict:
        entry["fuel_equivalent"] = entry["savings"] = None
        if fuel and entry.get("distance") and entry.get("per_100") is not None:
            entry["fuel_equivalent"] = round(fuel["per_100"] * entry["distance"] / 100, 2)
            entry["savings"] = round((fuel["per_100"] - entry["per_100"]) * entry["distance"] / 100, 2)
        return entry

    # --- this month ------------------------------------------------------------------
    cur_key = _month_key(now_local)
    prev_key = _month_key(now_local.replace(day=1) - timedelta(days=1))
    by_month: dict[str, list[dict]] = {}
    for x in priced:
        by_month.setdefault(_month_key(x["_local"]), []).append(x)

    month = _stats(by_month.get(cur_key, []))
    month.update(key=cur_key, label=i18n.month_label(lang, cur_key))
    home = readings.get("home") or []

    def month_distance(key: str) -> dict:
        start, end = _month_bounds(key, tz)
        odo = [p for p in odo_all if start <= p[0] < end]
        return _distance(odo, by_month.get(key, []), home)

    def month_home(key: str) -> dict | None:
        if not home:
            return None
        start, end = _month_bounds(key, tz)
        return _home_sum(home, start, end)

    dist = month_distance(cur_key)
    month.update(dist, distance_since=_iso(dist["distance_since"].astimezone(tz)) if dist["distance_since"] else None)
    month["avg_kw"] = _avg_kw(by_month.get(cur_key, []))
    month["by_network"] = _by_network(by_month.get(cur_key, []))
    month["home"] = month_home(cur_key)
    month["total_cost"] = round(month["cost"] + ((month["home"] or {}).get("cost") or 0.0), 2)
    with_fuel(month)
    prev = _stats(by_month.get(prev_key, []))
    month["prev"] = {"label": i18n.month_label(lang, prev_key, with_year=False),
                     "cost": prev["cost"], "avg_price": prev["avg_price"], "list_price": prev["list_price"],
                     "sessions": prev["sessions"]}

    monthly = []
    cursor = now_local.replace(day=1)
    for _ in range(6):
        key = _month_key(cursor)
        st = _stats(by_month.get(key, []))
        md = month_distance(key)
        nets = _by_network(by_month.get(key, []))
        monthly.append(with_fuel({
            "key": key, "label": i18n.month_label(lang, key, with_year=False)[:3],
            "cost": st["cost"], "kwh": st["kwh"], "avg_price": st["avg_price"], "idle": st["idle"],
            "sessions": st["sessions"], "distance": md["distance"],
            "per_100": md["per_100"], "kwh_per_100": md["kwh_per_100"],
            "multipass_cost": nets.get(MULTIPASS, {}).get("cost"),
            "multipass_sessions": nets.get(MULTIPASS, {}).get("sessions"),
            "home_kwh": (month_home(key) or {}).get("kwh"), "home_cost": (month_home(key) or {}).get("cost")}))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    monthly.reverse()
    first = next((i for i, m in enumerate(monthly) if m["sessions"] or m.get("home_kwh")), len(monthly) - 1)
    monthly = monthly[first:]

    # --- price radar ----------------------------------------------------------------------
    overall = _stats(priced)
    slots = []
    for (sid, a, b), (label, rng) in zip(SLOT_HOURS, i18n.SLOTS.get(lang, i18n.SLOTS["en"])):
        st = _stats([x for x in priced if a <= x["_local"].hour < b])
        slots.append({"id": sid, "label": label, "range": rng,
                      "avg_price": st["list_price"], "sessions": st["sessions"], "kwh": st["kwh"]})

    groups: dict[str, list[dict]] = {}
    for x in priced:
        groups.setdefault(x.get("site") or i18n.t(lang, "unknown_site"), []).append(x)
    sites = sorted(
        ({"site": k, **{f: _stats(v)[f] for f in ("sessions", "kwh", "cost", "credit")},
          "avg_price": _stats(v)["list_price"], "avg_kw": _avg_kw(v),
          "network": Counter(x.get("network") or SUPERCHARGER for x in v).most_common(1)[0][0]}
         for k, v in groups.items()),
        key=lambda r: (-r["sessions"], r["avg_price"] or 9),
    )

    insights: list[dict] = []
    used = [s for s in slots if s["sessions"]]
    if len(priced) >= 4 and len(used) >= 2 and overall["list_price"]:
        best = min(used, key=lambda s: s["avg_price"])
        diff = overall["list_price"] - best["avg_price"]
        if diff >= MIN_PRICE_GAP:
            insights.append({"kind": "slot", "text": i18n.t(
                lang, "in_slot_best", label=best["label"], range=best["range"],
                price=money(best["avg_price"]), diff=money(diff))})
        else:
            insights.append({"kind": "slot", "text": i18n.t(lang, "in_slot_flat")})
    else:
        insights.append({"kind": "slot", "text": i18n.t(lang, "in_slot_wait")})

    priced_sites = [r for r in sites if r["avg_price"]]
    if len(priced_sites) >= 2 and len(priced) >= 4:
        lo = min(priced_sites, key=lambda r: r["avg_price"])
        hi = max(priced_sites, key=lambda r: r["avg_price"])
        if hi["avg_price"] - lo["avg_price"] >= 0.01:
            insights.append({"kind": "site", "text": i18n.t(
                lang, "in_site", lo=_place(lo["site"]), lo_price=money(lo["avg_price"]),
                hi=_place(hi["site"]), hi_price=money(hi["avg_price"]))})

    nets = _by_network(priced)
    mp, sc = nets.get(MULTIPASS), nets.get(SUPERCHARGER)
    if mp and sc and mp["list_price"] and sc["list_price"]:
        insights.append({"kind": "network", "text": i18n.t(
            lang, "in_network", mp=money(mp["list_price"]), sc=money(sc["list_price"]),
            n=mp["sessions"])})

    if overall["credit"] > 0:
        insights.append({"kind": "credit", "text": i18n.t(
            lang, "in_credit", amount=money(overall["credit"]),
            paid=money(overall["avg_price"]), listed=money(overall["list_price"]))})

    if overall["idle"] > 0:
        n_idle = sum(1 for x in priced if (x.get("idle_fee") or 0) > 0)
        key = "in_idle_one" if n_idle == 1 else "in_idle_many"
        insights.append({"kind": "idle", "text": i18n.t(lang, key, amount=money(overall["idle"]), n=n_idle)})

    # --- comparisons -------------------------------------------------------------------------
    reference = values.get("reference_price")
    if reference is None:
        reference = settings.reference_price
    compare = {"fuel": fuel, "reference_price": reference, "reference_cost": None,
               "actual_cost": month["charge_cost"] if month["sessions"] else None,
               "fuel_month": values.get("fuel_month"),
               "fuel_label": settings.fuel_label or i18n.t(lang, "fuel_default")}
    if reference and month["kwh"]:
        compare["reference_cost"] = round(month["kwh"] * reference, 2)
        delta = compare["reference_cost"] - month["charge_cost"]
        if abs(delta) >= 0.5:
            insights.append({"kind": "reference", "text": i18n.t(
                lang, "in_reference", ref=money(reference), ref_cost=money(compare["reference_cost"]),
                actual=money(month["charge_cost"]), sign="+" if delta < 0 else "−", delta=money(abs(delta)))})

    if month.get("savings") is not None and month["savings"] >= 1:
        insights.append({"kind": "fuel", "text": i18n.t(
            lang, "in_fuel", dist=i18n.num(lang, month["distance"], 0), fuel=money(month["fuel_equivalent"]),
            saved=money(month["savings"]),
            consumption=i18n.num(lang, fuel["consumption"], 1), price=money(fuel["price"]), unit=unit)})

    health = vehicle.battery_health(readings.get("soc_long") or [], readings.get("range_long") or [], tz)
    kwh_pct = vehicle.kwh_per_percent(priced, readings.get("soc_long") or [])
    climate = vehicle.consumption_by_temperature(readings.get("soc_long") or [], odo_all,
                                                 readings.get("temp") or [], tz, kwh_pct)
    if climate and len(climate["bands"]) >= 2:
        cold, warm = climate["bands"][0], climate["bands"][-1]
        more = (cold["pct_per_100"] / warm["pct_per_100"] - 1) * 100 if warm["pct_per_100"] else 0
        if more >= 5:
            insights.append({"kind": "climate", "text": i18n.t(
                lang, "in_climate", cold=i18n.temp_band(lang, cold["from"], cold["to"]),
                warm=i18n.temp_band(lang, warm["from"], warm["to"]), more=round(more), unit=unit)})

    forecast["plan"] = _plan(lang, forecast, priced, overall["list_price"], now_utc, tz, money)
    projection = _projection(odo_all, priced, now_utc, fuel, home)
    if health and home:
        year_start = now_utc - timedelta(days=365)
        dc = sum(x["kwh"] for x in priced if x["_local"] >= year_start and (x.get("network") or SUPERCHARGER) == SUPERCHARGER)
        home_kwh = _home_sum(home, year_start)["kwh"]
        all_kwh = sum(x["kwh"] for x in priced if x["_local"] >= year_start) + home_kwh
        health["dc_share"] = round(dc / all_kwh * 100) if all_kwh else None

    reconcile = None
    if settings.ent_cost_total or settings.ent_kwh_total:
        ha_cost = values.get("cost_total")
        reconcile = {
            "ha_cost": ha_cost, "ha_kwh": values.get("kwh_total"),
            "inv_cost": overall["cost"], "inv_kwh": overall["kwh"], "inv_sessions": overall["sessions"],
            "diff": round(ha_cost - overall["cost"], 2) if ha_cost is not None and priced else None,
        }

    # --- API usage -------------------------------------------------------------------------------
    by_cat = meta.get("api_calls") or {}
    calls = sum(by_cat.values())
    api = {"calls": calls, "by_category": by_cat, "cost_usd": round(calls * USD_PER_DATA_CALL, 2),
           "budget": settings.api_budget, "credit_usd": MONTHLY_CREDIT_USD}

    totals = dict(overall)
    totals["by_network"] = nets
    totals["since"] = _iso(priced[-1]["_local"]) if priced else None

    return {
        "mode": meta.get("mode", "live"),
        "lang": lang,
        "locale": settings.locale,
        "tz": str(tz),
        "currency": currency,
        "distance_unit": unit,
        "generated_at": _iso(now_local),
        "setup": meta.get("setup", {}),
        "sync": meta.get("sync", {}),
        "status": status,
        "forecast": forecast,
        "last_charge": _session_view(priced[0], tz, lang) if priced else None,
        "month": month,
        "monthly": monthly,
        "slots": slots,
        "sites": sites,
        "multipass": _multipass(sessions, tz, lang),
        "insights": insights,
        "compare": compare,
        "projection": projection,
        "battery_health": health,
        "climate": climate,
        "reconcile": reconcile,
        "totals": totals,
        "sessions": [_session_view(x, tz, lang) for x in sessions[:40]],
        "api": api,
    }

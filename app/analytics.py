"""Turns invoices + readings + Home Assistant values into the dashboard JSON."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from . import i18n
from .config import Settings

SLOT_HOURS = [("night", 0, 6), ("morning", 6, 11), ("midday", 11, 16), ("afternoon", 16, 20), ("evening", 20, 24)]
USD_PER_DATA_CALL = 0.002
MONTHLY_CREDIT_USD = 10.0


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _month_key(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def _stats(items: list[dict]) -> dict:
    kwh = sum(i["kwh"] for i in items)
    charge = sum(i["charge_cost"] or 0.0 for i in items)
    total = sum(i["total"] for i in items)
    idle = sum(i["idle_fee"] or 0.0 for i in items)
    return {
        "sessions": len(items),
        "kwh": round(kwh, 1),
        "cost": round(total, 2),
        "charge_cost": round(charge, 2),
        "idle": round(idle, 2),
        "avg_price": round(charge / kwh, 4) if kwh else None,
    }


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
        "duration_min": round((stop - start).total_seconds() / 60) if (start and stop) else None,
        "has_invoice": bool(x.get("invoices")),
        "push_state": x.get("push_state"),
        "currency": x.get("currency") or "EUR",
    }


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

    # --- this month ------------------------------------------------------------------
    cur_key = _month_key(now_local)
    prev_key = _month_key(now_local.replace(day=1) - timedelta(days=1))
    by_month: dict[str, list[dict]] = {}
    for x in priced:
        by_month.setdefault(_month_key(x["_local"]), []).append(x)

    month = _stats(by_month.get(cur_key, []))
    month.update(key=cur_key, label=i18n.month_label(lang, cur_key))
    month_start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    odo_month = [p for p in odo_all if p[0] >= month_start]
    month["distance"] = month["per_100"] = month["distance_since"] = None
    if len(odo_month) >= 2:
        dist = odo_month[-1][1] - odo_month[0][1]
        since = odo_month[0][0]
        month["distance"] = round(dist)
        month["distance_since"] = _iso(since.astimezone(tz))
        covered = [x for x in by_month.get(cur_key, []) if x["_local"] >= since]
        if dist >= 50 and covered:
            month["per_100"] = round(sum(x["total"] for x in covered) / dist * 100, 2)
    prev = _stats(by_month.get(prev_key, []))
    month["prev"] = {"label": i18n.month_label(lang, prev_key, with_year=False),
                     "cost": prev["cost"], "avg_price": prev["avg_price"], "sessions": prev["sessions"]}

    monthly = []
    cursor = now_local.replace(day=1)
    for _ in range(6):
        key = _month_key(cursor)
        st = _stats(by_month.get(key, []))
        monthly.append({"key": key, "label": i18n.month_label(lang, key, with_year=False)[:3],
                        "cost": st["cost"], "kwh": st["kwh"], "avg_price": st["avg_price"],
                        "sessions": st["sessions"]})
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    monthly.reverse()
    first = next((i for i, m in enumerate(monthly) if m["sessions"]), len(monthly) - 1)
    monthly = monthly[first:]

    # --- price radar ----------------------------------------------------------------------
    overall = _stats(priced)
    slots = []
    for (sid, a, b), (label, rng) in zip(SLOT_HOURS, i18n.SLOTS.get(lang, i18n.SLOTS["en"])):
        st = _stats([x for x in priced if a <= x["_local"].hour < b])
        slots.append({"id": sid, "label": label, "range": rng,
                      "avg_price": st["avg_price"], "sessions": st["sessions"], "kwh": st["kwh"]})

    groups: dict[str, list[dict]] = {}
    for x in priced:
        groups.setdefault(x.get("site") or i18n.t(lang, "unknown_site"), []).append(x)
    sites = sorted(
        ({"site": k, **{f: _stats(v)[f] for f in ("sessions", "kwh", "avg_price", "cost")}}
         for k, v in groups.items()),
        key=lambda r: (-r["sessions"], r["avg_price"] or 9),
    )

    insights: list[dict] = []
    used = [s for s in slots if s["sessions"]]
    if len(priced) >= 4 and len(used) >= 2 and overall["avg_price"]:
        best = min(used, key=lambda s: s["avg_price"])
        diff = overall["avg_price"] - best["avg_price"]
        if diff >= 0.01:
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
                lang, "in_site", lo=lo["site"], lo_price=money(lo["avg_price"]),
                hi=hi["site"], hi_price=money(hi["avg_price"]))})

    if overall["idle"] > 0:
        n_idle = sum(1 for x in priced if (x.get("idle_fee") or 0) > 0)
        key = "in_idle_one" if n_idle == 1 else "in_idle_many"
        insights.append({"kind": "idle", "text": i18n.t(lang, key, amount=money(overall["idle"]), n=n_idle)})

    # --- comparisons -------------------------------------------------------------------------
    reference = values.get("reference_price")
    if reference is None:
        reference = settings.reference_price
    compare = {"reference_price": reference, "reference_cost": None,
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
        "insights": insights,
        "compare": compare,
        "reconcile": reconcile,
        "totals": totals,
        "sessions": [_session_view(x, tz, lang) for x in sessions[:40]],
        "api": api,
    }

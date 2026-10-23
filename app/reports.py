"""Monthly report: on the first days of a month, a summary of the previous one.

Always fired as the event ladecockpit_month_report (for your own automations, e.g. a push
message), plus a notification in Home Assistant when the option month_report is on.
Each month is reported once. A fresh install starts with the next month change, so it
does not report a month it barely saw.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from . import i18n
from .config import Settings
from .db import DB
from .homeassistant import HAClient

log = logging.getLogger("ladecockpit.reports")

EVENT = "ladecockpit_month_report"
CHECK_EVERY_S = 900
KV_KEY = "report_month"


def _key(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def build_report(d: dict, month_key: str, lang: str) -> dict | None:
    """Event payload for one month of the dashboard data (None without sessions)."""
    entry = next((m for m in d.get("monthly") or [] if m.get("key") == month_key), None)
    if not entry or not entry.get("sessions"):
        return None
    cur = d.get("currency") or "EUR"
    unit = d.get("distance_unit") or "km"
    money = lambda v: i18n.money(lang, v, cur)  # noqa: E731
    label = i18n.month_label(lang, month_key)
    parts = [i18n.t(lang, "report_text", sessions=entry["sessions"], kwh=i18n.num(lang, entry["kwh"], 0),
                    cost=money(entry["cost"]), price=money(entry["avg_price"] or 0))]
    if entry.get("distance") and entry.get("per_100") is not None:
        parts.append(i18n.t(lang, "report_distance", dist=i18n.num(lang, entry["distance"], 0),
                            per100=money(entry["per_100"]), unit=unit))
    if entry.get("savings") is not None:
        parts.append(i18n.t(lang, "report_fuel", fuel=money(entry["fuel_equivalent"]), saved=money(entry["savings"])))
    if entry.get("multipass_cost"):
        parts.append(i18n.t(lang, "report_multipass", cost=money(entry["multipass_cost"])))
    if entry.get("idle"):
        parts.append(i18n.t(lang, "report_idle", cost=money(entry["idle"])))
    return {
        "month": month_key, "label": label, "currency": cur, "distance_unit": unit,
        "sessions": entry["sessions"], "kwh": entry["kwh"], "cost": entry["cost"],
        "price_per_kwh": entry["avg_price"], "idle_fees": entry.get("idle"),
        "distance": entry.get("distance"), "cost_per_100": entry.get("per_100"),
        "kwh_per_100": entry.get("kwh_per_100"), "multipass_cost": entry.get("multipass_cost"),
        "fuel_equivalent": entry.get("fuel_equivalent"), "savings": entry.get("savings"),
        "title": i18n.t(lang, "report_title", month=label),
        "text": " ".join(parts),
    }


class MonthReporter:
    def __init__(self, settings: Settings, db: DB, ha: HAClient, build: Callable[[], Awaitable[dict]]):
        self.s = settings
        self.db = db
        self.ha = ha
        self.build = build

    async def run_forever(self) -> None:
        await asyncio.sleep(60)
        while True:
            try:
                await self.check()
            except Exception:  # noqa: BLE001 – try again later
                log.exception("Monthly report failed")
            await asyncio.sleep(CHECK_EVERY_S)

    async def check(self, now: datetime | None = None) -> dict | None:
        now_local = (now or datetime.now(timezone.utc)).astimezone(self.s.tz)
        current = _key(now_local)
        done = self.db.kv_get(KV_KEY)
        if done is None:
            self.db.kv_set(KV_KEY, current)  # fresh install: start with the next month change
            return None
        if done >= current:
            return None
        previous = _key(now_local.replace(day=1) - timedelta(days=1))
        d = await self.build()
        if not (d.get("setup") or {}).get("ha_ok", True):
            return None  # try again when Home Assistant is back
        report = build_report(d, previous, self.s.lang)
        if report:
            if not await self.ha.fire_event(EVENT, report):
                return None
            if self.s.month_report:
                await self.ha.call_service("persistent_notification", "create", {
                    "notification_id": f"ladecockpit_report_{previous}",
                    "title": report["title"], "message": report["text"],
                })
            log.info("Monthly report for %s sent", previous)
        self.db.kv_set(KV_KEY, current)
        return report

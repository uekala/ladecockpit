"""Monatsbericht: an den ersten Tagen eines Monats eine Zusammenfassung des vorigen.

Immer als Event ladecockpit_month_report ausgelöst (für eigene Automationen, z. B. eine Push-
Nachricht), dazu eine Benachrichtigung in Home Assistant, wenn die Option month_report an ist.
Jeder Monat wird einmal berichtet. Eine Neuinstallation beginnt mit dem nächsten Monatswechsel,
damit sie keinen Monat berichtet, den sie kaum gesehen hat.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from . import i18n
from .config import Settings
from .db import DB
from .homeassistant import HAClient
from .push import Ntfy

log = logging.getLogger("ladecockpit.reports")

EVENT = "ladecockpit_month_report"
CHECK_EVERY_S = 900
KV_KEY = "report_month"


def _key(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def build_report(d: dict, month_key: str, lang: str) -> dict | None:
    """Event-Daten für einen Monat der Dashboard-Daten (None ohne Ladungen)."""
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
    if entry.get("home_kwh"):
        if entry.get("home_cost") is not None:
            parts.append(i18n.t(lang, "report_home", kwh=i18n.num(lang, entry["home_kwh"], 0), cost=money(entry["home_cost"])))
        else:
            parts.append(i18n.t(lang, "report_home_kwh", kwh=i18n.num(lang, entry["home_kwh"], 0)))
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
        "home_kwh": entry.get("home_kwh"), "home_cost": entry.get("home_cost"),
        "title": i18n.t(lang, "report_title", month=label),
        "text": " ".join(parts),
    }


class MonthReporter:
    def __init__(self, settings: Settings, db: DB, ha: HAClient, build: Callable[[], Awaitable[dict]],
                 push: Ntfy | None = None):
        self.s = settings
        self.db = db
        self.ha = ha
        self.build = build
        self.push = push

    async def run_forever(self) -> None:
        await asyncio.sleep(60)
        while True:
            try:
                await self.check()
            except Exception:
                log.exception("Monthly report failed")
            await asyncio.sleep(CHECK_EVERY_S)

    async def check(self, now: datetime | None = None) -> dict | None:
        now_local = (now or datetime.now(UTC)).astimezone(self.s.tz)
        current = _key(now_local)
        done = self.db.kv_get(KV_KEY)
        if done is None:
            self.db.kv_set(KV_KEY, current)  # Neuinstallation: mit dem nächsten Monatswechsel beginnen
            return None
        if done >= current:
            return None
        previous = _key(now_local.replace(day=1) - timedelta(days=1))
        d = await self.build()
        use_ha = getattr(self.ha, "configured", True)
        if use_ha and not (d.get("setup") or {}).get("ha_ok", True):
            return None  # erneut versuchen, wenn Home Assistant zurück ist
        report = build_report(d, previous, self.s.lang)
        if report:
            if use_ha and not await self.ha.fire_event(EVENT, report):
                return None
            if self.push and self.push.configured and self.s.month_report:
                await self.push.send(report["title"], report["text"], tags=["calendar"])
            if use_ha and self.s.month_report:
                await self.ha.call_service("persistent_notification", "create", {
                    "notification_id": f"ladecockpit_report_{previous}",
                    "title": report["title"], "message": report["text"],
                })
            log.info("Monthly report for %s sent", previous)
        self.db.kv_set(KV_KEY, current)
        return report

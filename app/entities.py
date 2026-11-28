"""Ladecockpits eigene Entitäten in Home Assistant, für Dashboards und Automationen.

Ohne die Ladecockpit-Integration werden sie über die REST-API geschrieben (POST /api/states),
es braucht also kein YAML und keine eigene Integration. Solche Entitäten haben keine eindeutige ID:
Sie lassen sich in der Oberfläche nicht umbenennen und fehlen nach einem Neustart von Home
Assistant, bis Ladecockpit sie wieder schreibt (innerhalb weniger Minuten).

Ist die Integration (custom_components/ladecockpit, z. B. über HACS) geladen, geht jeder Zustand
stattdessen als Event an sie. Die Integration führt echte Entitäten mit denselben Entitäts-IDs,
einer eindeutigen ID und einem Gerät und stellt sie nach einem Neustart wieder her.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from . import i18n
from .config import Settings
from .homeassistant import HAClient

log = logging.getLogger("ladecockpit.entities")

PUBLISH_EVERY_S = 60
REWRITE_ALL_S = 600     # ab und zu alles neu schreiben, z. B. nach einem Neustart von HA
EVENT_REWRITE_ALL_S = 3600  # dasselbe mit der Integration, die ihre Entitäten selbst wiederherstellt
INTEGRATION = "ladecockpit"        # the integration's domain, see custom_components/ladecockpit
STATE_EVENT = "ladecockpit_state"  # one event per entity: {"entity_id", "state", "attributes"}
INTEGRATION_CHECK_S = 300           # wie oft Home Assistant gefragt wird, ob sie geladen ist
MAX_STATE_LEN = 255     # Home Assistant rejects longer states
MAX_STATIONS = 30       # hält die Attribute deutlich unter der Grenze von 16 KB des Recorders

ENTITY_IDS = (
    "sensor.ladecockpit_next_charge",
    "sensor.ladecockpit_battery",
    "sensor.ladecockpit_month_cost",
    "sensor.ladecockpit_month_energy",
    "sensor.ladecockpit_last_charge",
    "sensor.ladecockpit_price_tip",
    "sensor.ladecockpit_range_at_100",
    "sensor.ladecockpit_consumption",
    "sensor.ladecockpit_car",
    "sensor.ladecockpit_multipass",
    "binary_sensor.ladecockpit_problem",
)


def _season_attrs(seasons: dict | None, lang: str, insights: list[dict]) -> dict:
    """Winter- und Sommerzeit und die vier Jahreszeiten der letzten zwölf Monate als Attribute des Verbrauchssensors."""
    by_id = {s["id"]: s for s in (seasons or {}).get("seasons") or []}
    out = {}
    for sid in ("winter", "summer"):
        s = by_id.get(sid) or {}
        out[f"{sid}_kwh_per_100"] = s.get("kwh_per_100")
        out[f"{sid}_cost_per_100"] = s.get("per_100")
        out[f"{sid}_distance"] = s.get("distance")
        out[f"{sid}_price_per_kwh"] = _round(s.get("avg_price"), 4)
    out["season_now"] = i18n.t(lang, f"season_{seasons['current']}") if seasons else None
    out["winter_more_kwh_pct"] = (seasons or {}).get("kwh_diff_pct")
    out["winter_more_cost_pct"] = (seasons or {}).get("cost_diff_pct")
    out["season_tip"] = next((i["text"] for i in insights if i.get("kind") == "season"), None)
    current = (seasons or {}).get("current_quarter")
    out["by_season"] = [{"id": q["id"], "label": i18n.t(lang, f"quarter_{q['id']}"), "current": q["id"] == current,
                         "distance": q["distance"], "kwh_per_100": q["kwh_per_100"], "cost_per_100": q["per_100"],
                         "price_per_kwh": _round(q["avg_price"], 4)}
                        for q in (seasons or {}).get("quarters") or []]
    out["quarter_now"] = i18n.t(lang, f"quarter_{current}") if current else None
    return out


def _round(value, digits: int):
    return None if value is None else round(value, digits)


def _state(value, digits: int = 2) -> str:
    if value is None:
        return "unknown"
    if digits == 0:
        return str(round(value))
    return f"{value:.{digits}f}"


def _when(lang: str, iso: str | None) -> str:
    if not iso:
        return "–"
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%d.%m. %H:%M") if lang == "de" else f"{dt:%b} {dt.day}, {dt:%H:%M}"


def _month_start(d: dict) -> str | None:
    """Beginn des angezeigten Monats als `last_reset` – Home Assistant führt dann eine Langzeitstatistik
    der Monatssummen (state_class total) und beginnt jeden Monat eine neue Summe."""
    key = (d.get("month") or {}).get("key")
    if not key:
        return None
    try:
        tz = ZoneInfo(d.get("tz") or "UTC")
    except (KeyError, ValueError):
        tz = ZoneInfo("UTC")
    year, month = (int(v) for v in key.split("-"))
    return datetime(year, month, 1, tzinfo=tz).isoformat()


def build_states(d: dict, lang: str) -> dict[str, tuple[str, dict]]:
    """Entitäts-ID → (Zustand, Attribute), aus denselben Daten, die die Web-App zeigt."""
    name = lambda key: f"Ladecockpit {i18n.t(lang, 'ent_' + key)}"  # noqa: E731
    cur = d.get("currency") or "EUR"
    unit = d.get("distance_unit") or "km"
    money = lambda v: i18n.money(lang, v, cur)  # noqa: E731
    out: dict[str, tuple[str, dict]] = {}

    # --- next charging stop ---------------------------------------------------------------
    fc, st = d.get("forecast") or {}, d.get("status") or {}
    out["sensor.ladecockpit_next_charge"] = (fc.get("date_floor") or "unknown", {
        "friendly_name": name("next_charge"), "icon": "mdi:ev-station", "device_class": "date",
        "text": fc.get("text"), "label": fc.get("date_label"),
        "days": fc.get("days_to_floor"), "calendar_days": fc.get("calendar_days"),
        "battery_drop_per_day": fc.get("rate_pct_day"), "distance_per_day": fc.get("dist_day"),
        "distance_unit": unit, "battery_floor": st.get("floor"),
        "plan": (fc.get("plan") or {}).get("text"), "plan_date": (fc.get("plan") or {}).get("date"),
        "plan_site": (fc.get("plan") or {}).get("site"), "plan_saving": (fc.get("plan") or {}).get("saving"),
    })

    # --- Akku (auch der zuletzt bekannte Wert, während das Auto offline ist) ----------------------
    last_known = st.get("soc_source") == "last"
    out["sensor.ladecockpit_battery"] = (_state(st.get("soc"), 0), {
        "friendly_name": name("battery"), "unit_of_measurement": "%", "device_class": "battery",
        "state_class": "measurement", "range": _round(st.get("range"), 0), "distance_unit": unit,
        "last_known": last_known, "as_of": st.get("as_of") if last_known else None,
        "target": st.get("target"),
        "range_at_100": (d.get("battery_health") or {}).get("range_at_100"),
        "range_at_100_change_pct": (d.get("battery_health") or {}).get("change_pct"),
    })

    # --- this month -----------------------------------------------------------------------------
    m = d.get("month") or {}
    prev = m.get("prev") or {}
    home = m.get("home") or {}
    month_start = _month_start(d)
    out["sensor.ladecockpit_month_cost"] = (_state(m.get("total_cost", m.get("cost")) or 0.0), {
        "friendly_name": name("month_cost"), "unit_of_measurement": cur, "device_class": "monetary",
        "state_class": "total", "last_reset": month_start,
        "icon": "mdi:cash-multiple", "month": m.get("label"), "sessions": m.get("sessions"),
        "invoice_cost": m.get("cost"), "home_kwh": home.get("kwh"), "home_cost": home.get("cost"),
        "energy_kwh": m.get("kwh"), "price_per_kwh": _round(m.get("avg_price"), 4),
        "idle_fees": m.get("idle"), "credits": m.get("credit"), "list_price_per_kwh": _round(m.get("list_price"), 4),
        "distance": m.get("distance"), "distance_unit": unit,
        "cost_per_100": m.get("per_100"), "kwh_per_100": m.get("kwh_per_100"),
        "avg_power_kw": m.get("avg_kw"),
        "multipass_cost": (m.get("by_network") or {}).get("multipass", {}).get("cost"),
        "multipass_sessions": (m.get("by_network") or {}).get("multipass", {}).get("sessions"),
        "fuel_equivalent": m.get("fuel_equivalent"), "savings": m.get("savings"),
        "projected_year_cost": (d.get("projection") or {}).get("cost"),
        "projected_year_distance": (d.get("projection") or {}).get("distance"),
        "projected_year_savings": (d.get("projection") or {}).get("savings"),
        "previous_month": prev.get("label"),
        "previous_cost": prev.get("cost"), "previous_price_per_kwh": _round(prev.get("avg_price"), 4),
    })

    invoice_kwh = m.get("kwh") or 0.0
    out["sensor.ladecockpit_month_energy"] = (_state(invoice_kwh + (home.get("kwh") or 0.0), 1), {
        "friendly_name": name("month_energy"), "unit_of_measurement": "kWh", "device_class": "energy",
        "state_class": "total", "last_reset": month_start, "icon": "mdi:ev-station",
        "month": m.get("label"), "invoice_kwh": _round(invoice_kwh, 1), "home_kwh": home.get("kwh"),
        "sessions": m.get("sessions"),
    })

    # --- last session -------------------------------------------------------------------------
    last = d.get("last_charge")
    if last:
        multipass = last.get("network") == "multipass"
        text = " · ".join(p for p in (
            "MultiPass" if multipass else None,
            (last.get("operator") or last.get("site")) if multipass else last.get("site"),
            f"{i18n.num(lang, last['kwh'], 1)} kWh" if last.get("kwh") is not None else None,
            money(last["cost"]) if last.get("cost") is not None else None,
            f"{money(last['price'])}/kWh" if last.get("price") is not None else None,
            _when(lang, last.get("start")),
        ) if p)
        out["sensor.ladecockpit_last_charge"] = (_state(last.get("cost")), {
            "friendly_name": name("last_charge"), "unit_of_measurement": cur, "device_class": "monetary",
            "icon": "mdi:ev-plug-ccs2" if multipass else "mdi:ev-plug-tesla", "network": last.get("network"),
            "site": last.get("site"), "operator": last.get("operator"), "address": last.get("address"),
            "start": last.get("start"),
            "end": last.get("end"), "energy_kwh": _round(last.get("kwh"), 2),
            "price_per_kwh": _round(last.get("price"), 4), "list_price_per_kwh": _round(last.get("list_price"), 4),
            "credit": last.get("credit"), "idle_fee": last.get("idle"),
            "avg_power_kw": last.get("avg_kw"), "duration_min": last.get("duration_min"),
            "typical_power_kw": last.get("typical_kw"), "slow": bool(last.get("slow")), "start_soc": last.get("start_soc"),
            "text": text[:MAX_STATE_LEN], "session_id": last.get("id"),
        })
    else:
        out["sensor.ladecockpit_last_charge"] = ("unknown", {
            "friendly_name": name("last_charge"), "unit_of_measurement": cur, "device_class": "monetary",
            "icon": "mdi:ev-plug-tesla"})

    # --- price radar ------------------------------------------------------------------------------
    insights = d.get("insights") or []
    tip = next((i["text"] for i in insights if i.get("kind") == "slot"), None)
    slots = [s for s in d.get("slots") or [] if s.get("sessions")]
    best_slot = min(slots, key=lambda s: s["avg_price"]) if len(slots) >= 2 else None
    sites = [s for s in d.get("sites") or [] if s.get("avg_price")]
    best_site = min(sites, key=lambda s: s["avg_price"]) if sites else None
    out["sensor.ladecockpit_price_tip"] = ((tip or "unknown")[:MAX_STATE_LEN], {
        "friendly_name": name("price_tip"), "icon": "mdi:radar",
        "best_time": f"{best_slot['label']} ({best_slot['range']})" if best_slot else None,
        "best_time_price": _round(best_slot["avg_price"], 4) if best_slot else None,
        "best_site": best_site["site"] if best_site else None,
        "best_site_price": _round(best_site["avg_price"], 4) if best_site else None,
        "insights": [i["text"] for i in insights],
    })

    # --- battery health (long-term statistics: state_class measurement) ------------------------------
    h = d.get("battery_health") or {}
    out["sensor.ladecockpit_range_at_100"] = (_state(h.get("range_at_100"), 0), {
        "friendly_name": name("range_at_100"), "unit_of_measurement": unit, "device_class": "distance",
        "state_class": "measurement", "icon": "mdi:battery-heart-variant",
        "change_pct": h.get("change_pct"), "since": h.get("since"), "baseline": h.get("baseline"),
        "samples": h.get("samples"), "supercharger_share": h.get("dc_share"),
    })

    # --- Verbrauch: dieser Monat und nach Außentemperatur ---------------------------------------------
    climate = d.get("climate") or {}
    bands = [{"label": i18n.temp_band(lang, b["from"], b["to"]), "days": b["days"], "distance": b["distance"],
              "pct_per_100": b["pct_per_100"], "kwh_per_100": b["kwh_per_100"]} for b in climate.get("bands") or []]
    tip = next((i["text"] for i in insights if i.get("kind") == "climate"), None)
    out["sensor.ladecockpit_consumption"] = (_state(m.get("kwh_per_100"), 1), {
        "friendly_name": name("consumption"), "unit_of_measurement": f"kWh/100 {unit}",
        "state_class": "measurement", "icon": "mdi:thermometer-lines",
        "note": i18n.t(lang, "ent_consumption_note"), "by_temperature": bands, "temperature_tip": tip,
        **_season_attrs(d.get("seasons"), lang, insights),
    })

    # --- Bild des Autos (Konfigurator-Bild von Tesla, in der Web-App gewählt) ------------------------
    car = d.get("car")
    if car:
        labels, views = car.get("labels") or {}, car.get("views") or {}
        out["sensor.ladecockpit_car"] = (car["name"][:MAX_STATE_LEN], {
            "friendly_name": name("car"), "icon": "mdi:car-electric",
            "entity_picture": car.get("thumb"), "image": car.get("url"),
            **{f"image_{v}": u for v, u in views.items()},
            "model": labels.get("generation"), "trim": labels.get("trim"), "paint": labels.get("paint"),
            "wheels": labels.get("wheel"), "view": labels.get("view"), "auto_detected": car.get("auto"),
        })

    # --- Fremdstationen, an denen MultiPass funktioniert hat (aus den Rechnungen) --------------------
    mp = d.get("multipass") or {}
    stations = mp.get("stations") or []
    out["sensor.ladecockpit_multipass"] = (str(len(stations)), {
        "friendly_name": name("multipass"), "icon": "mdi:ev-plug-ccs2",
        "text": mp.get("text") or i18n.t(lang, "mp_none"),
        "stations": [{k: s.get(k) for k in ("site", "operator", "address", "sessions", "kwh", "avg_price", "last", "last_label", "map_url")}
                     for s in stations[:MAX_STATIONS]],
        "operators": mp.get("operators") or [],
        "sessions": mp.get("sessions") or 0, "energy_kwh": mp.get("kwh"), "cost": mp.get("cost"),
        "price_per_kwh": _round(mp.get("avg_price"), 4), "currency": cur,
    })

    # --- problems ------------------------------------------------------------------------------------
    setup, sync = d.get("setup") or {}, d.get("sync") or {}
    kind = sync.get("problem")
    if not kind and setup.get("tesla_configured") and not setup.get("tesla_connected"):
        kind = "not_connected"
    if not kind and setup.get("missing_entities"):
        kind = "entities"
    detail = {
        "auth": i18n.t(lang, "problem_auth"),
        "budget": i18n.t(lang, "problem_budget"),
        "sync": i18n.t(lang, "problem_sync", detail=(sync.get("error") or "")[:200]),
        "not_connected": i18n.t(lang, "problem_not_connected"),
        "entities": i18n.t(lang, "problem_entities", entities=", ".join(setup.get("missing_entities") or [])),
    }.get(kind)
    rec = d.get("reconcile") or {}
    api = d.get("api") or {}
    out["binary_sensor.ladecockpit_problem"] = ("on" if kind else "off", {
        "friendly_name": name("problem"), "device_class": "problem",
        "kind": kind, "message": detail, "last_sync": sync.get("last"), "next_sync": sync.get("next"),
        "invoices": (d.get("totals") or {}).get("sessions"), "reconcile_difference": rec.get("diff"),
        "api_requests_this_month": api.get("calls"), "api_budget": api.get("budget"),
    })
    return out


class EntityPublisher:
    def __init__(self, settings: Settings, ha: HAClient, build: Callable[[], Awaitable[dict]]):
        self.s = settings
        self.ha = ha
        self.build = build
        self._sent: dict[str, str] = {}
        self._last_full = 0.0
        self.integration = False      # True: Zustände gehen als Events an die Ladecockpit-Integration
        self._checked_at: float | None = None

    async def _check_integration(self, now: float) -> None:
        if self._checked_at is not None and now - self._checked_at < INTEGRATION_CHECK_S:
            return
        components = await self.ha.components()
        self._checked_at = now
        if components is None:
            return
        loaded = INTEGRATION in components
        if loaded != self.integration:
            log.info("Ladecockpit integration %s – entities now go %s", "found" if loaded else "gone",
                     "to it as events" if loaded else "to the states API")
            self.integration = loaded
            self._sent.clear()   # alles einmal auf dem neuen Weg senden
            self._last_full = 0.0

    async def run_forever(self) -> None:
        await asyncio.sleep(15)  # let the watcher read Home Assistant first
        while True:
            try:
                await self.publish_once()
            except Exception:  # noqa: BLE001 – keep going
                log.exception("Writing entities to Home Assistant failed")
            await asyncio.sleep(PUBLISH_EVERY_S)

    async def publish_once(self, now: float | None = None) -> int:
        """Geänderte Entitäten schreiben (alle alle REWRITE_ALL_S). Gibt zurück, wie viele geschrieben wurden."""
        now = time.time() if now is None else now
        d = await self.build()
        if not (d.get("setup") or {}).get("ha_ok", True):
            self._sent.clear()  # HA nicht erreichbar – alles neu schreiben, sobald es zurück ist
            self._checked_at = None
            return 0
        await self._check_integration(now)
        rewrite = now - self._last_full >= (EVENT_REWRITE_ALL_S if self.integration else REWRITE_ALL_S)
        written = 0
        for entity_id, (state, attributes) in build_states(d, self.s.lang).items():
            fingerprint = json.dumps([state, attributes], sort_keys=True, default=str)
            if not rewrite and self._sent.get(entity_id) == fingerprint:
                continue
            if self.integration:
                ok = await self.ha.fire_event(STATE_EVENT, {"entity_id": entity_id, "state": state,
                                                            "attributes": attributes})
            else:
                ok = await self.ha.set_state(entity_id, state, attributes)
            if ok:
                self._sent[entity_id] = fingerprint
                written += 1
            else:
                self._sent.pop(entity_id, None)
        if rewrite:
            self._last_full = now
        if written:
            log.debug("Wrote %d entities to Home Assistant", written)
        return written

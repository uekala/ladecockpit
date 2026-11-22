"""Abgleich mit Tesla und Weitergabe neuer Rechnungen an Home Assistant.

Takt:
  * normalerweise alle SYNC_INTERVAL_H Stunden (Standard 6 h)
  * nach dem Ende einer Ladung (vom Watcher erkannt oder POST /api/sync)
    alle BURST_INTERVAL_MIN Minuten, bis die neue Rechnung auftaucht –
    höchstens BURST_DURATION_MIN lang.
So bleibt es bei einigen Dutzend Tesla-Anfragen im Monat.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from . import i18n, invoices, networks, osm, stations, vehicle
from .config import Settings
from .db import DB, utcnow_iso
from .homeassistant import HAClient
from .push import Ntfy, mark_sent, pending
from .tesla import BudgetExceeded, NotConnected, RateLimited, TeslaClient, parse_session

log = logging.getLogger("ladecockpit.sync")

BURST_START_DELAY_S = 5
PROBLEM_ID = "ladecockpit_problem"
FAILURES_BEFORE_ALERT = 3
# Je Abgleich auf das Netz hin gelesene Rechnungen und wie weit zurück (jede ist eine Tesla-Anfrage, einmalig).
CHECK_PER_SYNC = 25
CHECK_DAYS = 120


class SyncService:
    def __init__(self, settings: Settings, db: DB, tesla: TeslaClient, ha: HAClient, push: Ntfy | None = None):
        self.s = settings
        self.db = db
        self.tesla = tesla
        self.ha = ha
        self.push = push
        self._wake = asyncio.Event()
        self._busy = asyncio.Lock()
        self.burst_until = 0.0
        self.last_sync: str | None = db.kv_get("last_sync")
        self.last_error: str | None = None
        self.next_sync: str | None = None
        self.failures = 0
        self.register = stations.Register(settings.data_dir)
        self.map = osm.Lookup()

    # --- control -------------------------------------------------------------
    def trigger_burst(self) -> None:
        self.burst_until = time.time() + self.s.burst_duration_min * 60
        # Kurze Pause, damit eine HA-Automation, die uns aufgerufen hat, schon auf das Event wartet.
        asyncio.get_running_loop().call_later(BURST_START_DELAY_S, self._wake.set)

    def wake(self) -> None:
        self._wake.set()

    @property
    def bursting(self) -> bool:
        return time.time() < self.burst_until

    async def run_forever(self) -> None:
        while True:
            await self.tick()
            wait_s = self.s.burst_interval_min * 60 if self.bursting else self.s.sync_interval_h * 3600
            if self.failures and not self.bursting:
                wait_s = min(wait_s, 1800)  # nach einem Fehler früher erneut versuchen
            self.next_sync = datetime.fromtimestamp(time.time() + wait_s, timezone.utc).isoformat(timespec="seconds")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=wait_s)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    async def tick(self) -> None:
        """Eine Runde: abgleichen, wenn möglich, und die Problem-Benachrichtigung aktuell halten."""
        if self.tesla.auth_error:
            await self.report("auth")
            return
        if not self.tesla.connected:
            return
        try:
            new = await self.sync_once()
        except NotConnected as e:
            self.last_error = str(e)
            return
        except BudgetExceeded as e:
            self.last_error = str(e)
            await self.report("budget")
            return
        except RateLimited as e:
            # Kein Fehler der Einrichtung: kein Traceback, zählt aber wie jeder andere fehlgeschlagene Abgleich.
            log.warning("Sync paused: %s", e)
            self.last_error = str(e)
            self.failures += 1
            if self.failures >= FAILURES_BEFORE_ALERT:
                await self.report("sync", str(e))
            return
        except Exception as e:  # noqa: BLE001 – keep the service running
            log.exception("Sync failed")
            self.last_error = str(e)
            self.failures += 1
            if self.tesla.auth_error:
                await self.report("auth")
            elif self.failures >= FAILURES_BEFORE_ALERT:
                await self.report("sync", str(e))
            return
        self.failures = 0
        await self.report(None)
        if new and self.bursting:
            self.burst_until = 0.0  # Rechnung da – zurück zum normalen Takt

    async def report(self, kind: str | None, detail: str = "") -> None:
        """Die Problem-Benachrichtigung in Home Assistant setzen oder entfernen (einmal je Problem gezeigt)."""
        current = self.db.kv_get("problem_kind")
        if kind == current:
            return
        enabled = self.ha.configured and self.s.notify_problems
        to_phone = self.push is not None and self.push.configured and self.s.notify_problems
        if kind is None:
            self.db.kv_del("problem_kind")
            if enabled:
                await self.ha.call_service("persistent_notification", "dismiss", {"notification_id": PROBLEM_ID})
            if to_phone:
                await self.push.send(i18n.t(self.s.lang, "problem_title"), i18n.t(self.s.lang, "problem_solved"),
                                     tags=["white_check_mark"])
            return
        self.db.kv_set("problem_kind", kind)
        message = i18n.t(self.s.lang, f"problem_{kind}", detail=detail[:200])
        if to_phone:
            await self.push.send(i18n.t(self.s.lang, "problem_title"), message, tags=["warning"], priority=4)
        if not enabled:
            return
        await self.ha.call_service("persistent_notification", "create", {
            "notification_id": PROBLEM_ID, "title": i18n.t(self.s.lang, "problem_title"), "message": message,
        })
        await self.ha.fire_event("ladecockpit_problem", {"kind": kind, "message": message})

    # --- sync -------------------------------------------------------------------
    async def sync_once(self) -> int:
        """Historie holen, speichern, neue Rechnungen an HA senden. Gibt die Zahl neuer Ladungen zurück."""
        async with self._busy:
            push_since = self.db.kv_get("push_since")
            if not push_since:
                # Erster Abgleich: Alles bis jetzt wird nur importiert, nie an HA gesendet,
                # damit Summen, die der Nutzer schon in HA führt, nicht doppelt zählen.
                push_since = utcnow_iso()
                self.db.kv_set("push_since", push_since)

            latest = self.db.latest_start()
            start = datetime.fromisoformat(latest) - timedelta(days=3) if latest else None

            new_count = 0
            for raw in await self.tesla.charging_history(start):
                session = parse_session(raw)
                if not session:
                    continue
                backfill = bool(session["start_ts"] and session["start_ts"] < push_since)
                if self.db.upsert_session(session, "backfill" if backfill else "new"):
                    new_count += 1
                    self._log_format(raw, session["session_id"])

            await self.check_invoices()
            await self.push_pending()
            await self.push_phone()
            self.last_sync = utcnow_iso()
            self.db.kv_set("last_sync", self.last_sync)
            self.last_error = None
            return new_count

    async def check_invoices(self, now: datetime | None = None) -> int:
        """Bevor Ladungen an Home Assistant gehen: ihr Netz aus der Rechnung, und bei MultiPass-Ladungen
        die Adresse der Station aus der Rechnung und ihr Betreiber aus dem Register.

        Die Rechnungsnummer im Dateinamen verrät das Netz meist schon („P“ Supercharger, „MSP“
        MultiPass); nur wenn nicht, wird das PDF geholt. MultiPass-Rechnungen werden für die Adresse
        der Station geholt. PDFs bleiben gespeichert, Ansicht und Monatsbericht brauchen also keine
        weitere Anfrage. Gibt die Zahl gelesener Rechnungen zurück."""
        now = now or datetime.now(timezone.utc)
        since = (now - timedelta(days=CHECK_DAYS)).isoformat(timespec="seconds")
        read = 0
        for s in self.db.sessions_to_check(since, CHECK_PER_SYNC * 4):
            if (s.get("network_reason") or "").startswith("invoice "):
                self.db.set_invoice_network(s["session_id"], s["network"])  # vom Dateinamen verraten
                continue
            if read >= CHECK_PER_SYNC:
                break
            text = await self._invoice_text(s)
            if text is None:
                break
            read += 1
            network = invoices.network_from_text(text)
            self.db.set_invoice_network(s["session_id"], network)
            if network == networks.MULTIPASS and s.get("network") != networks.MULTIPASS:
                log.info("Session %s is a MultiPass session (invoice number)", s["session_id"])
        for s in self.db.sessions_without_station(since, CHECK_PER_SYNC * 4):
            if s.get("network") != networks.MULTIPASS:
                self.db.set_station(s["session_id"], {})  # Supercharger: Der Standortname sagt alles
                continue
            if read >= CHECK_PER_SYNC:
                break
            text = await self._invoice_text(s)
            if text is None:
                break
            read += 1
            self.db.set_station(s["session_id"], stations.station_from_text(text) or {})
        await self.lookup_operators(now)
        await self.lookup_on_map(now)
        return read

    async def _invoice_text(self, s: dict) -> str | None:
        try:
            path = await invoices.pdf_path(self.tesla, self.s.data_dir, s)
        except Exception as e:  # noqa: BLE001 – beim nächsten Abgleich erneut versuchen
            log.warning("Could not fetch the invoice of session %s: %s", s["session_id"], e)
            return None
        return invoices.pdf_text(path.read_bytes())

    async def lookup_operators(self, now: datetime | None = None) -> int:
        """Betreiber deutscher MultiPass-Stationen aus dem Register der Bundesnetzagentur.
        Gibt die Zahl gefundener Stationen zurück."""
        if not self.s.operator_lookup:
            return 0
        now = now or datetime.now(timezone.utc)
        due = [s for s in self.db.sessions_with_station() if stations.due_for_lookup(s["station"], now)]
        if not due:
            return 0
        try:
            rows = await self.register.rows_for({s["station"]["postcode"] for s in due})
        except Exception:  # noqa: BLE001 – der Betreiber ist eine Zugabe, nie deswegen einen Abgleich abbrechen
            log.exception("Charging station register lookup failed")
            return 0
        if rows is None:
            return 0
        found = 0
        for s in due:
            station = dict(s["station"])
            hit = stations.match_operator(station, rows)
            station["checked"] = now.isoformat(timespec="seconds")
            station["match_v"] = stations.MATCH_VERSION
            for k in ("operator", "operator_shown", "operator_src", "map_checked", "map_v"):
                station.pop(k, None)
            if hit:
                station["operator"] = hit["operator"]
                if hit.get("shown"):
                    station["operator_shown"] = hit["shown"]
                found += 1
            self.db.set_station(s["session_id"], station)
        log.info("Operators found in the register for %d of %d MultiPass sessions", found, len(due))
        return found

    async def lookup_on_map(self, now: datetime | None = None) -> int:
        """Betreiber von MultiPass-Stationen, die das Register nicht hat (alle Stationen außerhalb
        Deutschlands), aus OpenStreetMap. Jede Adresse wird einmal gefragt und die Antwort für alle
        ihre Ladungen genutzt. Gibt die Zahl der Ladungen zurück, die einen Betreiber bekamen."""
        if not self.s.map_lookup:
            return 0
        now = now or datetime.now(timezone.utc)
        answered: dict[tuple, dict] = {}
        waiting: dict[tuple, list[dict]] = {}
        for s in self.db.sessions_with_station():
            station = s["station"]
            if osm.due(station, now, register_first=self.s.operator_lookup):
                waiting.setdefault(osm.key(station), []).append(s)
            elif station.get("map_v") == osm.VERSION and station.get("map_checked"):
                answered[osm.key(station)] = station
        if not waiting:
            return 0
        found = asked = 0
        for address, sessions in waiting.items():
            known = answered.get(address)
            if known:
                result = {k: known[k] for k in ("operator", "operator_src", "map_checked", "map_v") if k in known}
            else:
                if asked >= osm.PER_SYNC:
                    continue
                if asked:
                    await asyncio.sleep(self.map.pause_s)
                asked += 1
                try:
                    hit = await self.map.operator(sessions[0]["station"])
                except osm.Unavailable as e:
                    log.warning("OpenStreetMap lookup not available now (%s); trying again with the next sync", e)
                    break
                except Exception:  # noqa: BLE001 – der Betreiber ist eine Zugabe, nie deswegen einen Abgleich abbrechen
                    log.exception("OpenStreetMap lookup failed")
                    break
                result = {"map_checked": now.isoformat(timespec="seconds"), "map_v": osm.VERSION}
                if hit:
                    result.update(operator=hit["operator"], operator_src="osm")
                # Sagen, welche Station und warum, damit ein Fehlschlag nachvollziehbar ist (nur Ort, keine Straße).
                town = sessions[0]["station"].get("city") or sessions[0]["station"].get("postcode") or "?"
                log.info("OpenStreetMap, station in %s: %s", town,
                         getattr(self.map, "why", "") or ("operator found" if hit else "no operator"))
            for s in sessions:
                self.db.set_station(s["session_id"], {**s["station"], **result})
                found += 1 if result.get("operator") else 0
        if asked:
            log.info("OpenStreetMap asked about %d stations, operator found for %d sessions", asked, found)
        return found

    @staticmethod
    def _log_format(raw: dict, session_id: str) -> None:
        """Festhalten, was Tesla für Ladungen geschickt hat, die keine einfachen Supercharger-Datensätze sind
        (keine persönlichen Daten: nur Feldnamen und die zutreffende Regel)."""
        network, reason = networks.classify(raw)
        if network != networks.SUPERCHARGER:
            log.info("Session %s looks like %s (%s)", session_id, network, reason)
        extra = networks.unknown_keys(raw)
        if extra:
            log.info("Session %s has fields Ladecockpit does not know yet: %s", session_id, ", ".join(extra))

    async def push_pending(self) -> int:
        if not self.ha.configured:
            return 0
        pushed = 0
        max_age = timedelta(hours=self.s.push_max_age_h)
        now = datetime.now(timezone.utc)
        for s in self.db.sessions_to_push():
            if s["kwh"] is None or s["total"] is None:
                continue  # Abrechnung noch nicht endgültig – beim nächsten Abgleich erneut
            started = datetime.fromisoformat(s["start_ts"]) if s["start_ts"] else now
            if now - started > max_age:
                self.db.set_push_state(s["session_id"], "stale")
                continue
            if await self.ha.fire_event(self.s.ha_event, self.event_payload(s)):
                self.db.set_push_state(s["session_id"], "pushed")
                pushed += 1
        return pushed

    async def push_phone(self) -> int:
        """Neue Rechnungen über ntfy aufs Handy (unabhängig von Home Assistant)."""
        if not (self.push and self.push.configured):
            return 0
        sent = 0
        now = datetime.now(timezone.utc)
        for s in pending(self.db, self.db.sessions(), now, timedelta(hours=self.s.push_max_age_h)):
            p = self.event_payload(s)
            title = i18n.t(self.s.lang, "push_invoice_title", site=p["site"])
            tags = ["zap", "turtle"] if p["slow"] else ["zap"]
            if await self.push.send(title, p["text"], tags=tags):
                mark_sent(self.db, s["session_id"])
                sent += 1
            else:
                break  # ntfy nicht erreichbar: Der Rest wartet auf den nächsten Abgleich
        return sent

    def event_payload(self, s: dict) -> dict:
        tz, lang = self.s.tz, self.s.lang
        start = datetime.fromisoformat(s["start_ts"]).astimezone(tz) if s["start_ts"] else None
        end_raw = s.get("unlatch_ts") or s.get("stop_ts")
        end = datetime.fromisoformat(end_raw).astimezone(tz) if end_raw else None
        price = s["price"] or 0.0
        cur = s["currency"]
        when = (start.strftime("%d.%m. %H:%M") if lang == "de" else start.strftime("%b %d, %H:%M")) if start else "–"
        network = s.get("network") or networks.SUPERCHARGER
        text = (f"{i18n.num(lang, s['kwh'], 1)} kWh · {i18n.money(lang, s['total'], cur)} · "
                f"{i18n.money(lang, price, cur)}/kWh · {when}")
        operator = addr = None
        if network == networks.MULTIPASS:
            others = self.db.sessions()
            mine = next((x for x in others if x["session_id"] == s["session_id"]), dict(s))
            stations.describe([mine, *[x for x in others if x["session_id"] != s["session_id"]]])
            operator, addr = mine.get("_operator"), mine.get("_address")
            text = f"MultiPass · {operator} · {text}" if operator else "MultiPass · " + text
        speed = self._speed(s)
        return {
            "session_id": s["session_id"],
            "site": s["site"] or i18n.t(lang, "unknown_site"),
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "kwh": round(s["kwh"], 2),
            "charge_cost": round(s["charge_cost"] or 0.0, 2),
            "idle_fee": round(s["idle_fee"] or 0.0, 2),
            "total": round(s["total"], 2),
            "price_per_kwh": round(price, 4),
            "list_price_per_kwh": round(s["list_price"], 4) if s.get("list_price") is not None else round(price, 4),
            "credit": round(s.get("credit") or 0.0, 2),
            "currency": cur,
            "network": network,
            "operator": operator,
            "address": addr,
            "avg_power_kw": speed.get("kw"),
            "typical_power_kw": speed.get("typical_kw"),
            "slow": bool(speed.get("slow")),
            "text": text[:255],
        }

    def _speed(self, s: dict) -> dict:
        """Mittlere Leistung der Ladung gegenüber der üblichen am Standort (siehe vehicle.charging_speed)."""
        if not s.get("start_ts"):
            return {}
        since = datetime.fromisoformat(s["start_ts"]) - timedelta(days=400)
        sessions = [x for x in self.db.sessions() if x.get("kwh") and x.get("start_ts")]
        return vehicle.charging_speed(sessions, self.db.readings_since("soc", since)).get(s["session_id"], {})

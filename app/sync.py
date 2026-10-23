"""Sync with Tesla and hand new invoices to Home Assistant.

Rhythm:
  * normally every SYNC_INTERVAL_H hours (default 6 h)
  * after a charging session ends (detected by the watcher, or POST /api/sync)
    every BURST_INTERVAL_MIN minutes until the new invoice shows up –
    for at most BURST_DURATION_MIN.
That keeps it at a few dozen Tesla requests per month.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from . import i18n, networks
from .config import Settings
from .db import DB, utcnow_iso
from .homeassistant import HAClient
from .tesla import BudgetExceeded, NotConnected, TeslaClient, parse_session

log = logging.getLogger("ladecockpit.sync")

BURST_START_DELAY_S = 5
PROBLEM_ID = "ladecockpit_problem"
FAILURES_BEFORE_ALERT = 3


class SyncService:
    def __init__(self, settings: Settings, db: DB, tesla: TeslaClient, ha: HAClient):
        self.s = settings
        self.db = db
        self.tesla = tesla
        self.ha = ha
        self._wake = asyncio.Event()
        self._busy = asyncio.Lock()
        self.burst_until = 0.0
        self.last_sync: str | None = db.kv_get("last_sync")
        self.last_error: str | None = None
        self.next_sync: str | None = None
        self.failures = 0

    # --- control -------------------------------------------------------------
    def trigger_burst(self) -> None:
        self.burst_until = time.time() + self.s.burst_duration_min * 60
        # Short delay so an HA automation that called us is already listening for the event.
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
                wait_s = min(wait_s, 1800)  # retry sooner after an error
            self.next_sync = datetime.fromtimestamp(time.time() + wait_s, timezone.utc).isoformat(timespec="seconds")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=wait_s)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    async def tick(self) -> None:
        """One round: sync if possible and keep the problem notification up to date."""
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
            self.burst_until = 0.0  # invoice arrived – back to the normal rhythm

    async def report(self, kind: str | None, detail: str = "") -> None:
        """Raise or clear the problem notification in Home Assistant (shown once per problem)."""
        current = self.db.kv_get("problem_kind")
        if kind == current:
            return
        enabled = self.ha.configured and self.s.notify_problems
        if kind is None:
            self.db.kv_del("problem_kind")
            if enabled:
                await self.ha.call_service("persistent_notification", "dismiss", {"notification_id": PROBLEM_ID})
            return
        self.db.kv_set("problem_kind", kind)
        if not enabled:
            return
        message = i18n.t(self.s.lang, f"problem_{kind}", detail=detail[:200])
        await self.ha.call_service("persistent_notification", "create", {
            "notification_id": PROBLEM_ID, "title": i18n.t(self.s.lang, "problem_title"), "message": message,
        })
        await self.ha.fire_event("ladecockpit_problem", {"kind": kind, "message": message})

    # --- sync -------------------------------------------------------------------
    async def sync_once(self) -> int:
        """Fetch history, store it, send new invoices to HA. Returns number of new sessions."""
        async with self._busy:
            push_since = self.db.kv_get("push_since")
            if not push_since:
                # First sync: everything up to now is only imported, never sent to HA,
                # so totals the user already keeps in HA are not counted twice.
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

            await self.push_pending()
            self.last_sync = utcnow_iso()
            self.db.kv_set("last_sync", self.last_sync)
            self.last_error = None
            return new_count

    @staticmethod
    def _log_format(raw: dict, session_id: str) -> None:
        """Note what Tesla sent for sessions that are not plain Supercharger records
        (no personal data: field names and the rule that matched only)."""
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
                continue  # billing not final yet – try again next sync
            started = datetime.fromisoformat(s["start_ts"]) if s["start_ts"] else now
            if now - started > max_age:
                self.db.set_push_state(s["session_id"], "stale")
                continue
            if await self.ha.fire_event(self.s.ha_event, self.event_payload(s)):
                self.db.set_push_state(s["session_id"], "pushed")
                pushed += 1
        return pushed

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
        if network == networks.MULTIPASS:
            text = "MultiPass · " + text
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
            "text": text[:255],
        }

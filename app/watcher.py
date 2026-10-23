"""Polls Home Assistant (local, free) for battery, range, odometer and charging state.

* Stores readings so Ladecockpit has its own history – the last known battery level
  survives when the car is offline (e.g. in an underground garage), and monthly
  distance works without any helper in HA.
* Detects the end of a charging session and starts a short burst of Tesla syncs,
  so the invoice is picked up within minutes. No automation in HA needed for that.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from .config import Settings
from .db import DB
from .homeassistant import INVALID_STATES, HAClient
from .sync import SyncService

log = logging.getLogger("ladecockpit.watcher")

# Store a new reading when the value moved at least this much, or an hour passed.
MIN_DELTA = {"soc": 1.0, "range": 2.0, "odometer": 0.5}
MAX_AGE = timedelta(hours=1)
KEEP_DAYS = 400


class Watcher:
    def __init__(self, settings: Settings, db: DB, ha: HAClient, sync: SyncService):
        self.s = settings
        self.db = db
        self.ha = ha
        self.sync = sync
        self.latest: dict | None = None
        self._last_prune: datetime | None = None

    async def run_forever(self) -> None:
        while True:
            try:
                await self.poll_once()
            except Exception:  # noqa: BLE001 – keep polling
                log.exception("Polling Home Assistant failed")
            await asyncio.sleep(self.s.ha_poll_seconds)

    async def poll_once(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        live = await self.ha.live()
        self.latest = live
        values = live.get("values", {})

        for key in ("soc", "range", "odometer"):
            value = values.get(key)
            if value is None:
                continue
            last = self.db.last_reading(key)
            if last is None or abs(last[1] - value) >= MIN_DELTA[key] or now - last[0] >= MAX_AGE:
                self.db.add_reading(key, value, now)

        self._check_charging(live.get("raw", {}).get("charging"))

        if self._last_prune is None or now - self._last_prune > timedelta(days=1):
            self.db.prune_readings(now - timedelta(days=KEEP_DAYS))
            self._last_prune = now
        return live

    def _check_charging(self, state: str | None) -> None:
        if not state or state.lower() in INVALID_STATES:
            return  # car offline: keep the last valid state, compare when it is back
        previous = self.db.kv_get("last_charging_state")
        charging = self.s.charging_value.lower()
        if previous is not None and previous.lower() == charging and state.lower() != charging:
            log.info("Charging ended (%s → %s) – looking for the invoice", previous, state)
            self.sync.trigger_burst()
        if state != previous:
            self.db.kv_set("last_charging_state", state)

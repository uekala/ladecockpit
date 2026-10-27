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
MIN_DELTA = {"soc": 1.0, "range": 2.0, "odometer": 0.5, "temp": 0.5, "fuel_cost": 0.01, "fuel_litres": 0.01}
ROLE = {"soc": "soc", "range": "range", "odometer": "odometer", "temp": "outside_temp",
        "fuel_cost": "fuel_cost_total", "fuel_litres": "fuel_litres_total"}
MAX_AGE = timedelta(hours=1)
# The fuel totals only move when you fill up: one reading a day is plenty.
MAX_AGE_FOR = {"fuel_cost": timedelta(days=1), "fuel_litres": timedelta(days=1)}
HOME_MIN_STEP_KWH = 0.05
HOME_MAX_STEP_KWH = 100.0
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
        try:
            await self.seed_from_history()
        except Exception:  # noqa: BLE001
            log.exception("Could not read history from Home Assistant")
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

        for key in ("soc", "range", "odometer", "temp", "fuel_cost", "fuel_litres"):
            value = values.get(ROLE[key])
            if value is None:
                continue
            last = self.db.last_reading(key)
            max_age = MAX_AGE_FOR.get(key, MAX_AGE)
            if last is None or abs(last[1] - value) >= MIN_DELTA[key] or now - last[0] >= max_age:
                self.db.add_reading(key, value, now)

        self._check_charging(live.get("raw", {}).get("charging"))
        self._track_home(values, live.get("units", {}), now)

        if self._last_prune is None or now - self._last_prune > timedelta(days=1):
            self.db.prune_readings(now - timedelta(days=KEEP_DAYS))
            self._last_prune = now
        return live

    async def seed_from_history(self, now: datetime | None = None) -> int:
        """Fresh install: take the last days from HA's own history, so the battery level,
        the forecast and the distance show up right away instead of after the car was online."""
        now = now or datetime.now(timezone.utc)
        roles = self.ha.entities()
        added = 0
        for key in ("soc", "range", "odometer", "temp"):
            entity = roles.get(ROLE[key])
            if not entity or entity.startswith("weather.") or self.db.last_reading(key) is not None:
                continue
            kept: list[tuple[datetime, float]] = []
            for ts, value in await self.ha.history(entity, now - timedelta(days=10)):
                if not kept or abs(kept[-1][1] - value) >= MIN_DELTA[key] or ts - kept[-1][0] >= MAX_AGE:
                    kept.append((ts, value))
            for ts, value in kept:
                self.db.add_reading(key, value, ts)
            added += len(kept)
            if kept:
                log.info("Took %d %s values from the Home Assistant history", len(kept), key)
        return added

    def _track_home(self, values: dict, units: dict, now: datetime) -> None:
        """Charging at home: store what the wallbox meter added since the last poll, with the
        electricity price of that moment (so dynamic tariffs are priced correctly)."""
        meter = values.get("home_energy")
        if meter is None:
            return
        unit = (units.get("home_energy") or "kWh").lower()
        meter *= {"wh": 0.001, "mwh": 1000.0}.get(unit, 1.0)
        last = self.db.kv_get("home_meter")
        if last is None:
            self.db.kv_set("home_meter", str(meter))
            return
        delta = meter - float(last)
        if delta < 0 or delta > HOME_MAX_STEP_KWH:
            self.db.kv_set("home_meter", str(meter))  # meter replaced or reset: start again from here
            return
        if delta < HOME_MIN_STEP_KWH:
            return  # keep the old mark, small steps add up
        self.db.kv_set("home_meter", str(meter))
        self.db.add_reading("home_kwh", delta, now)
        price = values.get("home_price") or self.s.home_price
        if price is not None:
            self.db.add_reading("home_cost", delta * price, now)

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

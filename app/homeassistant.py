"""Home Assistant via its REST API: read states, read history, fire events."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from .config import Settings

log = logging.getLogger("ladecockpit.ha")

INVALID_STATES = ("unknown", "unavailable", "none", "")


def as_float(value) -> float | None:
    if value is None or str(value).lower() in INVALID_STATES:
        return None
    try:
        f = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # drop NaN


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class HAClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.s = settings
        self.last_error: str | None = None
        self._http = (
            httpx.AsyncClient(
                base_url=settings.ha_url,
                headers={"Authorization": f"Bearer {settings.ha_token}"},
                timeout=15,
                transport=transport,
            )
            if settings.ha_configured
            else None
        )

    @property
    def configured(self) -> bool:
        return self._http is not None

    def entities(self) -> dict[str, str]:
        """Configured entities by role (empty ones left out)."""
        s = self.s
        roles = {
            "soc": s.ent_soc, "range": s.ent_range, "odometer": s.ent_odometer,
            "charging": s.ent_charging, "cost_total": s.ent_cost_total, "kwh_total": s.ent_kwh_total,
            "reference_price": s.ent_reference_price, "fuel_month": s.ent_fuel_month,
        }
        return {k: v for k, v in roles.items() if v}

    async def state(self, entity_id: str) -> dict | None:
        if not self._http or not entity_id:
            return None
        try:
            r = await self._http.get(f"/api/states/{entity_id}")
        except httpx.HTTPError as e:
            self.last_error = f"Home Assistant not reachable ({e.__class__.__name__})"
            return None
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            self.last_error = f"Home Assistant answered HTTP {r.status_code}"
            return None
        return r.json()

    async def live(self) -> dict:
        """Current values of all configured entities."""
        roles = self.entities()
        if not self.configured or not roles:
            return {"available": False, "error": None, "missing": [], "values": {}, "raw": {}, "units": {}}
        self.last_error = None
        results = await asyncio.gather(*(self.state(eid) for eid in roles.values()))
        values, raw, units, missing = {}, {}, {}, []
        for (role, eid), item in zip(roles.items(), results):
            if not item:
                missing.append(eid)
                continue
            raw[role] = str(item.get("state", ""))
            values[role] = as_float(item.get("state"))
            unit = (item.get("attributes") or {}).get("unit_of_measurement")
            if unit:
                units[role] = unit
        reachable = self.last_error is None
        return {"available": reachable, "error": self.last_error,
                "missing": missing if reachable else [], "values": values, "raw": raw, "units": units}

    async def history(self, entity_id: str, start: datetime) -> list[tuple[datetime, float]]:
        """Numeric history of one entity since start (HA keeps ~10 days by default)."""
        if not self._http or not entity_id:
            return []
        ts = quote(start.astimezone(timezone.utc).isoformat(timespec="seconds"), safe="")
        try:
            r = await self._http.get(
                f"/api/history/period/{ts}",
                params={"filter_entity_id": entity_id, "minimal_response": "", "no_attributes": ""},
            )
        except httpx.HTTPError:
            return []
        if r.status_code >= 400:
            return []
        points: list[tuple[datetime, float]] = []
        for series in r.json() or []:
            for row in series:
                val = as_float(row.get("state"))
                dt = parse_dt(row.get("last_changed") or row.get("last_updated"))
                if val is not None and dt is not None:
                    points.append((dt, val))
        points.sort(key=lambda p: p[0])
        return points

    async def fire_event(self, event_type: str, data: dict) -> bool:
        if not self._http:
            return False
        try:
            r = await self._http.post(f"/api/events/{event_type}", json=data)
        except httpx.HTTPError as e:
            self.last_error = f"Could not send event to Home Assistant ({e.__class__.__name__})"
            return False
        if r.status_code >= 400:
            self.last_error = f"Home Assistant rejected the event (HTTP {r.status_code})"
            return False
        return True

    async def call_service(self, domain: str, service: str, data: dict) -> bool:
        if not self._http:
            return False
        try:
            r = await self._http.post(f"/api/services/{domain}/{service}", json=data)
        except httpx.HTTPError:
            return False
        return r.status_code < 400

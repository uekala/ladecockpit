"""Ladecockpit: real entities for the Ladecockpit app.

The app (Home Assistant app or Docker container) works out everything from the Tesla
invoices and fires one `ladecockpit_state` event per entity. This integration turns those
events into entities with a unique ID and a device, so they can be renamed, assigned to an
area and are restored after a restart. Without it, the app writes plain states instead.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import BINARY_SENSORS, DOMAIN, SENSORS, STATE_EVENT, signal

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
KNOWN = {Platform.SENSOR.value: set(SENSORS), Platform.BINARY_SENSOR.value: set(BINARY_SENSORS)}


def parse_entity_id(entity_id: object) -> tuple[str, str] | None:
    """`sensor.ladecockpit_month_cost` → ("sensor", "month_cost"), for the entities we know."""
    if not isinstance(entity_id, str) or "." not in entity_id:
        return None
    platform, obj = entity_id.split(".", 1)
    prefix = DOMAIN + "_"
    if not obj.startswith(prefix):
        return None
    key = obj[len(prefix):]
    return (platform, key) if key in KNOWN.get(platform, ()) else None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unknown: set[str] = set()

    @callback
    def on_state(event: Event) -> None:
        data = event.data
        target = parse_entity_id(data.get("entity_id"))
        if target is None:
            if data.get("entity_id") not in unknown:
                unknown.add(data.get("entity_id"))
                _LOGGER.debug("Ignoring %s – not an entity of this version", data.get("entity_id"))
            return
        attributes = data.get("attributes")
        async_dispatcher_send(hass, signal(*target), data.get("state"),
                              attributes if isinstance(attributes, dict) else {})

    entry.async_on_unload(hass.bus.async_listen(STATE_EVENT, on_state))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

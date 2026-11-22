"""Gemeinsame Basis der Ladecockpit-Entitäten."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, OWN_ATTRIBUTES, object_id, signal


def claim_entity_ids(hass: HomeAssistant, entry: ConfigEntry, platform: str,
                     keys: tuple[str, ...]) -> dict[str, State | None]:
    """`<platform>.ladecockpit_<key>` für diese Integration registrieren und den Zustand zurückgeben,
    den die App dort vorher geschrieben hat, falls vorhanden.

    Ohne die Integration schreibt die App unter diesen IDs einfache Zustände. Ihr Zustand wird
    übernommen und im selben Schritt entfernt, in dem der Registereintrag entsteht, sodass die Entität
    ihre ID behält (kein `_2`) und Dashboards und Automationen weiter funktionieren.
    """
    registry = er.async_get(hass)
    taken_over: dict[str, State | None] = {}
    for key in keys:
        unique_id = object_id(key)
        if registry.async_get_entity_id(platform, DOMAIN, unique_id):
            taken_over[key] = None
            continue
        entity_id = f"{platform}.{object_id(key)}"
        old = hass.states.get(entity_id)
        if old is not None and registry.async_get(entity_id) is None:
            hass.states.async_remove(entity_id)
        else:
            old = None
        registry.async_get_or_create(platform, DOMAIN, unique_id, suggested_object_id=object_id(key),
                                     config_entry=entry)
        taken_over[key] = old
    return taken_over


class LadecockpitEntity(RestoreEntity):
    """Eine Entität, deren Zustand und Attribute die App sendet (siehe const.STATE_EVENT)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _platform_name: str = ""

    def __init__(self, entry: ConfigEntry, key: str, initial: State | None = None) -> None:
        self._key = key
        self._attr_unique_id = object_id(key)
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="Ladecockpit", manufacturer="Ladecockpit",
            model="Tesla Supercharger invoices", entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://github.com/uekala/ladecockpit",
        )
        self._raw: str | None = None
        self._attrs: dict[str, Any] = {}
        self._own: dict[str, Any] = {}
        self._initial = initial

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = self._initial or await self.async_get_last_state()
        self._initial = None
        if last is not None and last.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._apply(last.state, dict(last.attributes))
        self.async_on_remove(async_dispatcher_connect(
            self.hass, signal(self._platform_name, self._key), self._on_update))

    @callback
    def _on_update(self, state: Any, attributes: dict[str, Any]) -> None:
        self._apply(state, attributes)
        self.async_write_ha_state()

    def _apply(self, state: Any, attributes: dict[str, Any]) -> None:
        self._raw = None if state is None else str(state)
        self._own = {k: attributes.get(k) for k in OWN_ATTRIBUTES}
        self._attrs = {k: v for k, v in attributes.items() if k not in OWN_ATTRIBUTES}
        self._attr_icon = self._own.get("icon")
        self._attr_entity_picture = self._own.get("entity_picture")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._attrs

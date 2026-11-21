"""Ladecockpit problem sensor: on when the Tesla sign-in expired, syncing fails or an entity is missing."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BINARY_SENSORS
from .entity import LadecockpitEntity, claim_entity_ids


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    initial = claim_entity_ids(hass, entry, "binary_sensor", BINARY_SENSORS)
    async_add_entities(LadecockpitProblem(entry, key, initial.get(key)) for key in BINARY_SENSORS)


class LadecockpitProblem(LadecockpitEntity, BinarySensorEntity):
    _platform_name = "binary_sensor"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool | None:
        return {"on": True, "off": False}.get(self._raw or "")

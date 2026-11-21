"""Ladecockpit sensors: next charge, month cost and energy, last charge, price tip and more."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SENSORS
from .entity import LadecockpitEntity, claim_entity_ids


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    initial = claim_entity_ids(hass, entry, "sensor", SENSORS)
    async_add_entities(LadecockpitSensor(entry, key, initial.get(key)) for key in SENSORS)


def _enum(kind, value):
    try:
        return kind(value) if value else None
    except ValueError:
        return None


class LadecockpitSensor(LadecockpitEntity, SensorEntity):
    _platform_name = "sensor"

    @property
    def device_class(self) -> SensorDeviceClass | None:
        return _enum(SensorDeviceClass, self._own.get("device_class"))

    @property
    def state_class(self) -> SensorStateClass | None:
        return _enum(SensorStateClass, self._own.get("state_class"))

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._own.get("unit_of_measurement")

    @property
    def last_reset(self) -> datetime | None:
        value = self._own.get("last_reset")
        if self.state_class != SensorStateClass.TOTAL or not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    @property
    def native_value(self) -> str | Decimal | date | None:
        raw = self._raw
        if raw is None or raw in ("unknown", "unavailable", ""):
            return None
        if self.device_class == SensorDeviceClass.DATE:
            try:
                return date.fromisoformat(raw)
            except ValueError:
                return None
        if self.native_unit_of_measurement or self.state_class or self.device_class:
            # Decimal keeps the number as the app wrote it ("130.10", "74"), as before the integration.
            try:
                value = Decimal(raw)
            except InvalidOperation:
                return None
            return value if value.is_finite() else None
        return raw

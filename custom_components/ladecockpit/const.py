"""Constants of the Ladecockpit integration."""
from __future__ import annotations

DOMAIN = "ladecockpit"

# The Ladecockpit app fires one event per entity: {"entity_id", "state", "attributes"}
# (see app/entities.py, STATE_EVENT).
STATE_EVENT = "ladecockpit_state"

# The entities the app writes, by platform. Their entity IDs stay the ones the app used
# before the integration existed: <platform>.ladecockpit_<key>.
SENSORS = (
    "next_charge",
    "battery",
    "month_cost",
    "month_energy",
    "last_charge",
    "price_tip",
    "range_at_100",
    "consumption",
    "car",
    "multipass",
)
BINARY_SENSORS = ("problem",)

# Attributes that become entity properties instead of extra attributes.
OWN_ATTRIBUTES = frozenset({
    "friendly_name", "unit_of_measurement", "device_class", "state_class", "icon",
    "last_reset", "entity_picture",
})


def signal(platform: str, key: str) -> str:
    """Dispatcher signal for one entity."""
    return f"{DOMAIN}_{platform}_{key}"


def object_id(key: str) -> str:
    return f"{DOMAIN}_{key}"

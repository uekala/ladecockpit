"""Konstanten der Ladecockpit-Integration."""
from __future__ import annotations

DOMAIN = "ladecockpit"

# Die Ladecockpit-App löst je Entität ein Event aus: {"entity_id", "state", "attributes"}
# (siehe app/entities.py, STATE_EVENT).
STATE_EVENT = "ladecockpit_state"

# Die Entitäten, die die App schreibt, nach Plattform. Ihre Entitäts-IDs bleiben die, die die App
# vor der Integration nutzte: <platform>.ladecockpit_<key>.
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

# Attribute, die zu Eigenschaften der Entität werden statt zu zusätzlichen Attributen.
OWN_ATTRIBUTES = frozenset({
    "friendly_name", "unit_of_measurement", "device_class", "state_class", "icon",
    "last_reset", "entity_picture",
})


def signal(platform: str, key: str) -> str:
    """Dispatcher-Signal für eine Entität."""
    return f"{DOMAIN}_{platform}_{key}"


def object_id(key: str) -> str:
    return f"{DOMAIN}_{key}"

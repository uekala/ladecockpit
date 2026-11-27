"""Die Ladecockpit-Integration: übernimmt die Zustände der App, folgt ihren Events, stellt sich selbst wieder her."""
from datetime import date, datetime

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache

from custom_components.ladecockpit.const import BINARY_SENSORS, DOMAIN, SENSORS, STATE_EVENT

MONTH = {"unit_of_measurement": "EUR", "device_class": "monetary", "state_class": "total",
         "last_reset": "2026-11-01T00:00:00+01:00", "icon": "mdi:cash-multiple",
         "friendly_name": "Ladecockpit Ladekosten Monat", "sessions": 14, "energy_kwh": 315.3}


async def setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Ladecockpit", unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def send(hass: HomeAssistant, entity_id: str, state: str, attributes: dict) -> None:
    hass.bus.async_fire(STATE_EVENT, {"entity_id": entity_id, "state": state, "attributes": attributes})
    await hass.async_block_till_done()


async def test_config_flow_creates_one_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["title"] == "Ladecockpit"
    await hass.async_block_till_done()
    again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert again["type"] is FlowResultType.ABORT


async def test_takes_over_the_app_states_with_the_same_ids(hass: HomeAssistant):
    # Was die App über die States-API geschrieben hat, bevor es die Integration gab.
    hass.states.async_set("sensor.ladecockpit_month_cost", "122.24", MONTH)
    hass.states.async_set("binary_sensor.ladecockpit_problem", "off", {"device_class": "problem", "kind": None})
    entry = await setup(hass)

    registry = er.async_get(hass)
    for platform, keys in (("sensor", SENSORS), ("binary_sensor", BINARY_SENSORS)):
        for key in keys:
            entity_id = registry.async_get_entity_id(platform, DOMAIN, f"ladecockpit_{key}")
            assert entity_id == f"{platform}.ladecockpit_{key}"            # no "_2"
            assert registry.async_get(entity_id).config_entry_id == entry.entry_id

    cost = hass.states.get("sensor.ladecockpit_month_cost")
    assert cost.state == "122.24" and cost.attributes["sessions"] == 14
    assert cost.attributes["state_class"] == "total" and cost.attributes["unit_of_measurement"] == "EUR"
    assert cost.attributes["friendly_name"] == "Ladecockpit Charging cost this month"
    assert hass.states.get("binary_sensor.ladecockpit_problem").state == "off"
    assert hass.states.get("sensor.ladecockpit_battery").state == "unknown"   # nothing sent yet

    devices = [d for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
               if (DOMAIN, entry.entry_id) in d.identifiers]
    assert len(devices) == 1
    device = devices[0]
    assert device.name == "Ladecockpit"
    assert all(e.device_id == device.id for e in er.async_entries_for_config_entry(registry, entry.entry_id))


async def test_follows_the_events(hass: HomeAssistant):
    await setup(hass)
    await send(hass, "sensor.ladecockpit_month_cost", "130.10", {**MONTH, "sessions": 15})
    cost = hass.states.get("sensor.ladecockpit_month_cost")
    assert cost.state == "130.10" and cost.attributes["sessions"] == 15
    assert cost.attributes["last_reset"] == datetime.fromisoformat(MONTH["last_reset"]).isoformat()
    assert cost.attributes["icon"] == "mdi:cash-multiple"

    await send(hass, "sensor.ladecockpit_next_charge", "2026-11-24",
               {"device_class": "date", "text": "Spätestens Di., 24.11. laden"})
    assert hass.states.get("sensor.ladecockpit_next_charge").state == date(2026, 11, 24).isoformat()

    await send(hass, "sensor.ladecockpit_price_tip", "Morgens war bisher am günstigsten.", {"insights": ["a", "b"]})
    tip = hass.states.get("sensor.ladecockpit_price_tip")
    assert tip.state == "Morgens war bisher am günstigsten." and tip.attributes["insights"] == ["a", "b"]

    await send(hass, "sensor.ladecockpit_car", "Model 3", {"entity_picture": "https://example.test/car.png"})
    assert hass.states.get("sensor.ladecockpit_car").attributes["entity_picture"] == "https://example.test/car.png"

    await send(hass, "binary_sensor.ladecockpit_problem", "on", {"kind": "auth", "message": "Sign in again"})
    problem = hass.states.get("binary_sensor.ladecockpit_problem")
    assert problem.state == "on" and problem.attributes["kind"] == "auth"

    await send(hass, "sensor.ladecockpit_battery", "74", {"unit_of_measurement": "%", "device_class": "battery",
                                                          "state_class": "measurement"})
    assert hass.states.get("sensor.ladecockpit_battery").state == "74"
    await send(hass, "sensor.ladecockpit_battery", "unknown", {"unit_of_measurement": "%", "device_class": "battery"})
    assert hass.states.get("sensor.ladecockpit_battery").state == "unknown"

    # Eine Entität einer neueren App-Version oder etwas, das nicht uns gehört, wird ignoriert.
    await send(hass, "sensor.ladecockpit_something_new", "1", {})
    await send(hass, "sensor.other_thing", "1", {})
    assert hass.states.get("sensor.ladecockpit_something_new") is None


async def test_renamed_entity_still_gets_its_values(hass: HomeAssistant):
    await setup(hass)
    registry = er.async_get(hass)
    registry.async_update_entity("sensor.ladecockpit_month_cost", new_entity_id="sensor.tesla_ladekosten")
    await hass.async_block_till_done()
    await send(hass, "sensor.ladecockpit_month_cost", "99.00", MONTH)
    assert hass.states.get("sensor.tesla_ladekosten").state == "99.00"


async def test_restored_after_a_restart(hass: HomeAssistant):
    mock_restore_cache(hass, [State("sensor.ladecockpit_month_energy", "315.3",
                                    {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total",
                                     "last_reset": "2026-11-01T00:00:00+01:00", "invoice_kwh": 315.3})])
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", DOMAIN, "ladecockpit_month_energy",
                                 suggested_object_id="ladecockpit_month_energy")
    await setup(hass)
    energy = hass.states.get("sensor.ladecockpit_month_energy")
    assert energy.state == "315.3" and energy.attributes["invoice_kwh"] == 315.3
    assert energy.attributes["device_class"] == "energy" and energy.attributes["unit_of_measurement"] == "kWh"


async def test_unload(hass: HomeAssistant):
    entry = await setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await send(hass, "sensor.ladecockpit_month_cost", "1.00", MONTH)   # no listener left
    assert hass.states.get("sensor.ladecockpit_month_cost").state == "unavailable"

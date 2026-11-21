import asyncio
import dataclasses
import json

from app import demo
from app.entities import (
    ENTITY_IDS,
    EVENT_REWRITE_ALL_S,
    INTEGRATION_CHECK_S,
    MAX_STATE_LEN,
    REWRITE_ALL_S,
    STATE_EVENT,
    EntityPublisher,
    build_states,
)


def test_states_from_demo_data(settings):
    d = demo.build_demo(settings)
    states = build_states(d, "en")
    assert set(states) == set(ENTITY_IDS)
    for entity_id, (state, attributes) in states.items():
        assert isinstance(state, str) and 0 < len(state) <= MAX_STATE_LEN, entity_id
        assert attributes["friendly_name"].startswith("Ladecockpit ")
        json.dumps(attributes)                                   # must be JSON for the REST API
    cost, attrs = states["sensor.ladecockpit_month_cost"]
    assert float(cost) == d["month"]["total_cost"] and attrs["invoice_cost"] == d["month"]["cost"]
    assert attrs["unit_of_measurement"] == d["currency"] and attrs["home_kwh"] == d["month"]["home"]["kwh"]
    assert (attrs["state_class"], attrs["device_class"]) == ("total", "monetary")
    assert attrs["last_reset"].startswith(d["month"]["key"] + "-01T00:00:00")
    energy, attrs = states["sensor.ladecockpit_month_energy"]
    assert float(energy) == round(d["month"]["kwh"] + d["month"]["home"]["kwh"], 1)
    assert (attrs["unit_of_measurement"], attrs["device_class"], attrs["state_class"]) == ("kWh", "energy", "total")
    assert attrs["invoice_kwh"] == d["month"]["kwh"] and attrs["last_reset"].startswith(d["month"]["key"])
    battery, attrs = states["sensor.ladecockpit_battery"]
    assert battery == str(round(d["status"]["soc"])) and attrs["device_class"] == "battery"
    last, attrs = states["sensor.ladecockpit_last_charge"]
    assert float(last) == d["last_charge"]["cost"] and attrs["site"] in attrs["text"]
    assert states["binary_sensor.ladecockpit_problem"][0] in ("on", "off")


def test_states_german_and_empty(settings):
    d = demo.build_demo(dataclasses.replace(settings, lang="de"))
    states = build_states(d, "de")
    assert states["sensor.ladecockpit_next_charge"][1]["friendly_name"] == "Ladecockpit Nächste Ladung"
    assert "kWh" in states["sensor.ladecockpit_last_charge"][1]["text"]
    empty = build_states({"setup": {"tesla_configured": True, "tesla_connected": False}}, "en")
    assert empty["sensor.ladecockpit_battery"][0] == "unknown"
    assert empty["sensor.ladecockpit_last_charge"][0] == "unknown"
    assert empty["sensor.ladecockpit_month_cost"][0] == "0.00"
    assert empty["sensor.ladecockpit_month_cost"][1]["last_reset"] is None
    assert empty["sensor.ladecockpit_month_energy"][0] == "0.0"
    problem = empty["binary_sensor.ladecockpit_problem"]
    assert problem[0] == "on" and problem[1]["kind"] == "not_connected"


def test_problem_kind_from_sync(settings):
    d = demo.build_demo(settings)
    d["sync"] = {**d.get("sync", {}), "problem": "auth"}
    state, attrs = build_states(d, "en")["binary_sensor.ladecockpit_problem"]
    assert state == "on" and attrs["kind"] == "auth" and "sign-in" in attrs["message"]


class StateHA:
    def __init__(self, components=None):
        self.writes = []
        self.events = []
        self.loaded = components if components is not None else {"sensor", "recorder"}
        self.asked = 0

    async def components(self):
        self.asked += 1
        return self.loaded

    async def set_state(self, entity_id, state, attributes):
        self.writes.append(entity_id)
        return True

    async def fire_event(self, event_type, data):
        self.events.append((event_type, data))
        return True


def test_publisher_writes_changes_only(settings):
    data = demo.build_demo(settings)
    data["setup"] = {**data.get("setup", {}), "ha_ok": True}
    ha = StateHA()

    async def build():
        return data

    pub = EntityPublisher(settings, ha, build)

    async def go():
        assert await pub.publish_once(now=1000.0) == len(ENTITY_IDS)      # first round: all
        assert await pub.publish_once(now=1060.0) == 0                    # nothing changed
        data["month"] = {**data["month"], "cost": data["month"]["cost"] + 5}
        assert await pub.publish_once(now=1120.0) == 1                    # only the month cost
        assert await pub.publish_once(now=1000.0 + REWRITE_ALL_S) == len(ENTITY_IDS)
        data["setup"]["ha_ok"] = False
        assert await pub.publish_once(now=5000.0) == 0                    # HA away: wait
        data["setup"]["ha_ok"] = True
        assert await pub.publish_once(now=5060.0) == len(ENTITY_IDS)      # back: write all

    asyncio.run(go())


def test_publisher_sends_events_once_the_integration_is_loaded(settings):
    data = demo.build_demo(settings)
    data["setup"] = {**data.get("setup", {}), "ha_ok": True}
    ha = StateHA()

    async def build():
        return data

    pub = EntityPublisher(settings, ha, build)

    async def go():
        assert await pub.publish_once(now=1000.0) == len(ENTITY_IDS)       # no integration: states API
        assert len(ha.writes) == len(ENTITY_IDS) and not ha.events and pub.integration is False
        ha.loaded = {"sensor", "ladecockpit"}
        assert await pub.publish_once(now=1060.0) == 0                     # not asked again yet
        assert await pub.publish_once(now=1000.0 + INTEGRATION_CHECK_S) == len(ENTITY_IDS)
        assert pub.integration is True and len(ha.writes) == len(ENTITY_IDS)  # all again, as events
        event_type, payload = ha.events[0]
        assert event_type == STATE_EVENT and set(payload) == {"entity_id", "state", "attributes"}
        assert {p["entity_id"] for _, p in ha.events} == set(ENTITY_IDS)
        start = 1000.0 + INTEGRATION_CHECK_S
        data["month"] = {**data["month"], "cost": data["month"]["cost"] + 5}
        assert await pub.publish_once(now=start + 60) == 1                 # changes only
        assert await pub.publish_once(now=start + REWRITE_ALL_S) == 0      # no 10-minute rewrite
        assert await pub.publish_once(now=start + EVENT_REWRITE_ALL_S) == len(ENTITY_IDS)
        ha.loaded = None                                                   # HA cannot be asked: keep the way
        assert await pub.publish_once(now=start + EVENT_REWRITE_ALL_S + INTEGRATION_CHECK_S) == 0
        assert pub.integration is True

    asyncio.run(go())


def test_components_from_the_config_api(settings):
    import httpx

    from app.homeassistant import HAClient

    def handler(request):
        assert request.url.path == "/api/config"
        return httpx.Response(200, json={"components": ["sensor", "ladecockpit", "sensor.template"]})

    ha = HAClient(dataclasses.replace(settings, ha_url="http://ha.test", ha_token="t"),
                  transport=httpx.MockTransport(handler))
    assert asyncio.run(ha.components()) == {"sensor", "ladecockpit", "sensor.template"}
    down = HAClient(dataclasses.replace(settings, ha_url="http://ha.test", ha_token="t"),
                    transport=httpx.MockTransport(lambda r: httpx.Response(502)))
    assert asyncio.run(down.components()) is None
    assert asyncio.run(HAClient(dataclasses.replace(settings, ha_url="", ha_token="")).components()) is None


def test_set_state_posts_to_states_api(settings):
    import httpx

    from app.homeassistant import HAClient

    seen = {}

    def handler(request):
        seen["path"], seen["body"] = request.url.path, json.loads(request.content)
        return httpx.Response(201, json={})

    ha = HAClient(dataclasses.replace(settings, ha_url="http://ha.test", ha_token="t"),
                  transport=httpx.MockTransport(handler))
    assert asyncio.run(ha.set_state("sensor.ladecockpit_battery", "66", {"unit_of_measurement": "%"}))
    assert seen == {"path": "/api/states/sensor.ladecockpit_battery",
                    "body": {"state": "66", "attributes": {"unit_of_measurement": "%"}}}


def test_health_and_consumption_entities(settings):
    d = demo.build_demo(dataclasses.replace(settings, lang="de"))
    states = build_states(d, "de")
    r100, attrs = states["sensor.ladecockpit_range_at_100"]
    assert r100 == str(d["battery_health"]["range_at_100"]) and attrs["state_class"] == "measurement"
    cons, attrs = states["sensor.ladecockpit_consumption"]
    # On the first days of a month the demo month may have no distance yet
    expected = d["month"]["kwh_per_100"]
    assert (cons == "unknown" if expected is None else float(cons) == expected)
    assert attrs["unit_of_measurement"] == "kWh/100 km"
    assert attrs["by_temperature"][0]["label"] == "0 bis 10 °C" and attrs["temperature_tip"]
    empty = build_states({}, "de")
    assert empty["sensor.ladecockpit_range_at_100"][0] == "unknown"
    assert empty["sensor.ladecockpit_consumption"][1]["by_temperature"] == []

import asyncio
import dataclasses
import json

from app import demo
from app.entities import (
    ENTITY_IDS,
    MAX_STATE_LEN,
    REWRITE_ALL_S,
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
    assert float(cost) == d["month"]["cost"] and attrs["unit_of_measurement"] == d["currency"]
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
    problem = empty["binary_sensor.ladecockpit_problem"]
    assert problem[0] == "on" and problem[1]["kind"] == "not_connected"


def test_problem_kind_from_sync(settings):
    d = demo.build_demo(settings)
    d["sync"] = {**d.get("sync", {}), "problem": "auth"}
    state, attrs = build_states(d, "en")["binary_sensor.ladecockpit_problem"]
    assert state == "on" and attrs["kind"] == "auth" and "sign-in" in attrs["message"]


class StateHA:
    def __init__(self):
        self.writes = []

    async def set_state(self, entity_id, state, attributes):
        self.writes.append(entity_id)
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

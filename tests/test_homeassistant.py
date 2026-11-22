"""HAClient against a mocked Home Assistant REST API: states, errors, events, own entities."""
import asyncio
import dataclasses
import json
from datetime import datetime, timezone

import httpx

from app.homeassistant import HAClient, as_float, parse_dt


def _client(settings, handler, **entities):
    s = dataclasses.replace(settings, ha_url="http://ha.test", ha_token="t", **entities)
    return HAClient(s, transport=httpx.MockTransport(handler))


def _clear_entities(settings):
    """Nur die Entitäten, die ein Test selbst setzt."""
    return {f.name: "" for f in dataclasses.fields(settings) if f.name.startswith("ent_")}


def test_as_float_accepts_comma_and_drops_invalid_states():
    assert as_float("12,5") == 12.5
    assert as_float(7) == 7.0
    for bad in (None, "unknown", "Unavailable", "none", "", "abc", "nan"):
        assert as_float(bad) is None


def test_parse_dt_handles_z_naive_and_garbage():
    assert parse_dt("2026-11-21T10:00:00Z") == datetime(2026, 11, 21, 10, tzinfo=timezone.utc)
    assert parse_dt("2026-11-21T10:00:00").tzinfo == timezone.utc
    assert parse_dt("") is None
    assert parse_dt("yesterday") is None


def test_not_configured_does_nothing(settings):
    ha = HAClient(dataclasses.replace(settings, ha_url="", ha_token=""))
    assert not ha.configured
    assert asyncio.run(ha.state("sensor.x")) is None
    assert asyncio.run(ha.history("sensor.x", datetime.now(timezone.utc))) == []
    assert asyncio.run(ha.fire_event("ev", {})) is False
    assert asyncio.run(ha.call_service("notify", "x", {})) is False
    assert asyncio.run(ha.set_state("sensor.x", "1", {})) is False
    assert asyncio.run(ha.live())["available"] is False


def test_live_reads_values_units_weather_and_missing(settings):
    states = {
        "sensor.car_battery": {"state": "64", "attributes": {"unit_of_measurement": "%"}},
        "weather.home": {"state": "cloudy", "attributes": {"temperature": 4.5, "temperature_unit": "°C"}},
        "binary_sensor.car_charging": {"state": "off", "attributes": {}},
    }

    def handler(request):
        eid = request.url.path.rsplit("/", 1)[-1]
        assert request.headers["authorization"] == "Bearer t"
        return httpx.Response(200, json=states[eid]) if eid in states else httpx.Response(404)

    ha = _client(settings, handler, **{**_clear_entities(settings),
                                       "ent_soc": "sensor.car_battery", "ent_outside_temp": "weather.home",
                                       "ent_charging": "binary_sensor.car_charging",
                                       "ent_range": "sensor.car_range"})
    live = asyncio.run(ha.live())
    assert live["available"] is True and live["error"] is None
    assert live["values"]["soc"] == 64.0
    assert live["values"]["outside_temp"] == 4.5          # aus dem Wetter-Attribut übernommen
    assert live["units"] == {"soc": "%", "outside_temp": "°C"}
    assert live["raw"]["charging"] == "off" and live["values"]["charging"] is None
    assert live["missing"] == ["sensor.car_range"]


def test_live_reports_http_errors_without_a_missing_list(settings):
    ha = _client(settings, lambda request: httpx.Response(401),
                 **{**_clear_entities(settings), "ent_soc": "sensor.car_battery"})
    live = asyncio.run(ha.live())
    assert live["available"] is False
    assert live["error"] == "Home Assistant answered HTTP 401"
    assert live["missing"] == []


def test_live_reports_unreachable_home_assistant(settings):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    ha = _client(settings, handler, **{**_clear_entities(settings), "ent_soc": "sensor.car_battery"})
    live = asyncio.run(ha.live())
    assert live["available"] is False
    assert live["error"] == "Home Assistant not reachable (ConnectError)"


def test_live_clears_an_old_error(settings):
    status = {"code": 500}
    ha = _client(settings, lambda request: httpx.Response(status["code"], json={"state": "50"}),
                 **{**_clear_entities(settings), "ent_soc": "sensor.car_battery"})
    assert asyncio.run(ha.live())["available"] is False
    status["code"] = 200
    live = asyncio.run(ha.live())
    assert live["available"] is True and live["values"]["soc"] == 50.0


def test_history_sorts_and_skips_bad_rows_and_errors(settings):
    rows = [[
        {"state": "70", "last_changed": "2026-11-20T12:00:00+00:00"},
        {"state": "68", "last_updated": "2026-11-20T08:00:00Z"},
        {"state": "69", "last_changed": "not a date"},
    ]]
    ha = _client(settings, lambda request: httpx.Response(200, json=rows))
    points = asyncio.run(ha.history("sensor.car_battery", datetime(2026, 11, 19, tzinfo=timezone.utc)))
    assert [v for _, v in points] == [68.0, 70.0]

    ha = _client(settings, lambda request: httpx.Response(500))
    assert asyncio.run(ha.history("sensor.car_battery", datetime(2026, 11, 19, tzinfo=timezone.utc))) == []


def test_fire_event_posts_data_and_reports_rejection(settings):
    seen = []

    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200 if len(seen) == 1 else 400)

    ha = _client(settings, handler)
    assert asyncio.run(ha.fire_event("ladecockpit_invoice", {"cost": 12.3})) is True
    assert seen[0] == ("/api/events/ladecockpit_invoice", {"cost": 12.3})
    assert asyncio.run(ha.fire_event("ladecockpit_invoice", {})) is False
    assert ha.last_error == "Home Assistant rejected the event (HTTP 400)"


def test_call_service_and_set_state(settings, caplog):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(502 if request.url.path.endswith("broken") else 200)

    ha = _client(settings, handler)
    assert asyncio.run(ha.call_service("notify", "mobile_app_phone", {"message": "hi"})) is True
    assert asyncio.run(ha.set_state("sensor.ladecockpit_cost", "12.3", {"unit_of_measurement": "€"})) is True
    assert seen[1] == ("POST", "/api/states/sensor.ladecockpit_cost",
                       {"state": "12.3", "attributes": {"unit_of_measurement": "€"}})
    with caplog.at_level("WARNING", logger="ladecockpit.ha"):
        assert asyncio.run(ha.set_state("sensor.broken", "1", {})) is False
    assert "rejected sensor.broken (HTTP 502)" in caplog.text

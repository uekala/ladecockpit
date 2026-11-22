import dataclasses

from app import checks
from app.analytics import build_dashboard
from tests.test_v04 import NOW, _readings, _sessions


def test_setup_hints_name_the_option(settings):
    s = dataclasses.replace(settings, lang="de", ha_url="http://ha", ent_fuel_price="sensor.e10",
                            fuel_price_daily=False, ent_odometer="sensor.km", ent_soc="sensor.soc",
                            ent_charging="sensor.lade", ent_home_energy="", ent_outside_temp="weather.x",
                            fuel_consumption=None, ent_fuel_consumption="")
    ids = {h["id"]: h for h in checks.hints(s, "de")}
    assert set(ids) == {"fuel_daily", "fuel_no_consumption", "no_home"}
    assert "„Spritpreis als Tagesdurchschnitt“" in ids["fuel_daily"]["text"]
    assert ids["fuel_no_consumption"]["level"] == "missing"
    # alles gesetzt: nichts zu sagen; ohne Home Assistant: gar nichts
    full = dataclasses.replace(s, fuel_price_daily=True, fuel_consumption=7.5, ent_home_energy="sensor.wb")
    assert checks.hints(full, "de") == []
    assert checks.hints(dataclasses.replace(s, ha_url=""), "de") == []


def test_entity_report_finds_missing_text_and_wrong_units():
    roles = {"soc": "sensor.soc", "odometer": "sensor.km", "fuel_price": "sensor.e10", "charging": "sensor.lade",
             "range": "sensor.range", "home_energy": "sensor.wb"}
    live = {"available": True, "missing": ["sensor.wb"],
            "raw": {"soc": "55", "odometer": "12345", "fuel_price": "unavailable", "charging": "Stopped", "range": "abc"},
            "values": {"soc": 55.0, "odometer": 12345.0, "fuel_price": None, "range": None},
            "units": {"soc": "%", "odometer": "m", "range": "km"}}
    rows = {r["role"]: r for r in checks.entity_report(roles, live, "en")}
    assert rows["soc"]["ok"] and rows["soc"]["label"] == "Battery level"
    assert rows["charging"]["ok"]                                    # Text ist für den Ladezustand in Ordnung
    assert rows["odometer"]["problem"] == "unexpected unit m"
    assert rows["fuel_price"]["problem"] == "unavailable right now"
    assert rows["range"]["problem"] == "does not deliver a number"
    assert rows["home_energy"]["problem"] == "entity not found"
    assert [r["role"] for r in checks.entity_report(roles, live, "en")][:3] == ["soc", "range", "odometer"]
    down = checks.entity_report(roles, {"available": False}, "en")
    assert all(r["ok"] is None for r in down)


def _dash(settings):
    live = {"values": {"soc": 30.0, "fuel_consumption": 8.0, "fuel_price": 2.0}, "units": {"odometer": "km"}}
    return build_dashboard(sessions=_sessions(), live=live, readings=_readings(),
                           settings=dataclasses.replace(settings, lang="de"), meta={}, now=NOW)


def test_radar_per_site_and_tips_with_a_target(settings):
    d = _dash(settings)
    mainz = next(r for r in d["site_radar"] if r["site_name"] == "Mainz, Germany")
    assert mainz["sessions"] == 3 and len(mainz["slots"]) == 5
    assert sum(s["sessions"] for s in mainz["slots"]) == 3
    assert all(r["sessions"] >= 3 for r in d["site_radar"])           # Bad Homburg hat nur 2
    assert all("action" in i and i["action"]["go"] for i in d["insights"])
    m = next(m for m in d["monthly"] if m.get("fuel_per_100") is not None)
    assert m["fuel_per_100"] == 16.0


def test_setup_steps_name_the_next_thing_to_do(settings):
    s = dataclasses.replace(settings, lang="de", tesla_client_id="abc", ha_url="", ha_token="")
    steps = {x["id"]: x for x in checks.steps(s, {}, [], [], "de")}
    assert [x for x in steps] == ["tesla_app", "tesla_login", "sync", "ha"]
    assert steps["tesla_app"]["status"] == "done"
    assert steps["tesla_login"]["status"] == "todo" and steps["sync"]["status"] == "waiting"
    assert steps["ha"]["status"] == "optional" and not steps["ha"]["required"]
    # angemeldet, abgeglichen, Home Assistant mit einer kaputten Entität und einem Tipp
    s2 = dataclasses.replace(s, ha_url="http://ha", ha_token="t")
    ents = [{"ok": True}, {"ok": False}]
    done = {x["id"]: x for x in checks.steps(
        s2, {"tesla_connected": True, "last_sync": "2026-11-21T08:00:00+00:00", "sessions": 12, "ha_ok": True,
             "when": "21.11. 09:00"}, ents, [{"id": "no_home"}], "de")}
    assert all(done[k]["status"] == "done" for k in ("tesla_app", "tesla_login", "sync", "ha"))
    assert done["sync"]["text"] == "12 Ladungen geholt, zuletzt 21.11. 09:00."
    assert done["entities"]["status"] == "problem" and done["entities"]["text"].startswith("1 von 2")
    assert done["extras"]["text"] == "1 Option würde noch etwas bringen."
    expired = {x["id"]: x for x in checks.steps(s, {"tesla_auth_error": "Token abgelaufen"}, [], [], "de")}
    assert expired["tesla_login"] == {**expired["tesla_login"], "status": "problem", "text": "Token abgelaufen"}


def test_values_that_only_exist_while_charging_are_no_problem():
    roles = {"time_to_full": "sensor.zeit", "charge_power": "sensor.leistung", "soc": "sensor.soc"}
    live = {"available": True, "raw": {"time_to_full": "unavailable", "charge_power": "unknown", "soc": "unavailable"},
            "values": {}, "units": {}}
    rows = {r["role"]: r for r in checks.entity_report(roles, live, "de")}
    assert rows["time_to_full"]["ok"] and rows["time_to_full"]["note"] == "nur beim Laden"
    assert rows["charge_power"]["ok"]
    assert rows["soc"]["ok"] is False


def test_the_tesla_line_adds_up_to_the_invoices(settings):
    d = _dash(settings)
    m = d["month"]
    assert m["distance_cost"] is not None
    assert round(m["fuel_equivalent"] - m["savings"], 2) == m["distance_cost"]

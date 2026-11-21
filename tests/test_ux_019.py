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
    # everything set: nothing to say; without Home Assistant: nothing at all
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
    assert rows["charging"]["ok"]                                    # text is fine for the charging state
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
    assert all(r["sessions"] >= 3 for r in d["site_radar"])           # Bad Homburg has only 2
    assert all("action" in i and i["action"]["go"] for i in d["insights"])
    m = next(m for m in d["monthly"] if m.get("fuel_per_100") is not None)
    assert m["fuel_per_100"] == 16.0

"""Setup check: an offline car is no setup problem, and tips can be hidden."""
import asyncio
import dataclasses

from fastapi.testclient import TestClient

from app import checks, main
from app.config import load
from app.db import DB

ROLES = {"soc": "sensor.tesla_battery", "range": "sensor.tesla_range", "odometer": "sensor.tesla_odometer",
         "charging": "sensor.tesla_charging", "outside_temp": "sensor.tesla_outside", "fuel_price": "sensor.e10",
         "charge_power": "sensor.tesla_power"}


def _asleep(**raw) -> dict:
    """Home Assistant right after a restart while the car is offline: every car value unknown."""
    values = {"soc": "unknown", "range": "unknown", "odometer": "unknown", "charging": "unknown",
              "outside_temp": "unknown", "fuel_price": "1.79", "charge_power": "unavailable", **raw}
    return {"available": True, "raw": values, "values": {"fuel_price": 1.79},
            "units": {"soc": "%", "range": "km", "odometer": "km", "fuel_price": "€"}}


def test_an_offline_car_is_no_setup_problem(settings):
    rows = {r["role"]: r for r in checks.entity_report(ROLES, _asleep(), "de", seen_before=True)}
    for role in ("soc", "range", "odometer", "charging", "outside_temp"):
        assert rows[role]["ok"] is True and rows[role]["offline"] is True and rows[role]["note"] == "Auto offline", role
    assert rows["fuel_price"]["ok"] and not rows["fuel_price"]["offline"]
    assert rows["charge_power"]["note"] == "nur beim Laden"

    s = dataclasses.replace(settings, lang="de", ha_url="http://ha", ha_token="t")
    rep = checks.report(s, ROLES, _asleep(), {"ha_ok": True, "car_when": "21.11. 21:12"})
    assert rep["offline"] == "21.11. 21:12"
    assert not [e for e in rep["entities"] if e["ok"] is False]
    step = next(x for x in rep["steps"] if x["id"] == "entities")
    assert step["status"] == "done" and "Auto gerade offline" in step["text"] and "21.11. 21:12" in step["text"]


def test_a_car_that_never_delivered_a_value_is_still_checked():
    rows = checks.entity_report(ROLES, _asleep(), "en", seen_before=False)
    bad = {r["role"] for r in rows if r["ok"] is False}
    assert bad == {"soc", "range", "odometer", "charging", "outside_temp"}
    assert all(r["problem"] == "unavailable right now" for r in rows if r["ok"] is False)


def test_single_values_missing_while_the_car_is_online_are_problems():
    # The odometer delivers, so the car is online: the battery without a value is a real problem.
    rows = {r["role"]: r for r in checks.entity_report(ROLES, _asleep(odometer="12345"), "en", seen_before=True)}
    assert rows["soc"]["ok"] is False and not rows["soc"]["offline"]
    # An entity that does not exist at all is never explained away as an offline car.
    live = {**_asleep(), "missing": ["sensor.tesla_range"]}
    rows = {r["role"]: r for r in checks.entity_report(ROLES, live, "en", seen_before=True)}
    assert rows["range"]["problem"] == "entity not found" and rows["soc"]["ok"] is False
    # Home Assistant down: nothing to judge, as before
    assert all(r["ok"] is None for r in checks.entity_report(ROLES, {"available": False}, "en", seen_before=True))
    # The weather station gone while the car is online: still a problem
    rows = {r["role"]: r for r in checks.entity_report(
        ROLES, _asleep(soc="40", range="230", odometer="12345", charging="stopped"), "en", seen_before=True)}
    assert rows["outside_temp"]["ok"] is False


def test_tips_can_be_hidden_but_a_half_setup_cannot(settings):
    s = dataclasses.replace(settings, lang="de", ha_url="http://ha", ha_token="t", ent_home_energy="",
                            ent_outside_temp="", ent_fuel_price="sensor.e10", fuel_consumption=None,
                            ent_fuel_consumption="", ent_odometer="sensor.km", ent_soc="sensor.soc",
                            ent_charging="sensor.lade", fuel_price_daily=True)
    all_ids = {h["id"]: h for h in checks.hints(s, "de")}
    assert all_ids["no_home"]["dismissable"] and not all_ids["fuel_no_consumption"]["dismissable"]
    assert set(all_ids) <= set(checks.HINT_IDS)

    rep = checks.report(s, {}, {"available": True}, {}, hidden={"no_home", "no_temp", "fuel_no_consumption"})
    assert [h["id"] for h in rep["hints"]] == ["fuel_no_consumption"]   # stays: half set up
    assert rep["hidden"] == 2

    rep = checks.report(dataclasses.replace(s, fuel_consumption=7.0), {}, {"available": True}, {},
                        hidden={"no_home", "no_temp"})
    assert rep["hints"] == [] and rep["hidden"] == 2 and rep["hidden_note"] is None
    extras = next(x for x in rep["steps"] if x["id"] == "extras")
    assert extras["status"] == "done" and extras["text"] == "Keine offenen Tipps, 2 ausgeblendet."


class _IdleSync:
    last_sync = None
    next_sync = None
    last_error = None
    bursting = False

    async def run_forever(self):
        await asyncio.Event().wait()


def test_hiding_a_tip_is_kept(monkeypatch, tmp_path):
    db = DB(tmp_path / "ladecockpit.db")
    settings = dataclasses.replace(load(), data_dir=tmp_path, tesla_client_id="id", tesla_client_secret="secret",
                                   app_password="pw", ha_url="http://ha.invalid", ha_token="t", force_demo=False,
                                   lang="de", ent_home_energy="")
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main, "sync", _IdleSync())
    with TestClient(main.app) as client:
        client.auth = ("ladecockpit", "pw")

        def check():
            return client.get("/api/dashboard").json()["setup"]["checks"]

        assert "no_home" in [h["id"] for h in check()["hints"]] and check()["hidden"] == 0
        assert client.put("/api/hint", json={"id": "no_home", "hidden": True}).json() == {"hidden": ["no_home"]}
        after = check()
        assert "no_home" not in [h["id"] for h in after["hints"]] and after["hidden"] == 1
        assert client.put("/api/hint", json={"id": "nonsense"}).status_code == 400
        assert client.put("/api/hint", json={"id": "no_home", "hidden": False}).json() == {"hidden": []}
        client.put("/api/hint", json={"id": "no_temp"})
        assert client.delete("/api/hints/hidden").json() == {"hidden": []}
        assert check()["hidden"] == 0


def test_the_demo_keeps_its_tips():
    with TestClient(main.app) as client:
        assert client.put("/api/hint", json={"id": "no_home"}).status_code == 404
        assert client.delete("/api/hints/hidden").status_code == 404

"""In der App einem Standort zugeordnete Betreiber: gespeichert, auf alle seine Ladungen angewandt, ohne Neustart."""
import asyncio
import dataclasses
import json

from fastapi.testclient import TestClient

from app import main, networks
from app.config import load
from app.db import DB


class _IdleSync:
    last_sync = None
    next_sync = None
    last_error = None
    bursting = False

    async def run_forever(self):
        await asyncio.Event().wait()


def _session(session_id: str, site: str, start: str, price: float) -> dict:
    raw = {"siteLocationName": site, "invoices": [{"fileName": "4020MSP0000019849_NL-NL.pdf"}]}
    return {"session_id": session_id, "vin": "TESTVIN0000000001", "site": site, "country": "NL",
            "start_ts": start, "stop_ts": start, "kwh": 20.0, "charge_cost": 20 * price, "idle_fee": 0.0,
            "other_fee": 0.0, "total": 20 * price, "currency": "EUR", "price": price,
            "invoices": json.dumps([{"id": "inv-" + session_id}]), "raw": json.dumps(raw)}


def test_demo_has_nothing_to_assign():
    with TestClient(main.app) as client:
        assert client.put("/api/operator", json={"site": "Hafenstadt", "operator": "Fastned"}).status_code == 404
        listed = client.get("/api/operators").json()
        assert listed["assigned"] == {} and "Fastned" in listed["known"] and "IONITY" in listed["known"]


def test_assign_and_remove_an_operator(monkeypatch, tmp_path):
    db = DB(tmp_path / "ladecockpit.db")
    db.upsert_session(_session("a1", "Hafenstadt, Netherlands", "2026-10-01T10:00:00+00:00", 0.59), "pushed")
    db.upsert_session(_session("b2", "Hafenstadt, Netherlands", "2026-10-05T10:00:00+00:00", 0.61), "pushed")
    settings = dataclasses.replace(load(), data_dir=tmp_path, tesla_client_id="id", tesla_client_secret="secret",
                                   app_password="pw", ha_url="", ha_token="", force_demo=False)
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main, "sync", _IdleSync())
    try:
        with TestClient(main.app) as client:
            assert client.put("/api/operator", json={"site": "x", "operator": "y"}).status_code == 401
            client.auth = ("ladecockpit", "pw")

            def site_row():
                return next(s for s in client.get("/api/dashboard").json()["sites"]
                            if s["site_name"] == "Hafenstadt, Netherlands")

            before = site_row()
            assert before["operator"] is None and before["operator_assigned"] is False and before["sessions"] == 2

            assert client.put("/api/operator", json={"site": " ", "operator": "Fastned"}).status_code == 400
            assert client.put("/api/operator", json={"site": "Hafenstadt, Netherlands", "operator": "x" * 61}).status_code == 400
            saved = client.put("/api/operator", json={"site": "hafenstadt,  netherlands", "operator": " Fastned "})
            assert saved.status_code == 200 and saved.json()["operator"] == "Fastned"

            # Gilt sofort für jede Ladung des Standorts, ohne Neustart.
            after = site_row()
            assert after["operator"] == "Fastned" and after["operator_assigned"] is True
            assert after["label"].startswith("Fastned")
            operators = {s["operator"] for s in client.get("/api/dashboard").json()["sessions"]}
            assert operators == {"Fastned"}
            assert client.get("/api/operators").json()["assigned"] == {"hafenstadt, netherlands": "Fastned"}
            assert json.loads(db.kv_get("site_operators")) == {"hafenstadt, netherlands": "Fastned"}

            # Changing replaces, an empty operator removes.
            client.put("/api/operator", json={"site": "Hafenstadt, Netherlands", "operator": "Allego"})
            assert site_row()["operator"] == "Allego"
            assert len(client.get("/api/operators").json()["assigned"]) == 1
            removed = client.put("/api/operator", json={"site": "Hafenstadt, Netherlands", "operator": ""})
            assert removed.json()["operator"] is None and removed.json()["assigned"] == {}
            assert site_row()["operator"] is None and site_row()["operator_assigned"] is False
    finally:
        networks.set_assigned_sites({})


def test_assigned_site_beats_the_option_and_travels_with_the_backup(tmp_path):
    from app import backup
    try:
        networks.configure(0.5, "Hafenstadt=Aus der Option")
        assert networks.assigned_operator("Hafenstadt Oost") == "Aus der Option"
        networks.set_assigned_sites({"Hafenstadt Oost": "Fastned", "": "leer", "Ort": " "})
        assert networks.assigned_operator("hafenstadt  oost") == "Fastned"
        assert networks.assigned_operator("Hafenstadt West") == "Aus der Option"
        assert networks.assigned_sites() == {"hafenstadt oost": "Fastned"}
    finally:
        networks.configure(0.5)
        networks.set_assigned_sites({})

    source = DB(tmp_path / "a" / "ladecockpit.db")
    source.kv_set("site_operators", json.dumps({"Hafenstadt": "Fastned"}))
    target = tmp_path / "backup.zip"
    backup.create(source, tmp_path / "a", "test", target)
    other = DB(tmp_path / "b" / "ladecockpit.db")
    backup.restore(other, tmp_path / "b", target)
    assert json.loads(other.kv_get("site_operators")) == {"Hafenstadt": "Fastned"}

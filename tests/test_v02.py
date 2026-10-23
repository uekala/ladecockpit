import asyncio
import dataclasses
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from app import config as config_module
from app.analytics import build_dashboard
from app.export import sessions_csv
from app.sync import SyncService
from app.tesla import TeslaError
from app.watcher import Watcher

ROOT = Path(__file__).resolve().parent.parent


# --- Home Assistant app ----------------------------------------------------------------
def test_app_options_become_settings(tmp_path, monkeypatch):
    options = tmp_path / "options.json"
    options.write_text(json.dumps({
        "language": "de", "tesla_client_id": "cid", "tesla_client_secret": "sec",
        "tesla_region": "eu", "tesla_redirect_uri": "http://localhost:8077/auth/callback",
        "entity_battery": "sensor.car_battery", "entity_charging": "", "charging_state": "charging",
        "soc_floor": 15, "soc_target": 70, "notify_problems": False, "reference_price": 0.49,
    }))
    monkeypatch.setattr(config_module, "ADDON_OPTIONS_PATH", options)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-token")
    monkeypatch.delenv("APP_MODE", raising=False)
    s = config_module.load()
    assert s.addon and not s.demo
    assert s.ha_url == "http://supervisor/core" and s.ha_token == "supervisor-token"
    assert s.data_dir == tmp_path
    assert s.lang == "de" and s.locale == "de-DE"
    assert s.tesla_client_id == "cid" and s.ent_soc == "sensor.car_battery" and s.ent_charging == ""
    assert (s.soc_floor, s.soc_target, s.notify_problems, s.reference_price) == (15, 70, False, 0.49)


def test_app_config_is_complete():
    cfg = yaml.safe_load((ROOT / "ladecockpit-app/config.yaml").read_text())
    schema = set(cfg["schema"])
    assert set(cfg["options"]) <= schema
    assert schema == set(config_module.ADDON_OPTION_MAP)
    for lang in ("en", "de"):
        tr = yaml.safe_load((ROOT / f"ladecockpit-app/translations/{lang}.yaml").read_text(encoding="utf-8"))
        assert set(tr["configuration"]) == schema, lang
    from app import __version__
    assert cfg["version"] == __version__
    assert cfg["ingress_port"] == 8077 and cfg["homeassistant_api"] is True


# --- analytics: power and energy per distance --------------------------------------------
def _session(sid, start, minutes, kwh, total):
    return {"session_id": sid, "site": "S", "start_ts": start.isoformat(timespec="seconds"),
            "stop_ts": (start + timedelta(minutes=minutes)).isoformat(timespec="seconds"),
            "kwh": kwh, "charge_cost": total, "idle_fee": 0.0, "total": total,
            "currency": "EUR", "price": total / kwh, "invoices": [], "push_state": "pushed"}


def test_power_and_kwh_per_100(settings):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    sessions = [_session("a", datetime(2026, 10, 15, 17, tzinfo=timezone.utc), 30, 50.0, 18.5),
                _session("b", datetime(2026, 10, 18, 17, tzinfo=timezone.utc), 15, 15.0, 5.55)]
    readings = {"soc": [], "soc_last": None, "range_last": None,
                "odometer": [(datetime(2026, 10, 1, 8, tzinfo=timezone.utc), 1000.0),
                             (datetime(2026, 10, 20, 8, tzinfo=timezone.utc), 1400.0)]}
    d = build_dashboard(sessions=sessions, live={"values": {}, "units": {"odometer": "km"}},
                        readings=readings, settings=settings, meta={}, now=now)
    assert d["sessions"][0]["avg_kw"] == 60 or d["sessions"][1]["avg_kw"] == 60
    assert {s["id"]: s["avg_kw"] for s in d["sessions"]} == {"a": 100, "b": 60}
    assert d["sites"][0]["avg_kw"] == 87                  # 65 kWh in 0.75 h
    assert d["month"]["kwh_per_100"] == 16.2               # 65 kWh / 400 km
    assert d["month"]["per_100"] == 6.01
    assert d["monthly"][-1]["kwh_per_100"] == 16.2


# --- export ----------------------------------------------------------------------------------
def test_csv_en_and_de(settings):
    s = _session("x", datetime(2026, 10, 15, 17, tzinfo=timezone.utc), 30, 50.0, 18.5)
    en = sessions_csv([s], settings).lstrip("﻿").splitlines()
    assert en[0].startswith("Date,Start,End,Site,kWh")
    assert en[1].split(",")[4] == "50.000" and en[1].split(",")[10] == "100"
    de = sessions_csv([s], dataclasses.replace(settings, lang="de")).lstrip("﻿").splitlines()
    assert de[0].startswith("Datum;Start;Ende;Standort;kWh")
    assert de[1].split(";")[0] == "15.10.2026" and de[1].split(";")[8] == "18,50"


# --- watcher: history on a fresh install ------------------------------------------------------
class HistoryHA:
    def entities(self):
        return {"soc": "sensor.battery", "odometer": "sensor.odometer"}

    async def history(self, entity, start):
        base = datetime(2026, 10, 10, tzinfo=timezone.utc)
        if entity == "sensor.battery":
            return [(base, 70.0), (base + timedelta(minutes=5), 70.0), (base + timedelta(hours=2), 64.0)]
        return [(base, 1000.0), (base + timedelta(hours=3), 1040.0)]


def test_seed_from_history_once(settings, db):
    watcher = Watcher(settings, db, HistoryHA(), sync=None)
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    assert asyncio.run(watcher.seed_from_history(now)) == 4      # duplicate 70 % dropped
    assert db.last_reading("soc")[1] == 64.0
    assert asyncio.run(watcher.seed_from_history(now)) == 0      # already has readings


# --- problem notifications ----------------------------------------------------------------------
class FlakyTesla:
    connected = True
    auth_error = None

    def __init__(self):
        self.fail = True

    async def charging_history(self, start_time=None):
        if self.fail:
            raise TeslaError("Tesla /api/1/dx/charging/history: HTTP 503")
        return []


class RecordingHA:
    configured = True

    def __init__(self):
        self.calls, self.events = [], []

    async def call_service(self, domain, service, data):
        self.calls.append((domain, service, data))
        return True

    async def fire_event(self, event_type, data):
        self.events.append((event_type, data))
        return True


def test_problem_raised_once_and_cleared(settings, db):
    tesla, ha = FlakyTesla(), RecordingHA()
    sync = SyncService(settings, db, tesla, ha)

    async def go():
        for _ in range(5):
            await sync.tick()
        tesla.fail = False
        await sync.tick()

    asyncio.run(go())
    creates = [c for c in ha.calls if c[1] == "create"]
    dismisses = [c for c in ha.calls if c[1] == "dismiss"]
    assert len(creates) == 1 and "503" in creates[0][2]["message"]
    assert len(dismisses) == 1
    assert [e[0] for e in ha.events] == ["ladecockpit_problem"]


def test_expired_login_is_reported(settings, db):
    tesla, ha = FlakyTesla(), RecordingHA()
    tesla.auth_error = "Token refresh failed (HTTP 401)."
    sync = SyncService(dataclasses.replace(settings, lang="de"), db, tesla, ha)
    asyncio.run(sync.tick())
    asyncio.run(sync.tick())
    creates = [c for c in ha.calls if c[1] == "create"]
    assert len(creates) == 1 and "Tesla-Anmeldung" in creates[0][2]["message"]


def test_no_notifications_when_disabled(settings, db):
    tesla, ha = FlakyTesla(), RecordingHA()
    tesla.auth_error = "expired"
    sync = SyncService(dataclasses.replace(settings, notify_problems=False), db, tesla, ha)
    asyncio.run(sync.tick())
    assert ha.calls == [] and ha.events == []

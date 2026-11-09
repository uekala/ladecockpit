"""Backend integration checks for a live standalone instance without Home Assistant."""
import asyncio
import dataclasses

from fastapi.testclient import TestClient

from app import main
from app.config import load
from app.db import DB
from app.homeassistant import HAClient


class _IdleSync:
    last_sync = None
    next_sync = None
    last_error = None
    bursting = False

    async def run_forever(self):
        await asyncio.Event().wait()


class _DisconnectedTesla:
    connected = False
    auth_error = None


def test_live_dashboard_starts_and_serves_without_home_assistant(monkeypatch, tmp_path):
    """A configured Tesla app with empty HA settings must use live mode, not demo mode."""
    settings = dataclasses.replace(
        load(),
        data_dir=tmp_path,
        tesla_client_id="test-client",
        tesla_client_secret="test-secret",
        app_password="test-password",
        ha_url="",
        ha_token="",
        force_demo=False,
    )
    database = DB(tmp_path / "standalone.db")
    captured = {}

    async def no_readings(_now):
        return {}

    def build_without_external_data(**kwargs):
        captured.update(kwargs)
        return {
            "mode": "live",
            "setup": kwargs["meta"]["setup"],
            "sessions": [],
            "forecast": {},
            "month": {},
            "totals": {},
            "insights": [],
        }

    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "db", database)
    monkeypatch.setattr(main, "tesla", _DisconnectedTesla())
    monkeypatch.setattr(main, "ha", HAClient(settings))
    monkeypatch.setattr(main, "sync", _IdleSync())
    monkeypatch.setattr(main, "watcher", type("WatcherStub", (), {"latest": None})())
    monkeypatch.setattr(main, "_readings", no_readings)
    monkeypatch.setattr(main, "_live", lambda: (_ for _ in ()).throw(AssertionError("HA live data was requested")))
    monkeypatch.setattr(main, "build_dashboard", build_without_external_data)
    monkeypatch.setattr(main, "_car", lambda _sessions=None: {"name": "Test Tesla"})
    monkeypatch.setattr(main, "_look", lambda: "classic")

    assert settings.demo is False
    assert main.ha.configured is False

    with TestClient(main.app) as client:
        # /healthz is only open without a password from localhost (container health check).
        health = client.get("/healthz", auth=("test", "test-password"))
        assert health.status_code == 200
        assert health.json()["mode"] == "live"

        page = client.get("/", auth=("test", "test-password"))
        assert page.status_code == 200
        assert "Ladecockpit" in page.text

        response = client.get("/api/dashboard", auth=("test", "test-password"))
        assert response.status_code == 200
        dashboard = response.json()

    assert dashboard["mode"] == "live"
    assert dashboard["setup"]["ha_configured"] is False
    assert dashboard["setup"]["entities"] == []
    assert dashboard["car"]["name"] == "Test Tesla"
    assert captured["live"] == {
        "available": False,
        "values": {},
        "units": {},
    }

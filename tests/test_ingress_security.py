import dataclasses

from fastapi.testclient import TestClient

import app.main as main_module


def _addon_settings(monkeypatch, password=""):
    monkeypatch.setattr(
        main_module,
        "settings",
        dataclasses.replace(
            main_module.settings,
            addon=True,
            app_password=password,
        ),
    )


def test_addon_direct_access_is_blocked_without_app_password(monkeypatch):
    _addon_settings(monkeypatch)

    with TestClient(main_module.app, client=("192.168.1.25", 12345)) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 403
    assert "Direct access is disabled" in response.text


def test_forged_ingress_headers_do_not_bypass_direct_access(monkeypatch):
    _addon_settings(monkeypatch)

    with TestClient(main_module.app, client=("192.168.1.25", 12345)) as client:
        response = client.get(
            "/api/dashboard",
            headers={
                "X-Hass-Source": "core.ingress",
                "X-Ingress-Path": "/api/hassio_ingress/fake-token",
            },
        )

    assert response.status_code == 403


def test_supervisor_ingress_is_allowed_without_mobile_password(monkeypatch):
    _addon_settings(monkeypatch)

    with TestClient(main_module.app, client=("172.30.32.2", 12345)) as client:
        response = client.get(
            "/api/dashboard",
            headers={
                "X-Hass-Source": "core.ingress",
                "X-Ingress-Path": "/api/hassio_ingress/test-token",
            },
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "demo"


def test_direct_access_requires_correct_mobile_password(monkeypatch):
    _addon_settings(monkeypatch, password="test-secret")

    with TestClient(main_module.app, client=("100.64.0.10", 12345)) as client:
        denied = client.get("/api/dashboard")
        allowed = client.get(
            "/api/dashboard",
            headers={"Authorization": "Basic bGFkZWNvY2twaXQ6dGVzdC1zZWNyZXQ="},
        )

    assert denied.status_code == 401
    assert allowed.status_code == 200

"""Durchgehende Prüfungen des Tesla-Abgleichs im eigenständigen Betrieb ohne Home Assistant."""
import asyncio
import dataclasses
import io
import time
import zipfile
from pathlib import Path

import httpx
from fpdf import FPDF
from test_networks import SUPERCHARGER_RAW

from app import main
from app.db import DB
from app.homeassistant import HAClient
from app.sync import SyncService
from app.tesla import TeslaClient


def invoice_pdf() -> bytes:
    doc = FPDF()
    doc.add_page()
    doc.set_font("Helvetica", size=10)
    doc.cell(0, 8, "Tesla invoice")
    doc.ln()
    doc.cell(0, 8, "Rechnungsnummer 4020P0000067890")
    return bytes(doc.output())


def test_tesla_history_invoice_and_export_work_without_home_assistant(settings, tmp_path, monkeypatch):
    """Teslas HTTP-API nachbilden, Ladung und PDF lokal speichern und beides ausliefern."""
    settings = dataclasses.replace(
        settings,
        data_dir=tmp_path,
        tesla_client_id="test-client",
        tesla_client_secret="test-secret",
        ha_url="",
        ha_token="",
        force_demo=False,
        api_base_override="https://tesla.test",
        token_url_override="https://tesla.test/oauth/token",
        operator_lookup=False,
    )
    database_path = tmp_path / "standalone.db"
    database = DB(database_path)
    pdf = invoice_pdf()
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/1/dx/charging/history":
            raw = {
                **SUPERCHARGER_RAW,
                "sessionId": "standalone-session-42",
                "invoices": [{
                    "contentId": "invoice-42",
                    "fileName": "tesla-invoice.pdf",
                    "invoiceType": "IMMEDIATE",
                }],
            }
            return httpx.Response(200, json={"response": {"data": [raw], "totalResults": 1}})
        if request.url.path == "/api/1/dx/charging/invoice/invoice-42":
            return httpx.Response(200, content=pdf, headers={"Content-Type": "application/pdf"})
        raise AssertionError(f"Unexpected mocked Tesla request: {request.method} {request.url}")

    tesla = TeslaClient(settings, database, transport=httpx.MockTransport(handler))
    # A valid test token avoids even a mocked OAuth refresh request.
    database.kv_set("tesla_access_token", "test-access-token")
    database.kv_set("tesla_refresh_token", "test-refresh-token")
    database.kv_set("tesla_access_expires", str(time.time() + 3600))

    ha = HAClient(settings)
    assert ha.configured is False

    async def forbidden_ha_call(*_args, **_kwargs):
        raise AssertionError("Standalone sync must not call Home Assistant")

    monkeypatch.setattr(ha, "fire_event", forbidden_ha_call)
    monkeypatch.setattr(ha, "call_service", forbidden_ha_call)
    sync = SyncService(settings, database, tesla, ha)

    assert asyncio.run(sync.sync_once()) == 1
    assert asyncio.run(sync.push_pending()) == 0
    stored = database.session("standalone-session-42")
    assert stored is not None
    assert stored["push_state"] == "backfill"
    assert stored["kwh"] == 6.05
    assert stored["invoices"][0]["id"] == "invoice-42"
    assert (tmp_path / "invoices" / "standalone-session-42.pdf").read_bytes() == pdf
    assert database.kv_get("last_sync") is not None
    assert len(requests) == 2
    assert all(request.headers.get("Authorization") == "Bearer test-access-token" for request in requests)

    # Die SQLite-Datenbank neu öffnen, um zu zeigen, dass die importierten Daten einen Neustart des Prozesses überstehen.
    reopened = DB(database_path)
    assert reopened.session("standalone-session-42")["total"] == stored["total"]

    # Dieselben Handler für Rechnungs- und CSV-Antworten durchlaufen, die die HTTP-Routen nutzen.
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "db", reopened)
    monkeypatch.setattr(main, "tesla", tesla)

    invoice_response = asyncio.run(main.invoice("standalone-session-42"))
    assert Path(invoice_response.path) == tmp_path / "invoices" / "standalone-session-42.pdf"
    assert Path(invoice_response.path).read_bytes() == pdf

    csv_response = asyncio.run(main.export_csv())
    csv_text = csv_response.body.decode("utf-8-sig")
    assert "standalone-session-42" in csv_text
    assert "Partnerstadt, Germany" in csv_text

    # Die echten HTTP-Routen durchlaufen, samt Darstellung der PDF-Seiten und ZIP-Export des Monats.
    async def exercise_http_routes():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            download = await client.get("/api/invoice/standalone-session-42")
            assert download.status_code == 200
            assert download.headers["content-type"] == "application/pdf"
            assert download.content == pdf
            assert "supercharger-2026-10" in download.headers["content-disposition"]

            pages = await client.get("/api/invoice/standalone-session-42/pages")
            assert pages.status_code == 200
            assert pages.json()["pages"] == 1

            page = await client.get("/api/invoice/standalone-session-42/page/1.png")
            assert page.status_code == 200
            assert page.headers["content-type"] == "image/png"
            assert page.content.startswith(bytes.fromhex("89504e470d0a1a0a"))

            missing_page = await client.get("/api/invoice/standalone-session-42/page/2.png")
            assert missing_page.status_code == 404

            archive = await client.get("/api/invoices/2026-10.zip")
            assert archive.status_code == 200
            assert archive.headers["content-type"] == "application/zip"
            with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
                names = zipped.namelist()
                assert len(names) == 1
                assert names[0].endswith("standalone-session-42.pdf")
                assert zipped.read(names[0]) == pdf

            invalid_month = await client.get("/api/invoices/2026-1.zip")
            assert invalid_month.status_code == 400
            empty_month = await client.get("/api/invoices/2026-09.zip")
            assert empty_month.status_code == 404

    asyncio.run(exercise_http_routes())
    asyncio.run(tesla._http.aclose())


def test_invoice_and_export_routes_require_configured_app_password(settings, tmp_path, monkeypatch):
    """Die globale Basic-Auth-Middleware muss auch Rechnungs- und Export-Endpunkte abdecken."""
    protected_settings = dataclasses.replace(
        settings,
        data_dir=tmp_path,
        force_demo=False,
        tesla_client_id="test-client",
        tesla_client_secret="test-secret",
        app_password="test-password",
    )
    monkeypatch.setattr(main, "settings", protected_settings)
    monkeypatch.setattr(main, "db", DB(tmp_path / "auth-test.db"))

    paths = (
        "/api/export.csv",
        "/api/invoice/nonexistent-session",
        "/api/invoice/nonexistent-session/pages",
        "/api/invoice/nonexistent-session/page/1.png",
        "/api/invoices/2026-10.zip",
    )
    auth = "Basic " + __import__("base64").b64encode(b"tester:test-password").decode("ascii")

    async def exercise_auth():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for path in paths:
                response = await client.get(path)
                assert response.status_code == 401, f"{path} was not protected"

                authenticated = await client.get(path, headers={"Authorization": auth})
                assert authenticated.status_code != 401, f"{path} rejected valid credentials"

    asyncio.run(exercise_auth())

"""End-to-end Tesla sync checks for standalone mode without Home Assistant."""
import asyncio
import dataclasses
import time
from pathlib import Path

import httpx
from fpdf import FPDF

from app import main
from app.db import DB
from app.homeassistant import HAClient
from app.sync import SyncService
from app.tesla import TeslaClient

from test_networks import SUPERCHARGER_RAW


def invoice_pdf() -> bytes:
    doc = FPDF()
    doc.add_page()
    doc.set_font("Helvetica", size=10)
    doc.cell(0, 8, "Tesla invoice")
    doc.ln()
    doc.cell(0, 8, "Rechnungsnummer 4020P0000067890")
    return bytes(doc.output())


def test_tesla_history_invoice_and_export_work_without_home_assistant(settings, tmp_path, monkeypatch):
    """Mock Tesla's HTTP API, persist the session/PDF locally, and serve both artifacts."""
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
    sync = SyncService(settings, database, tesla, ha)

    assert asyncio.run(sync.sync_once()) == 1
    stored = database.session("standalone-session-42")
    assert stored is not None
    assert stored["push_state"] == "backfill"
    assert stored["kwh"] == 6.05
    assert stored["invoices"][0]["id"] == "invoice-42"
    assert (tmp_path / "invoices" / "standalone-session-42.pdf").read_bytes() == pdf
    assert database.kv_get("last_sync") is not None
    assert len(requests) == 2
    assert all(request.headers.get("Authorization") == "Bearer test-access-token" for request in requests)

    # Reopen the SQLite database to prove that the imported data survives a process restart.
    reopened = DB(database_path)
    assert reopened.session("standalone-session-42")["total"] == stored["total"]

    # Exercise the same invoice and CSV response handlers used by the HTTP routes.
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

    asyncio.run(tesla._http.aclose())

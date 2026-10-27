import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from fpdf import FPDF
from pypdf import PdfReader

from app import monthpdf
from app.main import app


def _invoice() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Tesla invoice")
    return bytes(pdf.output())


SESSIONS = [
    {"session_id": "1", "vin": "TESTVIN0000000001", "site": "Bad Homburg, Germany", "start_ts": "2026-09-29T19:36:57+00:00",
     "kwh": 58.112, "price": 0.2177, "total": 12.65, "net_total": 10.63, "credit": 13.5, "invoices": [{"id": "a"}]},
    {"session_id": "2", "vin": "TESTVIN0000000001", "site": "IONITY Musterstadt", "network": "multipass",
     "start_ts": "2026-09-30T10:00:00+00:00", "kwh": 20.0, "price": 0.59, "total": 11.8, "net_total": 9.92,
     "credit": 0.0, "invoices": []},
]


def test_cover_and_merge():
    cover = monthpdf.cover("2026-09", SESSIONS, lang="de", tz=ZoneInfo("Europe/Berlin"), currency="EUR",
                           home={"kwh": 42.0, "cost": 13.02}, distance=1234, unit="km",
                           now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    text = PdfReader(io.BytesIO(cover)).pages[0].extract_text()
    for needle in ("Ladekosten September 2026", "TESTVIN0000000001", "29.09.2026", "Bad Homburg",
                   "MultiPass", "13,50 EUR", "24,45 EUR", "20,55 EUR", "42,0 kWh", "1.234 km",
                   "Anhang: 1 Rechnung", "Für 1 Ladung"):
        assert needle in text, needle
    merged = monthpdf.merge(cover, [_invoice()])
    assert len(PdfReader(io.BytesIO(merged)).pages) == 2


def test_report_endpoint_in_demo():
    with TestClient(app) as client:
        d = client.get("/api/dashboard").json()
        month = d["month"]["key"]
        r = client.get(f"/api/report/{month}.pdf")
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
        assert PdfReader(io.BytesIO(r.content)).pages[0].extract_text().startswith("Charging costs")
        assert client.get("/api/report/1999-01.pdf").status_code == 404
        assert client.get("/api/report/oops.pdf").status_code == 400

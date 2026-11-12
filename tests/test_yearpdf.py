import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app import yearpdf
from app.main import app

TZ = ZoneInfo("Europe/Berlin")
SESSIONS = [
    {"session_id": "1", "vin": "TESTVIN0000000001", "start_ts": "2026-01-10T10:00:00+00:00",
     "kwh": 40.0, "total": 20.0, "net_total": 16.81, "credit": 0.0},
    {"session_id": "2", "vin": "TESTVIN0000000001", "start_ts": "2026-01-20T10:00:00+00:00",
     "kwh": 10.5, "total": 5.25, "net_total": 4.41, "credit": 2.0},
    {"session_id": "3", "vin": "TESTVIN0000000001", "start_ts": "2026-03-05T10:00:00+00:00", "network": "multipass",
     "kwh": 20.0, "total": 11.8, "net_total": 9.92, "credit": 0.0},
    # New Year's Eve 23:30 UTC is already January in Berlin: it belongs to 2027.
    {"session_id": "4", "vin": "TESTVIN0000000001", "start_ts": "2026-12-31T23:30:00+00:00",
     "kwh": 30.0, "total": 15.0, "net_total": 12.61, "credit": 0.0},
    {"session_id": "5", "vin": "TESTVIN0000000001", "start_ts": "2025-06-01T10:00:00+00:00",
     "kwh": 99.0, "total": 50.0, "net_total": 42.02, "credit": 0.0},
    # Not billed yet: no total, so it is in no report.
    {"session_id": "6", "vin": "TESTVIN0000000001", "start_ts": "2026-04-01T10:00:00+00:00", "kwh": 5.0, "total": None},
]


def test_years_and_month_rows():
    assert yearpdf.years(SESSIONS, TZ) == [2027, 2026, 2025]
    rows = yearpdf.month_rows(2026, SESSIONS, TZ)
    assert [r["key"] for r in rows] == ["2026-01", "2026-03"]
    january = rows[0]
    assert january["sessions"] == 2 and january["kwh"] == 50.5
    assert january["gross"] == 25.25 and january["net"] == 21.22 and january["vat"] == 4.03
    assert january["credit"] == 2.0
    assert rows[1]["multipass_sessions"] == 1 and rows[1]["multipass_cost"] == 11.8


def test_month_without_net_leaves_net_and_vat_open():
    sessions = [*SESSIONS, {"session_id": "7", "start_ts": "2026-03-06T10:00:00+00:00",
                            "kwh": 1.0, "total": 1.0, "net_total": None}]
    march = yearpdf.month_rows(2026, sessions, TZ)[1]
    assert march["net"] is None and march["vat"] is None and march["gross"] == 12.8
    text = PdfReader(io.BytesIO(yearpdf.cover(2026, sessions, lang="de", tz=TZ, currency="EUR"))).pages[0].extract_text()
    assert "noch keine Abrechnung" in text


def test_cover_de():
    data = yearpdf.cover(2026, SESSIONS, lang="de", tz=TZ, currency="EUR", home={"kwh": 420.0, "cost": 130.2},
                         now=datetime(2027, 1, 2, tzinfo=timezone.utc))
    pages = PdfReader(io.BytesIO(data)).pages
    assert len(pages) == 1
    text = pages[0].extract_text()
    for needle in ("Ladekosten 2026", "02.01.2027", "TESTVIN0000000001", "Januar", "März", "Summe",
                   "70,5", "37,05 EUR", "31,14 EUR", "5,91 EUR", "2,00 EUR",
                   "Davon MultiPass (fremde Ladenetze): 1 Ladung, 11,80 EUR",
                   "Laden zu Hause (Wallbox-Zähler, kein Beleg): 420,0 kWh, 130,20 EUR", "Monatsberichten"):
        assert needle in text, needle
    assert "Dezember" not in text and "99,0" not in text


def test_cover_en():
    text = PdfReader(io.BytesIO(yearpdf.cover(2026, SESSIONS, lang="en", tz=TZ, currency="EUR"))).pages[0].extract_text()
    for needle in ("Charging costs 2026", "January", "March", "Total", "Gross", "month reports"):
        assert needle in text, needle


def test_year_endpoints_in_demo():
    with TestClient(app) as client:
        d = client.get("/api/dashboard").json()
        assert d["years"] and d["years"] == sorted(d["years"], reverse=True)
        year = d["years"][0]
        pdf = client.get(f"/api/year/{year}.pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
        assert f"-{year}.pdf" in pdf.headers["content-disposition"]
        assert client.get(f"/api/year/{year}/pages").json()["pages"] == 1
        assert client.get(f"/api/year/{year}/page/1.png").headers["content-type"] == "image/png"
        assert client.get(f"/api/year/{year}/page/2.png").status_code == 404
        assert client.get("/api/year/1999.pdf").status_code == 400
        assert client.get("/api/year/2001.pdf").status_code == 404
        assert client.get("/api/year/abc.pdf").status_code == 422

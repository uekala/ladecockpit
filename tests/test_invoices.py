import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from fpdf import FPDF

from app import invoices
from app.db import DB
from app.networks import MULTIPASS, SUPERCHARGER, classify
from app.sync import SyncService
from app.tesla import parse_session

from test_networks import SUPERCHARGER_RAW


def pdf(*lines):
    doc = FPDF()
    doc.add_page()
    doc.set_font("Helvetica", size=10)
    for line in lines:
        doc.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(doc.output())


# Shape of real invoices (numbers and names made up)
MULTIPASS_PDF = pdf("Rechnung", "Tesla Germany GmbH", "Rechnungsnummer 4020MSP0000012345", "Rechnungsdatum 2026/10/31",
                    "Ladestation", "Musterstrasse 1, Neustadt", "Stromgebuehr 0.578708 / kWh 1.1660 kWh 19 0.67")
SUPERCHARGER_PDF = pdf("Rechnung", "Tesla Germany GmbH", "Rechnungsnummer 4020SCD0000067890",
                       "Supercharger Bergstadt, Germany", "Supercharging 0.31 / kWh 44.189 kWh")


def test_network_from_the_invoice_number():
    assert invoices.network_from_pdf(MULTIPASS_PDF) == MULTIPASS
    assert invoices.network_from_pdf(SUPERCHARGER_PDF) == SUPERCHARGER
    assert invoices.network_from_pdf(pdf("Rechnung", "Kundennummer 3005038484", "USt-IdNr: DE265761887")) == invoices.UNKNOWN
    assert invoices.network_from_pdf(b"not a pdf") == invoices.UNKNOWN


def test_msp_number_in_the_file_name():
    raw = {**SUPERCHARGER_RAW, "invoices": [{"contentId": "x", "fileName": "4020MSP0000012345.pdf", "invoiceType": "IMMEDIATE"}]}
    assert classify(raw)[0] == MULTIPASS


def store(db, sid, site, start, with_invoice=True):
    raw = {**SUPERCHARGER_RAW, "sessionId": sid, "siteLocationName": site,
           "chargeStartDateTime": start.isoformat(), "chargeStopDateTime": (start + timedelta(minutes=20)).isoformat(),
           "invoices": [{"contentId": f"c{sid}", "fileName": "inv.pdf", "invoiceType": "IMMEDIATE"}] if with_invoice else []}
    db.upsert_session(parse_session(raw), "backfill")


def test_the_invoice_has_the_last_word(db):
    now = datetime.now(timezone.utc)
    store(db, 1, "Brunnenhausstr. 46, Neustadt", now)
    store(db, 2, "Charging Station ALDI SÜD", now - timedelta(hours=1))
    assert {s["session_id"]: s["network"] for s in db.sessions()} == {"1": SUPERCHARGER, "2": MULTIPASS}
    db.set_invoice_network("1", MULTIPASS)
    db.set_invoice_network("2", SUPERCHARGER)          # a Supercharger on a supermarket car park
    got = {s["session_id"]: (s["network"], s["network_reason"]) for s in db.sessions()}
    assert got == {"1": (MULTIPASS, "invoice number"), "2": (SUPERCHARGER, "invoice number")}
    db.set_invoice_network("1", invoices.UNKNOWN)       # the invoice did not tell: the hints decide
    assert db.session("1")["network"] == SUPERCHARGER


def test_older_databases_get_the_column(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE sessions (session_id TEXT PRIMARY KEY, invoices TEXT, raw TEXT, start_ts TEXT, "
                "first_seen TEXT NOT NULL, push_state TEXT NOT NULL DEFAULT 'new')")
    con.commit()
    con.close()
    DB(path)
    cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(sessions)")}
    assert "invoice_network" in cols


class InvoiceTesla:
    def __init__(self, files):
        self.files = files
        self.asked = []

    async def invoice_pdf(self, content_id):
        self.asked.append(content_id)
        data = self.files[content_id]
        if isinstance(data, Exception):
            raise data
        return data


def test_sync_reads_new_invoices_once(settings, db):
    now = datetime.now(timezone.utc)
    store(db, 1, "Neustadt - KiK", now)
    store(db, 2, "Bergstadt, Germany", now - timedelta(days=1))
    store(db, 3, "Bergstadt, Germany", now - timedelta(days=2), with_invoice=False)   # no invoice yet
    store(db, 4, "Bergstadt, Germany", now - timedelta(days=400))                     # too old to bother
    tesla = InvoiceTesla({"c1": MULTIPASS_PDF, "c2": SUPERCHARGER_PDF})
    sync = SyncService(settings, db, tesla, None)
    assert asyncio.run(sync.check_invoices()) == 2
    assert asyncio.run(sync.check_invoices()) == 0                                   # each invoice once
    assert sorted(tesla.asked) == ["c1", "c2"]
    assert db.session("1")["network"] == MULTIPASS and db.session("2")["network"] == SUPERCHARGER
    assert (settings.data_dir / "invoices" / "1.pdf").read_bytes() == MULTIPASS_PDF   # kept for viewing


def test_sync_stops_when_tesla_fails_and_tries_again(settings, db):
    now = datetime.now(timezone.utc)
    store(db, 1, "Neustadt - KiK", now)
    tesla = InvoiceTesla({"c1": RuntimeError("HTTP 503")})
    sync = SyncService(settings, db, tesla, None)
    assert asyncio.run(sync.check_invoices()) == 0
    assert db.session("1")["invoice_network"] is None
    tesla.files["c1"] = MULTIPASS_PDF
    assert asyncio.run(sync.check_invoices()) == 1
    assert json.loads(json.dumps(db.session("1")))["network"] == MULTIPASS

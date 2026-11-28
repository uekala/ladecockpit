"""Rechnungs-PDFs: einmal von Tesla geholt und aufbewahrt, und was sie über das Netz verraten.

Die Ladehistorie hat kein Feld, das das Netz nennt, die Rechnung aber schon: Tesla rechnet
Fremdladen (MultiPass) als Mobilitätsdienstleister ab, und diese Rechnungsnummern tragen „MSP“,
z. B. 4020MSP0000019797. Supercharger-Rechnungen haben eine Nummer ohne. Die Rechnung einer
Ladung entscheidet also, ob es eine Supercharger- oder eine MultiPass-Ladung war, auch an
Stationen, deren Name nichts verrät („Brunnenhausstr. 46, Neustadt“).
"""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from pypdf import PdfReader

from .networks import MULTIPASS, SUPERCHARGER, invoice_series
from .tesla import TeslaError

log = logging.getLogger("ladecockpit.invoices")

UNKNOWN = "unknown"  # geprüft, aber die Rechnung hat es nicht verraten


def cache_path(data_dir: Path, session_id: str) -> Path:
    folder = data_dir / "invoices"
    folder.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return folder / f"{safe_id}.pdf"


def is_pdf(data: bytes) -> bool:
    """Ob die Bytes wie ein PDF beginnen (vor dem Kopf können ein paar verirrte Bytes stehen)."""
    return b"%PDF-" in data[:1024]


def _cached_pdf_ok(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return is_pdf(f.read(1024))
    except OSError:
        return False


async def pdf_path(tesla, data_dir: Path, session: dict) -> Path:
    """Pfad des zwischengespeicherten Rechnungs-PDFs einer Ladung (beim ersten Bedarf von Tesla geholt).

    Nur echte PDFs werden behalten und in einem Schritt geschrieben: Eine Antwort, die kein PDF ist,
    oder ein abgebrochenes Schreiben darf nicht im Cache bleiben und Monatsbericht und Rechnungsansicht
    dauerhaft kaputt machen. Eine zwischengespeicherte Datei, die kein PDF ist, wird neu geholt."""
    path = cache_path(data_dir, session["session_id"])
    if path.exists() and not _cached_pdf_ok(path):
        log.warning("Cached invoice of session %s is not a PDF – fetching it again", session["session_id"])
        path.unlink(missing_ok=True)
    if not path.exists():
        data = await tesla.invoice_pdf(session["invoices"][0]["id"])
        if not is_pdf(data):
            raise TeslaError("Tesla did not return a PDF for this invoice.")
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return path


def pdf_text(data: bytes) -> str:
    """Text der ersten Seiten eines PDFs ("", wenn es sich nicht lesen lässt)."""
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages[:2])
    except Exception:
        return ""


def network_from_text(text: str) -> str:
    """MULTIPASS oder SUPERCHARGER aus dem Text einer Rechnung, oder UNKNOWN, wenn sie es nicht verrät."""
    numbers = re.findall(r"(?:Rechnungsnummer|Invoice\s*(?:Number|No\.?))\s*:?\s*(\S+)", text, re.I)
    series = invoice_series(numbers[0] if numbers else text)
    if series == "MSP":
        return MULTIPASS
    if series == "P" or re.search(r"\bsupercharg", text, re.I):
        return SUPERCHARGER
    return UNKNOWN


def network_from_pdf(data: bytes) -> str:
    """MULTIPASS oder SUPERCHARGER aus einem Rechnungs-PDF, oder UNKNOWN, wenn es nichts verrät."""
    return network_from_text(pdf_text(data))

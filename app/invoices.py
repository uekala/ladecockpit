"""Invoice PDFs: fetched from Tesla once and kept, and what they tell about the network.

The charging history has no field that names the network, but the invoice does: Tesla bills
third-party charging (MultiPass) as a mobility service provider, and those invoice numbers carry
"MSP", e.g. 4020MSP0000019797. Supercharger invoices have a number without it. So a session's
invoice settles whether it was a Supercharger or a MultiPass session, also at stations whose
name gives nothing away ("Brunnenhausstr. 46, Neustadt").
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

UNKNOWN = "unknown"  # checked, but the invoice did not tell


def cache_path(data_dir: Path, session_id: str) -> Path:
    folder = data_dir / "invoices"
    folder.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return folder / f"{safe_id}.pdf"


def is_pdf(data: bytes) -> bool:
    """Whether the bytes start like a PDF (the header may follow a few stray bytes)."""
    return b"%PDF-" in data[:1024]


def _cached_pdf_ok(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return is_pdf(f.read(1024))
    except OSError:
        return False


async def pdf_path(tesla, data_dir: Path, session: dict) -> Path:
    """Path of the cached invoice PDF of a session (fetched from Tesla on first use).

    Only real PDFs are kept, and written in one step: an answer that is not a PDF, or a write that
    was cut short, must not stay in the cache and break the month report and the invoice view for good.
    A cached file that is not a PDF is fetched again."""
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
    """Text of the first pages of a PDF ("" when it cannot be read)."""
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages[:2])
    except Exception:  # noqa: BLE001 – a broken or unusual PDF just tells nothing
        return ""


def network_from_text(text: str) -> str:
    """MULTIPASS or SUPERCHARGER from the text of an invoice, or UNKNOWN when it does not tell."""
    numbers = re.findall(r"(?:Rechnungsnummer|Invoice\s*(?:Number|No\.?))\s*:?\s*(\S+)", text, re.I)
    series = invoice_series(numbers[0] if numbers else text)
    if series == "MSP":
        return MULTIPASS
    if series == "P" or re.search(r"\bsupercharg", text, re.I):
        return SUPERCHARGER
    return UNKNOWN


def network_from_pdf(data: bytes) -> str:
    """MULTIPASS or SUPERCHARGER from an invoice PDF, or UNKNOWN when it does not tell."""
    return network_from_text(pdf_text(data))

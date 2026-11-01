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

from .networks import MULTIPASS, SUPERCHARGER

log = logging.getLogger("ladecockpit.invoices")

UNKNOWN = "unknown"  # checked, but the invoice did not tell
# Invoice numbers: digits, a short series code, digits – 4020MSP0000019797
_NUMBER = re.compile(r"\b\d{3,5}([A-Z]{2,5})\d{6,}\b")


def cache_path(data_dir: Path, session_id: str) -> Path:
    folder = data_dir / "invoices"
    folder.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return folder / f"{safe_id}.pdf"


async def pdf_path(tesla, data_dir: Path, session: dict) -> Path:
    """Path of the cached invoice PDF of a session (fetched from Tesla on first use)."""
    path = cache_path(data_dir, session["session_id"])
    if not path.exists():
        path.write_bytes(await tesla.invoice_pdf(session["invoices"][0]["id"]))
    return path


def network_from_pdf(data: bytes) -> str:
    """MULTIPASS or SUPERCHARGER from an invoice PDF, or UNKNOWN when it does not tell."""
    try:
        text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages[:2])
    except Exception:  # noqa: BLE001 – a broken or unusual PDF just tells nothing
        return UNKNOWN
    numbers = [m.group(1) for m in _NUMBER.finditer(text)]
    if any("MSP" in series for series in numbers):
        return MULTIPASS
    if numbers or re.search(r"\bsupercharg", text, re.I):
        return SUPERCHARGER
    return UNKNOWN

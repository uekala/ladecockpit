"""One PDF per month for tax or an employer: a cover sheet with all sessions (net, VAT, gross,
credits) followed by Tesla's invoices."""
from __future__ import annotations

import io
from datetime import datetime

from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

from . import i18n

TEXT = {
    "de": {
        "title": "Ladekosten {month}", "created": "Erstellt am {date} mit Ladecockpit aus den Tesla-Rechnungen.",
        "vehicle": "Fahrzeug (VIN): {vin}", "date": "Datum", "site": "Standort", "kwh": "kWh",
        "price": "/kWh", "net": "Netto", "vat": "MwSt.", "gross": "Brutto", "credit": "Gutschrift",
        "total": "Summe", "notes": "Beträge laut den angehängten Tesla-Rechnungen. Tesla-Gutschriften sind im "
        "Bruttobetrag bereits abgezogen. Netto und MwSt. stammen aus Teslas Abrechnung.",
        "home": "Laden zu Hause (Wallbox-Zähler, kein Beleg): {kwh} kWh, {cost}",
        "home_kwh": "Laden zu Hause (Wallbox-Zähler, kein Beleg): {kwh} kWh",
        "distance": "Gefahrene Strecke laut Kilometerstand: {dist} {unit}",
        "invoices": "Anhang: {n} Rechnungen", "no_invoice": "Für {n} Ladungen liegt noch keine Rechnung vor.",
        "invoices_one": "Anhang: 1 Rechnung", "no_invoice_one": "Für 1 Ladung liegt noch keine Rechnung vor.",
        "multipass": "MultiPass",
    },
    "en": {
        "title": "Charging costs {month}", "created": "Created on {date} with Ladecockpit from the Tesla invoices.",
        "vehicle": "Vehicle (VIN): {vin}", "date": "Date", "site": "Site", "kwh": "kWh",
        "price": "/kWh", "net": "Net", "vat": "VAT", "gross": "Gross", "credit": "Credit",
        "total": "Total", "notes": "Amounts as in the attached Tesla invoices. Tesla credits are already "
        "deducted from the gross amount. Net and VAT come from Tesla's billing.",
        "home": "Charging at home (wallbox meter, no receipt): {kwh} kWh, {cost}",
        "home_kwh": "Charging at home (wallbox meter, no receipt): {kwh} kWh",
        "distance": "Distance driven per odometer: {dist} {unit}",
        "invoices": "Attached: {n} invoices", "no_invoice": "{n} sessions have no invoice yet.",
        "invoices_one": "Attached: 1 invoice", "no_invoice_one": "1 session has no invoice yet.",
        "multipass": "MultiPass",
    },
}


def _t(lang: str, key: str, **kw) -> str:
    return (TEXT.get(lang) or TEXT["en"])[key].format(**kw)


def _latin(text: str) -> str:
    """The built-in PDF fonts only know Latin-1."""
    text = text.replace("€", "EUR").replace("–", "-").replace("−", "-").replace("’", "'")
    return text.encode("latin-1", "replace").decode("latin-1")


def cover(month_key: str, sessions: list[dict], *, lang: str, tz, currency: str,
          home: dict | None = None, distance: float | None = None, unit: str = "km",
          now: datetime | None = None) -> bytes:
    money = lambda v: "" if v is None else i18n.money(lang, v, currency)  # noqa: E731
    num = lambda v, d=1: "" if v is None else i18n.num(lang, v, d)  # noqa: E731
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, _latin(_t(lang, "title", month=i18n.month_label(lang, month_key))), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    created = (now or datetime.now(tz)).astimezone(tz)
    pdf.cell(0, 5, _latin(_t(lang, "created", date=created.strftime("%d.%m.%Y" if lang == "de" else "%Y-%m-%d"))),
             new_x="LMARGIN", new_y="NEXT")
    vins = sorted({s.get("vin") for s in sessions if s.get("vin") and s.get("vin") != "DEMO"})
    if vins:
        pdf.cell(0, 5, _latin(_t(lang, "vehicle", vin=", ".join(vins))), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    widths = [20, 52, 16, 18, 20, 18, 22, 22]
    heads = [_t(lang, k) for k in ("date", "site", "kwh", "price", "net", "vat", "gross", "credit")]
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_fill_color(235, 238, 240)
    for i, (w, h) in enumerate(zip(widths, heads)):
        pdf.cell(w, 7, _latin(h), border="B", align="L" if i < 2 else "R", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8.5)
    sums = {"kwh": 0.0, "net": 0.0, "vat": 0.0, "gross": 0.0, "credit": 0.0}
    missing_net = False
    for s in sessions:
        start = datetime.fromisoformat(s["start_ts"]).astimezone(tz) if s.get("start_ts") else None
        gross = s.get("total")
        net = s.get("net_total")
        vat = round(gross - net, 2) if gross is not None and net is not None else None
        missing_net = missing_net or net is None
        site = s.get("site") or ""
        if s.get("network") == "multipass":
            site = f"{_t(lang, 'multipass')} · {site}"
        row = [start.strftime("%d.%m.%Y" if lang == "de" else "%Y-%m-%d") if start else "", site[:34],
               num(s.get("kwh")), money(s.get("price")), money(net), money(vat), money(gross),
               money(s.get("credit")) if s.get("credit") else ""]
        for i, (w, v) in enumerate(zip(widths, row)):
            pdf.cell(w, 6, _latin(v), border="B", align="L" if i < 2 else "R")
        pdf.ln()
        sums["kwh"] += s.get("kwh") or 0.0
        sums["gross"] += gross or 0.0
        sums["credit"] += s.get("credit") or 0.0
        if net is not None:
            sums["net"] += net
            sums["vat"] += vat
    pdf.set_font("Helvetica", "B", 8.5)
    total_row = [_t(lang, "total"), "", num(sums["kwh"]), "",
                 "" if missing_net else money(sums["net"]), "" if missing_net else money(sums["vat"]),
                 money(sums["gross"]), money(sums["credit"]) if sums["credit"] else ""]
    for i, (w, v) in enumerate(zip(widths, total_row)):
        pdf.cell(w, 7, _latin(v), align="L" if i < 2 else "R")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 9)
    if home and home.get("kwh"):
        key = "home" if home.get("cost") is not None else "home_kwh"
        pdf.multi_cell(0, 5, _latin(_t(lang, key, kwh=num(home["kwh"]), cost=money(home.get("cost")))),
                       new_x="LMARGIN", new_y="NEXT")
    if distance:
        pdf.multi_cell(0, 5, _latin(_t(lang, "distance", dist=num(distance, 0), unit=unit)), new_x="LMARGIN", new_y="NEXT")
    with_invoice = sum(1 for s in sessions if s.get("invoices"))
    pdf.multi_cell(0, 5, _latin(_t(lang, "invoices_one" if with_invoice == 1 else "invoices", n=with_invoice)),
                   new_x="LMARGIN", new_y="NEXT")
    open_ = len(sessions) - with_invoice
    if open_:
        pdf.multi_cell(0, 5, _latin(_t(lang, "no_invoice_one" if open_ == 1 else "no_invoice", n=open_)),
                       new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 4.5, _latin(_t(lang, "notes")), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def merge(cover_pdf: bytes, invoices: list[bytes]) -> bytes:
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(cover_pdf)))
    for data in invoices:
        writer.append(PdfReader(io.BytesIO(data)))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

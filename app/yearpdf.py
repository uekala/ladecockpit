"""One page per year for tax or an employer: a line per month with sessions, kWh, net, VAT,
gross and credits, and the totals of the year. The invoices themselves are in the month reports."""
from __future__ import annotations

from datetime import datetime

from fpdf import FPDF

from . import i18n
from .monthpdf import _latin

TEXT = {
    "de": {
        "title": "Ladekosten {year}", "created": "Erstellt am {date} mit Ladecockpit aus den Tesla-Rechnungen.",
        "vehicle": "Fahrzeug (VIN): {vin}", "month": "Monat", "sessions": "Ladungen", "kwh": "kWh",
        "net": "Netto", "vat": "MwSt.", "gross": "Brutto", "credit": "Gutschrift", "total": "Summe",
        "multipass": "Davon MultiPass (fremde Ladenetze): {n} Ladungen, {cost}",
        "multipass_one": "Davon MultiPass (fremde Ladenetze): 1 Ladung, {cost}",
        "home": "Laden zu Hause (Wallbox-Zähler, kein Beleg): {kwh} kWh, {cost}",
        "home_kwh": "Laden zu Hause (Wallbox-Zähler, kein Beleg): {kwh} kWh",
        "notes": "Beträge laut Teslas Rechnungen. Tesla-Gutschriften sind im Bruttobetrag bereits abgezogen. "
        "Netto und MwSt. stammen aus Teslas Abrechnung. Die Rechnungen selbst hängen an den Monatsberichten.",
        "no_net": "Für mindestens eine Ladung liegt noch keine Abrechnung mit Netto und MwSt. vor; "
        "diese Spalten bleiben für den Monat und die Summe leer.",
    },
    "en": {
        "title": "Charging costs {year}", "created": "Created on {date} with Ladecockpit from the Tesla invoices.",
        "vehicle": "Vehicle (VIN): {vin}", "month": "Month", "sessions": "Sessions", "kwh": "kWh",
        "net": "Net", "vat": "VAT", "gross": "Gross", "credit": "Credit", "total": "Total",
        "multipass": "Of which MultiPass (third-party networks): {n} sessions, {cost}",
        "multipass_one": "Of which MultiPass (third-party networks): 1 session, {cost}",
        "home": "Charging at home (wallbox meter, no receipt): {kwh} kWh, {cost}",
        "home_kwh": "Charging at home (wallbox meter, no receipt): {kwh} kWh",
        "notes": "Amounts as in Tesla's invoices. Tesla credits are already deducted from the gross amount. "
        "Net and VAT come from Tesla's billing. The invoices themselves are attached to the month reports.",
        "no_net": "At least one session has no billing with net and VAT yet; "
        "those columns stay empty for that month and the total.",
    },
}


def _t(lang: str, key: str, **kw) -> str:
    return (TEXT.get(lang) or TEXT["en"])[key].format(**kw)


def in_year(session: dict, year: int, tz) -> bool:
    """Whether a billed session started in this year (local time)."""
    if not session.get("start_ts") or session.get("total") is None:
        return False
    return datetime.fromisoformat(session["start_ts"]).astimezone(tz).year == year


def years(sessions: list[dict], tz) -> list[int]:
    """Years with billed sessions, newest first."""
    found = {datetime.fromisoformat(s["start_ts"]).astimezone(tz).year
             for s in sessions if s.get("start_ts") and s.get("total") is not None}
    return sorted(found, reverse=True)


def month_rows(year: int, sessions: list[dict], tz) -> list[dict]:
    """Totals per month of the year, only months with sessions. net and vat are None for a month
    in which a session has no net amount yet."""
    rows: dict[int, dict] = {}
    for s in sessions:
        if not in_year(s, year, tz):
            continue
        month = datetime.fromisoformat(s["start_ts"]).astimezone(tz).month
        row = rows.setdefault(month, {"key": f"{year}-{month:02d}", "sessions": 0, "kwh": 0.0, "net": 0.0,
                                      "vat": 0.0, "gross": 0.0, "credit": 0.0, "complete": True,
                                      "multipass_sessions": 0, "multipass_cost": 0.0})
        gross, net = s["total"], s.get("net_total")
        row["sessions"] += 1
        row["kwh"] += s.get("kwh") or 0.0
        row["gross"] += gross
        row["credit"] += s.get("credit") or 0.0
        if net is None:
            row["complete"] = False
        else:
            row["net"] += net
            row["vat"] += round(gross - net, 2)
        if s.get("network") == "multipass":
            row["multipass_sessions"] += 1
            row["multipass_cost"] += gross
    out = []
    for month in sorted(rows):
        row = rows[month]
        complete = row.pop("complete")
        for field in ("kwh", "net", "vat", "gross", "credit", "multipass_cost"):
            row[field] = round(row[field], 2)
        if not complete:
            row["net"] = row["vat"] = None
        out.append(row)
    return out


def cover(year: int, sessions: list[dict], *, lang: str, tz, currency: str,
          home: dict | None = None, now: datetime | None = None) -> bytes:
    money = lambda v: "" if v is None else i18n.money(lang, v, currency)  # noqa: E731
    num = lambda v, d=1: "" if v is None else i18n.num(lang, v, d)  # noqa: E731
    rows = month_rows(year, sessions, tz)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, _latin(_t(lang, "title", year=year)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    created = (now or datetime.now(tz)).astimezone(tz)
    pdf.cell(0, 5, _latin(_t(lang, "created", date=created.strftime("%d.%m.%Y" if lang == "de" else "%Y-%m-%d"))),
             new_x="LMARGIN", new_y="NEXT")
    vins = sorted({s.get("vin") for s in sessions if in_year(s, year, tz) and s.get("vin") and s.get("vin") != "DEMO"})
    if vins:
        pdf.cell(0, 5, _latin(_t(lang, "vehicle", vin=", ".join(vins))), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    widths = [34, 22, 24, 28, 26, 28, 26]
    heads = [_t(lang, k) for k in ("month", "sessions", "kwh", "net", "vat", "gross", "credit")]
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_fill_color(235, 238, 240)
    for i, (w, h) in enumerate(zip(widths, heads)):
        pdf.cell(w, 7, _latin(h), border="B", align="L" if i == 0 else "R", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8.5)
    complete = all(r["net"] is not None for r in rows)
    for r in rows:
        line = [i18n.month_label(lang, r["key"], with_year=False), str(r["sessions"]), num(r["kwh"]),
                money(r["net"]), money(r["vat"]), money(r["gross"]), money(r["credit"]) if r["credit"] else ""]
        for i, (w, v) in enumerate(zip(widths, line)):
            pdf.cell(w, 6, _latin(v), border="B", align="L" if i == 0 else "R")
        pdf.ln()
    pdf.set_font("Helvetica", "B", 8.5)
    credit = sum(r["credit"] for r in rows)
    total = [_t(lang, "total"), str(sum(r["sessions"] for r in rows)), num(sum(r["kwh"] for r in rows)),
             money(sum(r["net"] for r in rows)) if complete else "",
             money(sum(r["vat"] for r in rows)) if complete else "",
             money(sum(r["gross"] for r in rows)), money(credit) if credit else ""]
    for i, (w, v) in enumerate(zip(widths, total)):
        pdf.cell(w, 7, _latin(v), align="L" if i == 0 else "R")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 9)
    multipass = sum(r["multipass_sessions"] for r in rows)
    if multipass:
        pdf.multi_cell(0, 5, _latin(_t(lang, "multipass_one" if multipass == 1 else "multipass", n=multipass,
                                       cost=money(sum(r["multipass_cost"] for r in rows)))),
                       new_x="LMARGIN", new_y="NEXT")
    if home and home.get("kwh"):
        key = "home" if home.get("cost") is not None else "home_kwh"
        pdf.multi_cell(0, 5, _latin(_t(lang, key, kwh=num(home["kwh"]), cost=money(home.get("cost")))),
                       new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 4.5, _latin(_t(lang, "notes")), new_x="LMARGIN", new_y="NEXT")
    if not complete:
        pdf.multi_cell(0, 4.5, _latin(_t(lang, "no_net")), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())

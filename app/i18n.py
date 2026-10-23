"""Small translation helper for texts the backend generates (insights, forecast, HA event)."""
from __future__ import annotations

MONTHS = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember"],
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
}
WEEKDAYS = {
    "de": ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "CAD": "CA$", "AUD": "A$", "JPY": "¥"}

# Time windows for the price radar (start time of a session, local time)
SLOTS = {
    "de": [("Nachts", "0–6 Uhr"), ("Morgens", "6–11 Uhr"), ("Mittags", "11–16 Uhr"),
           ("Nachmittags", "16–20 Uhr"), ("Abends", "20–24 Uhr")],
    "en": [("Night", "0–6 h"), ("Morning", "6–11 h"), ("Midday", "11–16 h"),
           ("Afternoon", "16–20 h"), ("Evening", "20–24 h")],
}

TEXTS = {
    "de": {
        "fc_no_soc": "Kein Akkustand aus Home Assistant – Prognose nicht möglich.",
        "fc_too_little": "Noch zu wenig Akku-Verlauf für eine Prognose.",
        "fc_flat": "Der Akku sinkt gerade kaum – kein Ladestopp in Sicht.",
        "fc_today": "Heute laden – der Akku erreicht bald {floor} %.",
        "fc_tomorrow": "Morgen laden einplanen.",
        "fc_latest": "Spätestens {date} laden – in etwa {days} Tagen.",
        "in_slot_best": "{label} ({range}) lädst du am günstigsten: Ø {price}/kWh, {diff}/kWh unter deinem Schnitt.",
        "in_slot_flat": "Die Uhrzeit macht bei deinen Ladungen bisher kaum einen Unterschied.",
        "in_slot_wait": "Nach ein paar weiteren Ladungen zeigt der Preis-Radar, welche Uhrzeit für dich am günstigsten ist.",
        "in_site": "Am günstigsten warst du in {lo} (Ø {lo_price}/kWh), am teuersten in {hi} (Ø {hi_price}/kWh).",
        "in_idle_one": "Blockiergebühren bisher: {amount} bei 1 Ladung – rechtzeitig abstecken spart Geld.",
        "in_idle_many": "Blockiergebühren bisher: {amount} bei {n} Ladungen – rechtzeitig abstecken spart Geld.",
        "in_reference": "Mit dem Referenzpreis von {ref}/kWh wären es diesen Monat {ref_cost} gewesen – laut Rechnungen sind es {actual} ({sign}{delta}).",
        "fuel_default": "Sprit diesen Monat",
        "unknown_site": "Unbekannter Supercharger",
        "problem_title": "Ladecockpit",
        "problem_auth": "Die Tesla-Anmeldung ist abgelaufen. Öffne Ladecockpit und verbinde dich neu mit Tesla, sonst werden keine Rechnungen mehr gebucht.",
        "problem_sync": "Der Abgleich mit Tesla schlägt seit mehreren Versuchen fehl: {detail}",
        "problem_budget": "Das Monatsbudget für Tesla-Abfragen ist erreicht. Bis Monatsende werden keine Rechnungen mehr geholt.",
        "csv_header": "Datum;Start;Ende;Standort;kWh;Preis pro kWh;Ladekosten;Blockiergebühr;Summe;Währung;Ø kW;Ladung-ID",
    },
    "en": {
        "fc_no_soc": "No battery level from Home Assistant – no forecast possible.",
        "fc_too_little": "Not enough battery history for a forecast yet.",
        "fc_flat": "The battery is barely dropping – no charging stop in sight.",
        "fc_today": "Charge today – the battery will reach {floor} % soon.",
        "fc_tomorrow": "Plan to charge tomorrow.",
        "fc_latest": "Charge by {date} – in about {days} days.",
        "in_slot_best": "{label} ({range}) is your cheapest time: avg {price}/kWh, {diff}/kWh below your average.",
        "in_slot_flat": "Time of day hardly makes a difference for your sessions so far.",
        "in_slot_wait": "After a few more sessions the price radar shows which time of day is cheapest for you.",
        "in_site": "Cheapest so far: {lo} (avg {lo_price}/kWh). Most expensive: {hi} (avg {hi_price}/kWh).",
        "in_idle_one": "Idle fees so far: {amount} in 1 session – unplugging on time saves money.",
        "in_idle_many": "Idle fees so far: {amount} in {n} sessions – unplugging on time saves money.",
        "in_reference": "At your reference price of {ref}/kWh this month would have cost {ref_cost} – the invoices say {actual} ({sign}{delta}).",
        "fuel_default": "Fuel this month",
        "unknown_site": "Unknown Supercharger",
        "problem_title": "Ladecockpit",
        "problem_auth": "The Tesla sign-in expired. Open Ladecockpit and connect to Tesla again, otherwise no invoices are booked.",
        "problem_sync": "Syncing with Tesla has failed several times in a row: {detail}",
        "problem_budget": "The monthly budget for Tesla requests is used up. No invoices are fetched until next month.",
        "csv_header": "Date,Start,End,Site,kWh,Price per kWh,Charging cost,Idle fee,Total,Currency,Avg kW,Session ID",
    },
}


def t(lang: str, key: str, **kw) -> str:
    table = TEXTS.get(lang) or TEXTS["en"]
    return table.get(key, TEXTS["en"].get(key, key)).format(**kw)


def num(lang: str, value: float, digits: int = 1) -> str:
    s = f"{value:,.{digits}f}"
    if lang == "de":
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def symbol(currency: str | None) -> str:
    code = (currency or "EUR").upper()
    return CURRENCY_SYMBOLS.get(code, code)


def money(lang: str, value: float, currency: str | None, digits: int = 2) -> str:
    sym = symbol(currency)
    amount = num(lang, abs(value), digits)
    sign = "−" if value < 0 else ""
    if lang == "de" or len(sym) > 2:
        return f"{sign}{amount} {sym}"
    return f"{sign}{sym}{amount}"


def month_label(lang: str, key: str, with_year: bool = True) -> str:
    y, m = key.split("-")
    name = (MONTHS.get(lang) or MONTHS["en"])[int(m) - 1]
    return f"{name} {y}" if with_year else name


def weekday(lang: str, index: int) -> str:
    return (WEEKDAYS.get(lang) or WEEKDAYS["en"])[index]


def date_label(lang: str, dt) -> str:
    wd = weekday(lang, dt.weekday())
    if lang == "de":
        return f"{wd}, {dt:%d.%m.}"
    return f"{wd}, {dt:%b} {dt.day}"

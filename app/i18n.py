"""Kleine Übersetzungshilfe für Texte, die das Backend erzeugt (Hinweise, Prognose, HA-Event)."""
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

# Zeitfenster für das Preis-Radar (Startzeit einer Ladung, Ortszeit)
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
        "in_slot_best_few": "{label} ({range}) war bisher am günstigsten: Ø {price}/kWh, {diff}/kWh unter deinem Schnitt – allerdings erst {n}× geladen.",
        "in_slot_flat": "Die Uhrzeit macht bei deinen Ladungen bisher kaum einen Unterschied.",
        "in_tariff": "In {site} kostet nachts und früh (Nebenzeit) {off}/kWh, tagsüber {peak}/kWh. Hättest du deine {kwh} kWh aus der Hauptzeit an solchen Standorten nachts geladen, wären es {saving} weniger gewesen.",
        "in_slot_wait": "Nach ein paar weiteren Ladungen zeigt der Preis-Radar, welche Uhrzeit für dich am günstigsten ist.",
        "in_site": "Am günstigsten warst du in {lo} (Ø {lo_price}/kWh), am teuersten in {hi} (Ø {hi_price}/kWh).",
        "in_price_change": "Neuer Preis in {site}: Seit {since} kostet die kWh {now} statt {before} ({sign}{diff}/kWh). Ältere Ladungen dort fließen noch zum alten Preis in den Ø ein.",
        "in_network": "MultiPass-Ladungen ({n}) kosten dich im Schnitt {mp}/kWh, am Supercharger sind es {sc}/kWh.",
        "in_credit": "Tesla-Gutschriften haben bisher {amount} übernommen. Gezahlt hast du Ø {paid}/kWh, der Listenpreis lag bei Ø {listed}/kWh – Preisvergleiche nutzen den Listenpreis.",
        "in_idle_one": "Blockiergebühren bisher: {amount} bei 1 Ladung – rechtzeitig abstecken spart Geld.",
        "in_idle_many": "Blockiergebühren bisher: {amount} bei {n} Ladungen – rechtzeitig abstecken spart Geld.",
        "in_reference": "Mit dem Referenzpreis von {ref}/kWh wären es diesen Monat {ref_cost} gewesen – laut Rechnungen sind es {actual} ({sign}{delta}).",
        "in_reference_day": "Nachts und früh zu laden hat dir diesen Monat {saving} gespart: Zum Tagespreis deiner Ladeorte (Ø {ref}/kWh) wären es {ref_cost} gewesen statt {actual} – {kwh} kWh hast du in der Nebenzeit geladen.",
        "in_fuel": "Die {dist} {unit} diesen Monat hätten mit dem Verbrenner ({consumption} L/100 km, {price}/L) etwa {fuel} gekostet – gespart: {saved}.",
        "in_fuel_daily": "Die {dist} {unit} diesen Monat hätten mit dem Verbrenner ({consumption} L/100 km, Tagesdurchschnitt im Mittel {price}/L) etwa {fuel} gekostet – gespart: {saved}.",
        "plan": "Tipp: {when} in {site} laden – dort hast du bisher Ø {best}/kWh gezahlt statt {avg}/kWh, rund {saving} weniger bei {kwh} kWh.",
        "today": "heute",
        "tomorrow": "morgen",
        "report_title": "Ladecockpit · {month}",
        "report_text": "{sessions} Ladungen, {kwh} kWh, {cost} (Ø {price}/kWh).",
        "report_distance": "{dist} km gefahren, {per100} pro 100 km.",
        "report_fuel": "Mit dem Verbrenner wären es etwa {fuel} gewesen – gespart: {saved}.",
        "report_multipass": "Davon MultiPass: {cost}.",
        "report_home": "Zu Hause geladen: {kwh} kWh für {cost}.",
        "report_home_kwh": "Zu Hause geladen: {kwh} kWh.",
        "report_idle": "Blockiergebühren: {cost}.",
        "in_season_more": "In der Winterzeit braucht dein Tesla {w_kwh} kWh und kostet {w_cost} pro 100 {unit}, in der Sommerzeit {s_kwh} kWh und {s_cost} – rund {pct} % mehr Strom im Winter.",
        "in_season_less": "In der Winterzeit braucht dein Tesla {w_kwh} kWh und kostet {w_cost} pro 100 {unit}, in der Sommerzeit {s_kwh} kWh und {s_cost} – rund {pct} % weniger Strom im Winter.",
        "in_climate": "Bei {cold} braucht dein Tesla rund {more} % mehr Akku pro 100 {unit} als bei {warm}.",
        "in_slow_one": "Am {day} in {site} hast du nur mit Ø {kw} kW geladen, sonst bekommst du dort rund {typical} kW. "
                       "Häufige Gründe: ein kalter Akku (den Supercharger vorher als Navi-Ziel eingeben, dann heizt das Auto vor) "
                       "oder eine geteilte oder gedrosselte Säule.",
        "in_slow_many": "{n} Ladungen der letzten 45 Tage waren deutlich langsamer als sonst an der Station, zuletzt am {day} "
                        "in {site} mit Ø {kw} statt rund {typical} kW. Häufige Gründe: ein kalter Akku (den Supercharger "
                        "vorher als Navi-Ziel eingeben, dann heizt das Auto vor) oder eine geteilte oder gedrosselte Säule.",
        "band_below": "unter {hi} °C",
        "band_above": "über {lo} °C",
        "band_range": "{lo} bis {hi} °C",
        "fuel_default": "Sprit diesen Monat",
        "unknown_site": "Unbekannter Supercharger",
        "problem_title": "Ladecockpit",
        "problem_auth": "Die Tesla-Anmeldung ist abgelaufen. Öffne Ladecockpit und verbinde dich neu mit Tesla, sonst werden keine Rechnungen mehr gebucht.",
        "problem_sync": "Der Abgleich mit Tesla schlägt seit mehreren Versuchen fehl: {detail}",
        "problem_solved": "Wieder alles in Ordnung – der Abgleich mit Tesla klappt.",
        "push_invoice_title": "⚡ Neue Rechnung · {site}",
        "push_test_title": "Ladecockpit",
        "push_test": "Testnachricht – die Benachrichtigungen kommen an.",
        "problem_budget": "Das Monatsbudget für Tesla-Abfragen ist erreicht. Bis Monatsende werden keine Rechnungen mehr geholt.",
        "problem_not_connected": "Ladecockpit ist noch nicht mit Tesla verbunden.",
        "problem_entities": "Diese Entitäten gibt es in Home Assistant nicht: {entities}",
        "ent_next_charge": "Nächste Ladung",
        "ent_battery": "Akku",
        "ent_month_cost": "Ladekosten Monat",
        "ent_month_energy": "Lademenge Monat",
        "ent_last_charge": "Letzte Ladung",
        "ent_price_tip": "Preistipp",
        "ent_problem": "Problem",
        "ent_range_at_100": "Reichweite bei 100 %",
        "ent_consumption": "Verbrauch",
        "ent_car": "Fahrzeug",
        "ent_multipass": "MultiPass-Stationen",
        "mp_summary_one": "MultiPass hat bisher an 1 Station funktioniert{ops}.",
        "mp_summary_many": "MultiPass hat bisher an {n} Stationen funktioniert{ops}.",
        "mp_operators": " – Anbieter: {names}",
        "mp_none": "Noch keine MultiPass-Ladung in deinen Rechnungen.",
        "unknown_station": "Unbekannte Station",
        "ent_consumption_note": "Abgerechnete kWh pro 100 km diesen Monat, inklusive Ladeverlusten.",
        "season_winter": "Winterzeit",
        "season_summer": "Sommerzeit",
        "quarter_winter": "Winter",
        "quarter_spring": "Frühling",
        "quarter_summer": "Sommer",
        "quarter_autumn": "Herbst",
        "csv_header": "Datum;Start;Ende;Standort;kWh;Preis pro kWh;Ladekosten;Blockiergebühr;Summe;Währung;Ø kW;Ladung-ID;Netz;Listenpreis pro kWh;Gutschrift;Netto;Betreiber;Adresse",
    },
    "en": {
        "fc_no_soc": "No battery level from Home Assistant – no forecast possible.",
        "fc_too_little": "Not enough battery history for a forecast yet.",
        "fc_flat": "The battery is barely dropping – no charging stop in sight.",
        "fc_today": "Charge today – the battery will reach {floor} % soon.",
        "fc_tomorrow": "Plan to charge tomorrow.",
        "fc_latest": "Charge by {date} – in about {days} days.",
        "in_slot_best": "{label} ({range}) is your cheapest time: avg {price}/kWh, {diff}/kWh below your average.",
        "in_slot_best_few": "{label} ({range}) has been your cheapest time so far: avg {price}/kWh, {diff}/kWh below your average – but you have only charged {n}× then.",
        "in_slot_flat": "Time of day hardly makes a difference for your sessions so far.",
        "in_tariff": "In {site} a kWh costs {off} at night and early in the morning (off-peak) and {peak} during the day. Had you charged your {kwh} peak-time kWh at such sites at night, it would have been {saving} less.",
        "in_slot_wait": "After a few more sessions the price radar shows which time of day is cheapest for you.",
        "in_site": "Cheapest so far: {lo} (avg {lo_price}/kWh). Most expensive: {hi} (avg {hi_price}/kWh).",
        "in_price_change": "New price in {site}: since {since} a kWh costs {now} instead of {before} ({sign}{diff}/kWh). Older sessions there still count at the old price in the averages.",
        "in_network": "MultiPass sessions ({n}) cost you avg {mp}/kWh, Superchargers {sc}/kWh.",
        "in_credit": "Tesla credits covered {amount} so far. You paid avg {paid}/kWh, the list price was avg {listed}/kWh – price comparisons use the list price.",
        "in_idle_one": "Idle fees so far: {amount} in 1 session – unplugging on time saves money.",
        "in_idle_many": "Idle fees so far: {amount} in {n} sessions – unplugging on time saves money.",
        "in_reference": "At your reference price of {ref}/kWh this month would have cost {ref_cost} – the invoices say {actual} ({sign}{delta}).",
        "in_reference_day": "Charging at night and early in the morning saved you {saving} this month: at the day price of your sites (avg {ref}/kWh) it would have been {ref_cost} instead of {actual} – {kwh} kWh were off-peak.",
        "in_fuel": "This month's {dist} {unit} would have cost about {fuel} with a combustion car ({consumption} L/100 km, {price}/L) – saved: {saved}.",
        "in_fuel_daily": "This month's {dist} {unit} would have cost about {fuel} with a combustion car ({consumption} L/100 km, daily average {price}/L on the whole) – saved: {saved}.",
        "plan": "Tip: charge {when} at {site} – you paid avg {best}/kWh there instead of {avg}/kWh, about {saving} less for {kwh} kWh.",
        "today": "today",
        "tomorrow": "tomorrow",
        "report_title": "Ladecockpit · {month}",
        "report_text": "{sessions} sessions, {kwh} kWh, {cost} (avg {price}/kWh).",
        "report_distance": "{dist} {unit} driven, {per100} per 100 {unit}.",
        "report_fuel": "A combustion car would have cost about {fuel} – saved: {saved}.",
        "report_multipass": "Of which MultiPass: {cost}.",
        "report_home": "Charged at home: {kwh} kWh for {cost}.",
        "report_home_kwh": "Charged at home: {kwh} kWh.",
        "report_idle": "Idle fees: {cost}.",
        "in_season_more": "In winter time your Tesla uses {w_kwh} kWh and {w_cost} per 100 {unit}, in summer time {s_kwh} kWh and {s_cost} – about {pct} % more energy in winter.",
        "in_season_less": "In winter time your Tesla uses {w_kwh} kWh and {w_cost} per 100 {unit}, in summer time {s_kwh} kWh and {s_cost} – about {pct} % less energy in winter.",
        "in_climate": "At {cold} your Tesla uses about {more} % more battery per 100 {unit} than at {warm}.",
        "in_slow_one": "On {day} at {site} you only charged at {kw} kW on average, where you usually get about {typical} kW. "
                       "Common reasons: a cold battery (set the Supercharger as navigation destination so the car "
                       "preconditions) or a shared or throttled stall.",
        "in_slow_many": "{n} sessions in the last 45 days were much slower than usual at that site, most recently on {day} "
                        "at {site} with {kw} instead of about {typical} kW. Common reasons: a cold battery (set the "
                        "Supercharger as navigation destination so the car preconditions) or a shared or throttled stall.",
        "band_below": "below {hi} °C",
        "band_above": "above {lo} °C",
        "band_range": "{lo} to {hi} °C",
        "fuel_default": "Fuel this month",
        "unknown_site": "Unknown Supercharger",
        "problem_title": "Ladecockpit",
        "problem_auth": "The Tesla sign-in expired. Open Ladecockpit and connect to Tesla again, otherwise no invoices are booked.",
        "problem_sync": "Syncing with Tesla has failed several times in a row: {detail}",
        "problem_solved": "All fine again – syncing with Tesla works.",
        "push_invoice_title": "⚡ New invoice · {site}",
        "push_test_title": "Ladecockpit",
        "push_test": "Test message – notifications arrive.",
        "problem_budget": "The monthly budget for Tesla requests is used up. No invoices are fetched until next month.",
        "problem_not_connected": "Ladecockpit is not connected to Tesla yet.",
        "problem_entities": "These entities do not exist in Home Assistant: {entities}",
        "ent_next_charge": "Next charge",
        "ent_battery": "Battery",
        "ent_month_cost": "Charging cost this month",
        "ent_month_energy": "Energy charged this month",
        "ent_last_charge": "Last charge",
        "ent_price_tip": "Price tip",
        "ent_problem": "Problem",
        "ent_range_at_100": "Range at 100 %",
        "ent_consumption": "Consumption",
        "ent_car": "Car",
        "ent_multipass": "MultiPass stations",
        "mp_summary_one": "MultiPass has worked at 1 station so far{ops}.",
        "mp_summary_many": "MultiPass has worked at {n} stations so far{ops}.",
        "mp_operators": " – operators: {names}",
        "mp_none": "No MultiPass session in your invoices yet.",
        "unknown_station": "Unknown station",
        "ent_consumption_note": "Billed kWh per 100 km/mi this month, including charging losses.",
        "season_winter": "Winter time",
        "season_summer": "Summer time",
        "quarter_winter": "Winter",
        "quarter_spring": "Spring",
        "quarter_summer": "Summer",
        "quarter_autumn": "Autumn",
        "csv_header": "Date,Start,End,Site,kWh,Price per kWh,Charging cost,Idle fee,Total,Currency,Avg kW,Session ID,Network,List price per kWh,Credit,Net,Operator,Address",
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


def day_label(lang: str, dt) -> str:
    """A date with year: "20.10.2026" / "Oct 20, 2026"."""
    return f"{dt:%d.%m.%Y}" if lang == "de" else f"{dt:%b} {dt.day}, {dt.year}"


def temp_band(lang: str, lo: float | None, hi: float | None) -> str:
    if lo is None:
        return t(lang, "band_below", hi=f"{hi:g}")
    if hi is None:
        return t(lang, "band_above", lo=f"{lo:g}")
    return t(lang, "band_range", lo=f"{lo:g}", hi=f"{hi:g}")

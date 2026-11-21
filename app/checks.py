"""What the setup is missing, and whether each Home Assistant entity delivers what it should.

The web app and the mobile app show this under "Setup check": hints for options that would add
something (with the name of the option in the app configuration) and one line per entity with its
current value and unit."""
from __future__ import annotations

from .config import Settings
from .homeassistant import INVALID_STATES

# Units an entity may have, per role (lower case, without spaces). An empty tuple: any unit.
UNITS = {
    "soc": ("%",),
    "range": ("km", "mi"),
    "odometer": ("km", "mi"),
    "charge_power": ("kw", "w"),
    "cost_total": ("€", "eur", "$", "usd", "£", "gbp"),
    "kwh_total": ("kwh",),
    "reference_price": ("€/kwh", "eur/kwh", "$/kwh", "usd/kwh", "£/kwh", "gbp/kwh"),
    "fuel_month": ("€", "eur", "$", "usd", "£", "gbp"),
    "fuel_consumption": ("l/100km", "l/100 km", "mpg"),
    "fuel_price": ("€", "eur", "€/l", "eur/l", "$", "usd", "$/gal", "£", "£/l", "gbp"),
    "fuel_cost_total": ("€", "eur", "$", "usd", "£", "gbp"),
    "fuel_litres_total": ("l", "gal"),
    "outside_temp": ("°c", "°f", "c", "f"),
    "home_energy": ("kwh", "wh"),
    "home_price": ("€/kwh", "eur/kwh", "ct/kwh", "$/kwh", "usd/kwh", "£/kwh", "gbp/kwh"),
}
# Roles whose state is text or a time, not a number
TEXT_ROLES = ("charging", "time_to_full")

# Option names as the app configuration in Home Assistant shows them
OPTION = {
    "de": {"fuel_price_daily": "Spritpreis als Tagesdurchschnitt", "entity_odometer": "Entität Kilometerstand",
           "entity_charging": "Entität Ladestatus", "fuel_consumption": "Verbrauch Vergleichsauto",
           "fuel_price": "Spritpreis", "entity_home_energy": "Wallbox-Zähler (kWh)",
           "entity_outside_temp": "Außentemperatur", "entity_battery": "Entität Akkustand"},
    "en": {"fuel_price_daily": "Fuel price as a daily average", "entity_odometer": "Odometer entity",
           "entity_charging": "Charging state entity", "fuel_consumption": "Consumption of a comparison car",
           "fuel_price": "Fuel price", "entity_home_energy": "Wallbox energy meter (kWh)",
           "entity_outside_temp": "Outside temperature", "entity_battery": "Battery level entity"},
}

# What each entity is for, as the setup check names it
ROLE_NAMES = {
    "de": {"soc": "Akkustand", "range": "Reichweite", "odometer": "Kilometerstand", "charging": "Ladestatus",
           "charge_power": "Ladeleistung", "time_to_full": "Zeit bis voll", "cost_total": "Ladekosten gesamt",
           "kwh_total": "Lademenge gesamt", "reference_price": "Referenzpreis", "fuel_month": "Spritkosten Monat",
           "fuel_consumption": "Verbrauch Vergleichsauto", "fuel_price": "Spritpreis",
           "fuel_cost_total": "Tankkosten gesamt", "fuel_litres_total": "Getankte Liter gesamt",
           "outside_temp": "Außentemperatur", "home_energy": "Wallbox-Zähler", "home_price": "Strompreis zu Hause"},
    "en": {"soc": "Battery level", "range": "Range", "odometer": "Odometer", "charging": "Charging state",
           "charge_power": "Charging power", "time_to_full": "Time to full", "cost_total": "Cost total",
           "kwh_total": "Energy total", "reference_price": "Reference price", "fuel_month": "Fuel cost this month",
           "fuel_consumption": "Comparison car consumption", "fuel_price": "Fuel price",
           "fuel_cost_total": "Fuel cost total", "fuel_litres_total": "Litres filled total",
           "outside_temp": "Outside temperature", "home_energy": "Wallbox meter", "home_price": "Electricity price at home"},
}

TEXTS = {
    "de": {
        "fuel_daily": "Du hast einen Spritpreis-Sensor. Mit „{option}“ rechnet der Verbrenner-Vergleich jeden Tag mit dessen Tagesdurchschnitt.",
        "fuel_no_consumption": "Für den Verbrenner-Vergleich fehlt der Verbrauch des Vergleichsautos („{option}“).",
        "fuel_no_price": "Für den Verbrenner-Vergleich fehlt ein Spritpreis („{option}“, fest oder als Entität).",
        "no_odometer": "Ohne „{option}“ fehlen Strecke, Kosten pro 100 km und der Verbrenner-Vergleich.",
        "no_charging": "Mit „{option}“ holt Ladecockpit die Rechnung gleich nach dem Laden statt beim nächsten regelmäßigen Abgleich.",
        "no_battery": "Mit „{option}“ gibt es Akku-Anzeige, Ladestopp-Prognose und Akku-Gesundheit.",
        "no_home": "Lädst du auch zu Hause? Mit „{option}“ rechnet Ladecockpit diese Ladungen mit ein.",
        "no_temp": "Mit „{option}“ zeigt Ladecockpit den Verbrauch je nach Temperatur.",
        "hidden": "Nicht sichtbar in der Konfiguration? Dort „Nicht verwendete optionale Konfigurationsoptionen anzeigen“ einschalten.",
        "missing": "Entität nicht gefunden",
        "unavailable": "gerade nicht verfügbar",
        "not_numeric": "liefert keine Zahl",
        "unit": "unerwartete Einheit {unit}",
    },
    "en": {
        "fuel_daily": "You have a fuel price sensor. With \"{option}\" the comparison with a combustion car uses its average of every day.",
        "fuel_no_consumption": "The comparison with a combustion car needs the consumption of the comparison car (\"{option}\").",
        "fuel_no_price": "The comparison with a combustion car needs a fuel price (\"{option}\", fixed or as an entity).",
        "no_odometer": "Without \"{option}\" there is no distance, no cost per 100 km and no comparison with a combustion car.",
        "no_charging": "With \"{option}\" Ladecockpit fetches the invoice right after charging instead of at the next regular sync.",
        "no_battery": "With \"{option}\" you get the battery card, the charging forecast and battery health.",
        "no_home": "Do you charge at home too? With \"{option}\" Ladecockpit counts those sessions in.",
        "no_temp": "With \"{option}\" Ladecockpit shows the consumption by temperature.",
        "hidden": "Not shown in the configuration? Turn on \"Show unused optional configuration options\" there.",
        "missing": "entity not found",
        "unavailable": "unavailable right now",
        "not_numeric": "does not deliver a number",
        "unit": "unexpected unit {unit}",
    },
}


def _t(lang: str, key: str, **kw) -> str:
    return (TEXTS.get(lang) or TEXTS["en"])[key].format(**kw)


def _option(lang: str, key: str) -> str:
    return (OPTION.get(lang) or OPTION["en"])[key]


def hints(settings: Settings, lang: str) -> list[dict]:
    """Options that would add something. Each: {id, text}; `level` "tip" (adds a feature) or
    "missing" (a feature is half set up)."""
    s = settings
    if not s.ha_url:
        return []
    out: list[dict] = []

    def add(hid: str, level: str, option: str) -> None:
        out.append({"id": hid, "level": level, "text": _t(lang, hid, option=_option(lang, option))})

    has_price = bool(s.ent_fuel_price or s.fuel_price or (s.ent_fuel_cost_total and s.ent_fuel_litres_total))
    has_consumption = bool(s.ent_fuel_consumption or s.fuel_consumption)
    if has_price and not has_consumption:
        add("fuel_no_consumption", "missing", "fuel_consumption")
    if has_consumption and not has_price:
        add("fuel_no_price", "missing", "fuel_price")
    if s.ent_fuel_price and not s.fuel_price_daily:
        add("fuel_daily", "tip", "fuel_price_daily")
    if not s.ent_odometer:
        add("no_odometer", "missing" if has_consumption else "tip", "entity_odometer")
    if not s.ent_soc:
        add("no_battery", "tip", "entity_battery")
    if not s.ent_charging:
        add("no_charging", "tip", "entity_charging")
    if not s.ent_home_energy:
        add("no_home", "tip", "entity_home_energy")
    if not s.ent_outside_temp:
        add("no_temp", "tip", "entity_outside_temp")
    return out


def entity_report(roles: dict[str, str], live: dict, lang: str) -> list[dict]:
    """One line per configured entity: {role, entity, state, unit, ok, problem}."""
    raw, values, units = live.get("raw") or {}, live.get("values") or {}, live.get("units") or {}
    missing = set(live.get("missing") or [])
    reachable = bool(live.get("available"))
    out = []
    order = list(ROLE_NAMES["en"])
    for role, eid in sorted(roles.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99):
        row = {"role": role, "label": (ROLE_NAMES.get(lang) or ROLE_NAMES["en"]).get(role, role), "entity": eid, "state": raw.get(role), "unit": units.get(role), "ok": True,
               "problem": None}
        if not reachable:
            row["ok"] = None                       # Home Assistant itself is down: nothing to judge
        elif eid in missing:
            row.update(ok=False, problem=_t(lang, "missing"))
        elif str(raw.get(role, "")).strip().lower() in INVALID_STATES:
            row.update(ok=False, problem=_t(lang, "unavailable"))
        elif role not in TEXT_ROLES and values.get(role) is None:
            row.update(ok=False, problem=_t(lang, "not_numeric"))
        else:
            unit = (units.get(role) or "").strip().lower().replace(" ", "")
            allowed = tuple(u.replace(" ", "") for u in UNITS.get(role, ()))
            if unit and allowed and unit not in allowed:
                row.update(ok=False, problem=_t(lang, "unit", unit=units.get(role)))
        out.append(row)
    return out


def report(settings: Settings, roles: dict[str, str], live: dict) -> dict:
    lang = settings.lang
    h = hints(settings, lang)
    return {"hints": h, "hidden_note": _t(lang, "hidden") if settings.addon and h else None,
            "entities": entity_report(roles, live, lang)}

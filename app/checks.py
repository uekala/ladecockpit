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
# Roles that only have a value while the car charges: unavailable or unknown is normal otherwise
WHILE_CHARGING = ("time_to_full", "charge_power")

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

# The setup, step by step: title and what each state says
STEPS = {
    "de": {
        "tesla_app": ("Tesla-Developer-App", "Client ID ist eingetragen.", "Noch keine Client ID – lege die App bei Tesla an und trage Client ID und Secret ein."),
        "tesla_login": ("Mit Tesla anmelden", "Angemeldet.", "Noch nicht angemeldet."),
        "sync": ("Erster Abgleich", "{n} Ladungen geholt, zuletzt {when}.", "Noch kein Abgleich – startet nach der Anmeldung von selbst."),
        "ha": ("Home Assistant", "Verbunden.", "Nicht eingerichtet. Akku, Strecke und Ladestopp-Prognose kommen von dort."),
        "entities": ("Entitäten", "Alle {n} liefern Werte.", "Noch keine Entität eingetragen (Akkustand, Kilometerstand, Ladestatus)."),
        "extras": ("Weitere Auswertungen", "Alles eingerichtet.", "{n} Optionen würden noch etwas bringen."),
        "extras_one": "1 Option würde noch etwas bringen.",
        "problem_entities": "{n} von {m} liefern keinen passenden Wert.",
        "optional": "optional",
    },
    "en": {
        "tesla_app": ("Tesla developer app", "Client ID is set.", "No client ID yet – create the app at Tesla and enter client ID and secret."),
        "tesla_login": ("Sign in with Tesla", "Signed in.", "Not signed in yet."),
        "sync": ("First sync", "{n} sessions fetched, last {when}.", "No sync yet – it starts by itself after signing in."),
        "ha": ("Home Assistant", "Connected.", "Not set up. Battery, distance and the charging forecast come from there."),
        "entities": ("Entities", "All {n} deliver values.", "No entity entered yet (battery level, odometer, charging state)."),
        "extras": ("More insights", "Everything is set up.", "{n} options would still add something."),
        "extras_one": "1 option would still add something.",
        "problem_entities": "{n} of {m} do not deliver a fitting value.",
        "optional": "optional",
    },
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
        "charging_only": "nur beim Laden",
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
        "charging_only": "only while charging",
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
               "problem": None, "note": None}
        if not reachable:
            row["ok"] = None                       # Home Assistant itself is down: nothing to judge
        elif eid in missing:
            row.update(ok=False, problem=_t(lang, "missing"))
        elif str(raw.get(role, "")).strip().lower() in INVALID_STATES:
            if role in WHILE_CHARGING:
                row["note"] = _t(lang, "charging_only")      # fine: the car is not charging
            else:
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


def steps(settings: Settings, state: dict, entities: list[dict], hint_list: list[dict], lang: str) -> list[dict]:
    """The setup in order. Each: {id, status, title, text, required}; status is "done", "todo" (the
    next thing to do), "problem" (set up, but not working) or "optional" (not set up, not needed).
    state: tesla_connected, tesla_auth_error, last_sync, sync_error, sessions, ha_ok, ha_error, when."""
    t = STEPS.get(lang) or STEPS["en"]
    out: list[dict] = []

    def add(sid: str, status: str, text: str, required: bool = True) -> None:
        out.append({"id": sid, "status": status, "title": t[sid][0], "text": text, "required": required})

    s = settings
    add("tesla_app", "done" if s.tesla_configured else "todo", t["tesla_app"][1 if s.tesla_configured else 2])
    if state.get("tesla_auth_error"):
        add("tesla_login", "problem", str(state["tesla_auth_error"]))
    else:
        connected = bool(state.get("tesla_connected"))
        add("tesla_login", "done" if connected else "todo", t["tesla_login"][1 if connected else 2])
    if state.get("sync_error"):
        add("sync", "problem", str(state["sync_error"]))
    elif state.get("last_sync"):
        add("sync", "done", t["sync"][1].format(n=state.get("sessions", 0), when=state.get("when") or ""))
    else:
        add("sync", "todo", t["sync"][2])
    if not s.ha_configured:
        add("ha", "optional", t["ha"][2], required=False)
    elif state.get("ha_ok"):
        add("ha", "done", t["ha"][1], required=False)
    else:
        add("ha", "problem", str(state.get("ha_error") or ""), required=False)
    if s.ha_configured:
        bad = [e for e in entities if e["ok"] is False]
        if not entities:
            add("entities", "todo", t["entities"][2], required=False)
        elif bad:
            add("entities", "problem", t["problem_entities"].format(n=len(bad), m=len(entities)), required=False)
        elif all(e["ok"] is None for e in entities):
            add("entities", "problem", str(state.get("ha_error") or ""), required=False)
        else:
            add("entities", "done", t["entities"][1].format(n=len(entities)), required=False)
        add("extras", "optional" if hint_list else "done",
            (t["extras_one"] if len(hint_list) == 1 else t["extras"][2].format(n=len(hint_list)))
            if hint_list else t["extras"][1], required=False)
    # Only the first open required step is "todo"; the ones after it wait.
    seen_todo = False
    for step in out:
        if step["status"] == "todo":
            if seen_todo:
                step["status"] = "waiting"
            seen_todo = True
    return out


def report(settings: Settings, roles: dict[str, str], live: dict, state: dict | None = None) -> dict:
    lang = settings.lang
    h = hints(settings, lang)
    ents = entity_report(roles, live, lang) if settings.ha_configured else []
    return {"hints": h, "hidden_note": _t(lang, "hidden") if settings.addon and h else None,
            "entities": ents, "steps": steps(settings, state or {}, ents, h, lang)}

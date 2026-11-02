"""Which network a session from the Tesla charging history belongs to.

Tesla bills two kinds of sessions through the same history: its own Superchargers, and
since 2025 third-party chargers paid with Tesla MultiPass. The Fleet API has no field
that names the network, and Tesla has not documented how MultiPass sessions look.
So this goes by hints, from strong to weak; the weakest is the price: a site that does not
look like a Supercharger and cost more than MULTIPASS_MIN_PRICE per kWh. It runs whenever sessions are read from
the database (the raw Tesla record is kept), so a better rule in a later version also
re-classifies older sessions.
"""
from __future__ import annotations

import re

SUPERCHARGER = "supercharger"
MULTIPASS = "multipass"

# Values a plain Supercharger record has (seen in real data).
SUPERCHARGER_BILLING = {"IMMEDIATE"}
# Fields of a plain Supercharger record. Anything else is logged, so new formats get noticed.
KNOWN_KEYS = {
    "billingType", "chargeStartDateTime", "chargeStopDateTime", "countryCode", "credit", "fees",
    "invoices", "sessionId", "siteLocationName", "unlatchDateTime", "vehicleMakeType", "vin",
}

_HINT = re.compile(r"multi\s*pass|roaming|third[\s_-]*party|partner|e-?msp|ocpi|hubject|electroverse", re.I)
_HINT_KEY = re.compile(r"operator|network|provider|cpo|evse|partner|roaming|third_?party|emsp", re.I)
# MultiPass invoice numbers carry "MSP" (Tesla as mobility service provider): 4020MSP0000019797
_MSP_NUMBER = re.compile(r"\d{3,5}MSP\d{6,}", re.I)
# Free text and IDs: never searched for hints (a site called "Partnerweg" is still a Supercharger).
_SKIP = {"siteLocationName", "vin", "contentId", "fileName", "sessionId", "sessionFeeId",
         "chargeStartDateTime", "chargeStopDateTime", "unlatchDateTime"}

# Operators that do not run Superchargers. Matched as whole words in the site name.
_BRANDS = re.compile(
    r"\b(enbw|ionity|fastned|allego|aral\s*pulse|bp\s*pulse|shell(?:\s*recharge)?|ewe\s*go|e\.on|eon drive|"
    r"vattenfall|maingau|pfalzwerke|electra|atlante|zunder|plugsurfing|wirelane|elli|qwello|chargepoint|"
    r"monta|virta|greenway|iberdrola|endesa|instavolt|osprey|gridserve|pod\s*point|totalenergies|"
    r"lidl|kaufland|aldi|stadtwerke|mobility\+|tesla\s*multipass|be\s*charge|ladenetz|innogy|easycharger)\b",
    re.I,
)


# Tesla names its Superchargers "Place, Country" ("Bergstadt, Germany", "Seestadt - Center, Germany").
# Third-party sites can look alike ("Brunnenhausstr. 46, Neustadt"), so the part after the last comma
# must be a country.
_COUNTRIES = frozenset("""
germany deutschland netherlands the-netherlands nederland belgium belgique belgië belgie france austria
österreich osterreich switzerland schweiz suisse svizzera italy italia spain españa espana portugal denmark
danmark sweden sverige norway norge finland suomi poland polska czech-republic czechia česko cesko slovakia
slovensko hungary magyarország magyarorszag slovenia slovenija croatia hrvatska luxembourg luxemburg ireland
united-kingdom uk great-britain england scotland wales northern-ireland iceland ísland estonia eesti latvia
latvija lithuania lietuva romania românia bulgaria greece turkey türkiye turkiye serbia liechtenstein monaco
andorra malta cyprus bosnia-and-herzegovina montenegro north-macedonia albania kosovo ukraine moldova
georgia israel jordan morocco united-arab-emirates uae saudi-arabia qatar united-states usa canada mexico
chile australia new-zealand japan china south-korea korea taiwan hong-kong singapore thailand malaysia
philippines india
""".split())
_TESLA_WORDS = re.compile(r"\b(tesla|supercharger)\b", re.I)

# Price rule: a session whose site does not look like a Supercharger and whose energy cost more
# than this per kWh (EUR) is counted as MultiPass. Superchargers rarely cost more; when they do
# (peak hours), their site name still has the Supercharger form, so they are not affected.
# 0 turns the rule off. Set from MULTIPASS_MIN_PRICE at start (see configure).
DEFAULT_MIN_PRICE = 0.50
_min_price = DEFAULT_MIN_PRICE


def configure(min_price: float | None) -> None:
    """Set the price rule (EUR per kWh, 0 or None = off)."""
    global _min_price
    _min_price = float(min_price) if min_price and min_price > 0 else 0.0


def looks_like_supercharger(site: str | None) -> bool:
    """True when the site name has the form Tesla gives its Superchargers, or says Tesla."""
    site = (site or "").strip()
    if not site:
        return False
    if _TESLA_WORDS.search(site):
        return True
    place, comma, country = site.rpartition(",")
    country = "-".join(country.casefold().split())
    return bool(comma and place.strip() and country in _COUNTRIES)


def kwh_rate(raw: dict) -> tuple[float, str] | None:
    """(list price per kWh, currency) from the CHARGING fees, or None.

    Uses the listed rate (rateBase), so a session partly paid with Tesla credits keeps its
    real price; without a rate, the total divided by the kWh.
    """
    usage = cost = 0.0
    currency = ""
    for fee in raw.get("fees") or []:
        if not isinstance(fee, dict) or str(fee.get("feeType", "")).upper() != "CHARGING":
            continue
        if str(fee.get("uom", "")).lower() != "kwh":
            continue
        try:
            kwh = float(fee.get("usageBase") or 0)
            if fee.get("rateBase") is not None:
                amount = kwh * float(fee["rateBase"])
            else:
                amount = float(fee.get("totalBase") or fee.get("totalDue") or 0)
        except (TypeError, ValueError):
            continue
        if kwh <= 0:
            continue
        usage += kwh
        cost += amount
        currency = currency or str(fee.get("currencyCode") or "").upper()
    if usage <= 0:
        return None
    return round(cost / usage, 4), currency


# How the operators matched by _BRANDS are written (lower-case match → display name).
_OPERATOR_NAMES = {
    "enbw": "EnBW", "ionity": "IONITY", "fastned": "Fastned", "allego": "Allego", "aral pulse": "Aral pulse",
    "bp pulse": "bp pulse", "shell recharge": "Shell Recharge", "shell": "Shell Recharge", "ewe go": "EWE Go", "e.on": "E.ON",
    "eon drive": "E.ON Drive", "vattenfall": "Vattenfall", "maingau": "Maingau", "pfalzwerke": "Pfalzwerke",
    "electra": "Electra", "atlante": "Atlante", "zunder": "Zunder", "plugsurfing": "Plugsurfing",
    "wirelane": "Wirelane", "elli": "Elli", "qwello": "Qwello", "chargepoint": "ChargePoint", "monta": "Monta",
    "virta": "Virta", "greenway": "GreenWay", "iberdrola": "Iberdrola", "endesa": "Endesa",
    "instavolt": "InstaVolt", "osprey": "Osprey", "gridserve": "Gridserve", "pod point": "Pod Point",
    "totalenergies": "TotalEnergies", "lidl": "Lidl", "kaufland": "Kaufland", "aldi": "Aldi",
    "stadtwerke": "Stadtwerke", "mobility+": "Mobility+", "be charge": "Be Charge", "ladenetz": "ladenetz.de",
    "innogy": "innogy", "easycharger": "EasyCharger",
}


def operator(site: str | None) -> str | None:
    """The charging network named in a site name ("EnBW Ladepark Südstadt" → "EnBW"), if any."""
    for match in _BRANDS.finditer(site or ""):
        key = re.sub(r"\s+", " ", match.group(0).lower())
        if key in _OPERATOR_NAMES:
            return _OPERATOR_NAMES[key]
    return None


_SITE_SPLIT = re.compile(r"\s+[-–|]\s+")
_CODE = re.compile(r"^[A-Za-z]{0,5}[\s-]?\d{2,}[A-Za-z]?$")  # a station number like "OBN 0317", not a network
_POSTCODE = re.compile(r"^[\d\s-]+")


def _plain(text: str) -> str:
    return " ".join(text.split()).casefold()


def place_names(sites) -> frozenset[str]:
    """Towns named in your own site names: the town of a Supercharger ("Bergstadt, Germany",
    "Seestadt - Center, Germany") and the town after the comma of an address
    ("Brunnenhausstr. 46, Neustadt"). They tell "Neustadt - KiK" (town first) from
    "Hyper Charge - Musterstadt" (network first)."""
    places: set[str] = set()
    for site in sites:
        place, comma, tail = (site or "").strip().rpartition(",")
        if not comma or not place.strip():
            continue
        if "-".join(tail.casefold().split()) in _COUNTRIES:
            town = _SITE_SPLIT.split(place.strip(), maxsplit=1)[0]
        else:
            town = _POSTCODE.sub("", tail.strip())
        town = _plain(town)
        if town and any(ch.isalpha() for ch in town):
            places.add(town)
    return frozenset(places)


def operator_from_site(site: str | None, places: frozenset[str] = frozenset()) -> str | None:
    """The network behind a third-party site: a known brand, otherwise the part before the dash
    as Tesla writes MultiPass sites ("Hyper Charge - Musterstadt" → "Hyper Charge").
    A part before the dash that is one of `places` is a town, not a network ("Neustadt - KiK")."""
    known = operator(site)
    if known:
        return known
    if looks_like_supercharger(site):
        return None
    parts = _SITE_SPLIT.split((site or "").strip(), maxsplit=1)
    if len(parts) == 2:
        head = parts[0].strip()
        if 2 <= len(head) <= 40 and any(ch.isalpha() for ch in head) and not _CODE.match(head) and _plain(head) not in places:
            return head
    return None


def _records(raw: dict):
    yield raw
    for key in ("fees", "invoices"):
        for item in raw.get(key) or []:
            if isinstance(item, dict):
                yield item


def classify(raw: dict | None) -> tuple[str, str | None]:
    """(network, reason) for one raw record of the Tesla charging history."""
    if not raw:
        return SUPERCHARGER, None
    for record in _records(raw):
        for key, value in record.items():
            if _HINT_KEY.search(key):
                return MULTIPASS, f"field {key}"
            if key not in _SKIP and isinstance(value, str) and _HINT.search(value):
                return MULTIPASS, f"{key}={value}"
    for inv in raw.get("invoices") or []:
        name = inv.get("fileName") if isinstance(inv, dict) else None
        if isinstance(name, str) and _MSP_NUMBER.search(name):
            return MULTIPASS, f"invoice {name}"
    for key, record in (("billingType", raw), *(("invoiceType", inv) for inv in raw.get("invoices") or [])):
        value = record.get(key) if isinstance(record, dict) else None
        if value and str(value).upper() not in SUPERCHARGER_BILLING:
            return MULTIPASS, f"{key}={value}"
    site = raw.get("siteLocationName") or ""
    brand = _BRANDS.search(site)
    if brand:
        return MULTIPASS, f"site {brand.group(0)}"
    if _min_price > 0 and not looks_like_supercharger(site):
        rate = kwh_rate(raw)
        if rate and rate[1] == "EUR" and rate[0] > _min_price:
            return MULTIPASS, f"price {rate[0]:.2f} EUR/kWh, site not like a Supercharger"
    return SUPERCHARGER, None


def unknown_keys(raw: dict) -> list[str]:
    return sorted(set(raw) - KNOWN_KEYS)

"""Which network a session from the Tesla charging history belongs to.

Tesla bills two kinds of sessions through the same history: its own Superchargers, and
since 2025 third-party chargers paid with Tesla MultiPass. The Fleet API has no field
that names the network, and Tesla has not documented how MultiPass sessions look.
So this goes by hints, from strong to weak. It runs whenever sessions are read from
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
    "billingType", "chargeStartDateTime", "chargeStopDateTime", "countryCode", "fees",
    "invoices", "sessionId", "siteLocationName", "unlatchDateTime", "vehicleMakeType", "vin",
}

_HINT = re.compile(r"multi\s*pass|roaming|third[\s_-]*party|partner|e-?msp|ocpi|hubject|electroverse", re.I)
_HINT_KEY = re.compile(r"operator|network|provider|cpo|evse|partner|roaming|third_?party|emsp", re.I)
# Free text and IDs: never searched for hints (a site called "Partnerweg" is still a Supercharger).
_SKIP = {"siteLocationName", "vin", "contentId", "fileName", "sessionId", "sessionFeeId",
         "chargeStartDateTime", "chargeStopDateTime", "unlatchDateTime"}

# Operators that do not run Superchargers. Matched as whole words in the site name.
_BRANDS = re.compile(
    r"\b(enbw|ionity|fastned|allego|aral\s*pulse|bp\s*pulse|shell\s*recharge|ewe\s*go|e\.on|eon drive|"
    r"vattenfall|maingau|pfalzwerke|electra|atlante|zunder|plugsurfing|wirelane|elli|qwello|chargepoint|"
    r"monta|virta|greenway|iberdrola|endesa|instavolt|osprey|gridserve|pod\s*point|totalenergies|"
    r"lidl|kaufland|aldi|stadtwerke|mobility\+|tesla\s*multipass|be\s*charge|ladenetz|innogy|easycharger)\b",
    re.I,
)


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
    for key, record in (("billingType", raw), *(("invoiceType", inv) for inv in raw.get("invoices") or [])):
        value = record.get(key) if isinstance(record, dict) else None
        if value and str(value).upper() not in SUPERCHARGER_BILLING:
            return MULTIPASS, f"{key}={value}"
    site = raw.get("siteLocationName") or ""
    brand = _BRANDS.search(site)
    if brand:
        return MULTIPASS, f"site {brand.group(0)}"
    return SUPERCHARGER, None


def unknown_keys(raw: dict) -> list[str]:
    return sorted(set(raw) - KNOWN_KEYS)

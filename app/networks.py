"""Zu welchem Netz eine Ladung aus der Tesla-Ladehistorie gehört.

Tesla rechnet zwei Arten von Ladungen über dieselbe Historie ab: die eigenen Supercharger und
seit 2025 Fremdsäulen, bezahlt mit Tesla MultiPass. Die Fleet API hat kein Feld, das das Netz
nennt, und Tesla hat nicht dokumentiert, wie MultiPass-Ladungen aussehen. Deshalb geht das nach
Hinweisen, von stark nach schwach; der schwächste ist der Preis: ein Standort, der nicht wie ein
Supercharger aussieht und mehr als MULTIPASS_MIN_PRICE pro kWh gekostet hat. Das läuft bei jedem
Lesen von Ladungen aus der Datenbank (der Roh-Datensatz von Tesla bleibt erhalten), eine bessere
Regel in einer späteren Version ordnet also auch ältere Ladungen neu ein.
"""
from __future__ import annotations

import re

SUPERCHARGER = "supercharger"
MULTIPASS = "multipass"

# Values a plain Supercharger record has (seen in real data).
SUPERCHARGER_BILLING = {"IMMEDIATE"}
# Felder eines einfachen Supercharger-Datensatzes. Alles andere wird geloggt, damit neue Formate auffallen.
KNOWN_KEYS = {
    "billingType", "chargeStartDateTime", "chargeStopDateTime", "countryCode", "credit", "fees",
    "invoices", "sessionId", "siteLocationName", "unlatchDateTime", "vehicleMakeType", "vin",
}

_HINT = re.compile(r"multi\s*pass|roaming|third[\s_-]*party|partner|e-?msp|ocpi|hubject|electroverse", re.I)
_HINT_KEY = re.compile(r"operator|network|provider|cpo|evse|partner|roaming|third_?party|emsp", re.I)
# Die Rechnungsnummer nennt die Art der Rechnung und damit das Netz: Supercharger-Rechnungen sind
# Serie "P" (4020P0019025690_DE-DE.pdf), MultiPass-Rechnungen Serie "MSP" – Tesla als Mobilitäts-
# dienstleister (4020MSP0000019849_DE-DE.pdf). Tesla schreibt die Nummer in den Dateinamen der Rechnung.
_INVOICE_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d{3,5}([A-Za-z]{1,5})\d{6,}")
_SERIES = {"MSP": MULTIPASS, "P": SUPERCHARGER}


def invoice_series(text: str | None) -> str | None:
    """Die Serie der ersten Rechnungsnummer in einem Text oder Dateinamen ("4020MSP0000019849" → "MSP")."""
    m = _INVOICE_NUMBER.search(text or "")
    return m.group(1).upper() if m else None
# Freitext und IDs: nie nach Hinweisen durchsucht (ein Standort namens „Partnerweg“ bleibt ein Supercharger).
_SKIP = {"siteLocationName", "vin", "contentId", "fileName", "sessionId", "sessionFeeId",
         "chargeStartDateTime", "chargeStopDateTime", "unlatchDateTime"}

# Betreiber, die keine Supercharger betreiben. Als ganze Wörter im Standortnamen gesucht.
_BRANDS = re.compile(
    r"\b(enbw|ionity|fastned|allego|aral\s*pulse|bp\s*pulse|shell(?:\s*recharge)?|ewe\s*go|e\.on(?:\s*drive)?|eon drive|"
    r"vattenfall|maingau|pfalzwerke|electra|atlante|zunder|plugsurfing|wirelane|elli|qwello|chargepoint|"
    r"monta|virta|greenway|iberdrola|endesa|instavolt|osprey|gridserve|pod\s*point|totalenergies|"
    r"lidl|kaufland|aldi|stadtwerke|mobility\+|tesla\s*multipass|be\s*charge|ladenetz|innogy|easycharger)\b",
    re.I,
)


# Tesla nennt seine Supercharger „Ort, Land“ („Bergstadt, Germany“, „Seestadt - Center, Germany“).
# Fremdstandorte können ähnlich aussehen („Brunnenhausstr. 46, Neustadt“), deshalb muss der Teil nach
# dem letzten Komma ein Land sein.
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

# Preisregel: Eine Ladung, deren Standort nicht wie ein Supercharger aussieht und deren Energie mehr
# als dies pro kWh (EUR) gekostet hat, zählt als MultiPass. Supercharger kosten selten mehr; wenn doch
# (Hauptzeit), hat ihr Standortname trotzdem die Supercharger-Form, sie sind also nicht betroffen.
# 0 schaltet die Regel ab. Beim Start aus MULTIPASS_MIN_PRICE gesetzt (siehe configure).
DEFAULT_MIN_PRICE = 0.50
_min_price = DEFAULT_MIN_PRICE


def home_country(sessions) -> str | None:
    """Das Land, in dem die meisten Ladungen stattfanden (ISO-Code, wie Tesla ihn meldet), oder None."""
    codes = [str(x.get("country")).upper() for x in sessions if x.get("country")]
    if not codes:
        return None
    best = max(set(codes), key=lambda c: (codes.count(c), c))
    return best


def place(site: str | None, country: str | None, home: str | None) -> str | None:
    """„Bergstadt, Germany“ → „Bergstadt“ für eine Ladung im Heimatland. Ein Standort im Ausland
    behält sein Land, ebenso ein Name, dessen letzter Teil kein Land ist
    („Brunnenhausstr. 46, Neustadt“)."""
    site = (site or "").strip()
    if not site:
        return None
    name, comma, tail = site.rpartition(",")
    if not (comma and name.strip() and "-".join(tail.casefold().split()) in _COUNTRIES):
        return site
    if home and country and str(country).upper() != home:
        return site
    return name.strip()


def configure(min_price: float | None, site_operators: str | None = None) -> None:
    """Die Preisregel setzen (EUR pro kWh, 0 oder None = aus) und die Betreiber, die der Nutzer
    Standorten zugeordnet hat („Hafenstadt=Fastned; Parkhaus Mitte=Stadtwerke“)."""
    global _min_price, _site_operators
    _min_price = float(min_price) if min_price and min_price > 0 else 0.0
    _site_operators = parse_site_operators(site_operators)


# Von Hand zugeordnete Betreiber: (Text im Standortnamen oder in der Adresse, Betreiber), siehe configure.
_site_operators: tuple[tuple[str, str], ...] = ()
# In der App einem Standort zugeordnete Betreiber: {Standortname klein geschrieben: Betreiber}. Sie gehen
# der Option oben vor, die für ganze Gruppen von Standorten bleibt („jeder Standort mit Hafenstadt darin“).
_assigned_sites: dict[str, str] = {}


def _site_key(site: str | None) -> str:
    return " ".join((site or "").split()).casefold()


def set_assigned_sites(assigned: dict[str, str] | None) -> None:
    """Die einzelnen Standorten zugeordneten Betreiber ersetzen ({Standortname: Betreiber})."""
    global _assigned_sites
    _assigned_sites = {_site_key(site): " ".join(name.split())
                       for site, name in (assigned or {}).items() if _site_key(site) and name and name.strip()}


def assigned_sites() -> dict[str, str]:
    return dict(_assigned_sites)


def parse_site_operators(text: str | None) -> tuple[tuple[str, str], ...]:
    """„Hafenstadt=Fastned; Parkhaus Mitte = Stadtwerke“ → (("hafenstadt", "Fastned"), …).
    Einträge werden durch Semikolon oder Zeilenumbruch getrennt; einer ohne „=“ oder mit leerer Seite wird übersprungen."""
    pairs = []
    for entry in re.split(r"[;\n]+", text or ""):
        needle, eq, name = entry.partition("=")
        needle, name = " ".join(needle.split()).casefold(), " ".join(name.split())
        if eq and needle and name:
            pairs.append((needle, name))
    return tuple(pairs)


def assigned_operator(*texts: str | None) -> str | None:
    """Der Betreiber, den der Nutzer einem Standort zugeordnet hat: der erste Eintrag, dessen Text in einem
    der `texts` vorkommt (Standortname, Stationsname, Adresse), ohne Unterschied von Groß- und Kleinschreibung."""
    exact = _assigned_sites.get(_site_key(texts[0] if texts else None))
    if exact:
        return exact
    if not _site_operators:
        return None
    haystack = [" ".join(t.split()).casefold() for t in texts if t]
    for needle, name in _site_operators:
        if any(needle in t for t in haystack):
            return name
    return None


def looks_like_supercharger(site: str | None) -> bool:
    """True, wenn der Standortname die Form hat, die Tesla seinen Superchargern gibt, oder Tesla nennt."""
    site = (site or "").strip()
    if not site:
        return False
    if _TESLA_WORDS.search(site):
        return True
    place, comma, country = site.rpartition(",")
    country = "-".join(country.casefold().split())
    return bool(comma and place.strip() and country in _COUNTRIES)


def kwh_rate(raw: dict) -> tuple[float, str] | None:
    """(Listenpreis pro kWh, Währung) aus den CHARGING-Gebühren, oder None.

    Nimmt den Listenpreis (rateBase), eine teils mit Tesla-Guthaben bezahlte Ladung behält also ihren
    echten Preis; ohne Preis die Summe geteilt durch die kWh.
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


# Wie die von _BRANDS gefundenen Betreiber geschrieben werden (Treffer in Kleinschreibung → Anzeigename).
_OPERATOR_NAMES = {
    "enbw": "EnBW", "ionity": "IONITY", "fastned": "Fastned", "allego": "Allego", "aral pulse": "Aral pulse",
    "bp pulse": "bp pulse", "shell recharge": "Shell Recharge", "shell": "Shell Recharge", "ewe go": "EWE Go", "e.on": "E.ON", "e.on drive": "E.ON Drive",
    "eon drive": "E.ON Drive", "vattenfall": "Vattenfall", "maingau": "Maingau", "pfalzwerke": "Pfalzwerke",
    "electra": "Electra", "atlante": "Atlante", "zunder": "Zunder", "plugsurfing": "Plugsurfing",
    "wirelane": "Wirelane", "elli": "Elli", "qwello": "Qwello", "chargepoint": "ChargePoint", "monta": "Monta",
    "virta": "Virta", "greenway": "GreenWay", "iberdrola": "Iberdrola", "endesa": "Endesa",
    "instavolt": "InstaVolt", "osprey": "Osprey", "gridserve": "Gridserve", "pod point": "Pod Point",
    "totalenergies": "TotalEnergies", "lidl": "Lidl", "kaufland": "Kaufland", "aldi": "Aldi",
    "stadtwerke": "Stadtwerke", "mobility+": "Mobility+", "be charge": "Be Charge", "ladenetz": "ladenetz.de",
    "innogy": "innogy", "easycharger": "EasyCharger",
}


def known_operators() -> list[str]:
    """Die Betreiber, die Ladecockpit mit Namen kennt, zur Auswahl aus einer Liste."""
    return sorted(set(_OPERATOR_NAMES.values()) - {"Stadtwerke", "Lidl", "Kaufland", "Aldi"}, key=str.casefold)


def operator(site: str | None) -> str | None:
    """Das Ladenetz, das ein Standortname nennt („EnBW Ladepark Südstadt“ → „EnBW“), falls vorhanden."""
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
    """Orte in deinen eigenen Standortnamen: der Ort eines Superchargers („Bergstadt, Germany“,
    „Seestadt - Center, Germany“) und der Ort nach dem Komma einer Adresse
    („Brunnenhausstr. 46, Neustadt“). Sie unterscheiden „Neustadt - KiK“ (Ort zuerst) von
    „Hyper Charge - Musterstadt“ (Netz zuerst)."""
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
    """Das Netz hinter einem Fremdstandort: eine bekannte Marke, sonst der Teil vor dem Bindestrich,
    wie Tesla MultiPass-Standorte schreibt („Hyper Charge - Musterstadt“ → „Hyper Charge“).
    Ein Teil vor dem Bindestrich, der in `places` steht, ist ein Ort, kein Netz („Neustadt - KiK“)."""
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
    """(Netz, Grund) für einen Roh-Datensatz der Tesla-Ladehistorie."""
    if not raw:
        return SUPERCHARGER, None
    # Die Rechnungsnummer entscheidet, vor jedem Hinweis: Ein Supercharger auf einem Supermarktparkplatz
    # bleibt ein Supercharger, eine MultiPass-Station mit schlichter Adresse bleibt MultiPass.
    for inv in raw.get("invoices") or []:
        name = inv.get("fileName") if isinstance(inv, dict) else None
        network = _SERIES.get(invoice_series(name) or "")
        if network:
            return network, f"invoice {name}"
    # Ein Standort, dem der Nutzer einen Betreiber zugeordnet hat, ist eine Fremdstation.
    if assigned_operator(raw.get("siteLocationName")):
        return MULTIPASS, "operator assigned in the settings"
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
    if _min_price > 0 and not looks_like_supercharger(site):
        rate = kwh_rate(raw)
        if rate and rate[1] == "EUR" and rate[0] > _min_price:
            return MULTIPASS, f"price {rate[0]:.2f} EUR/kWh, site not like a Supercharger"
    return SUPERCHARGER, None


def unknown_keys(raw: dict) -> list[str]:
    return sorted(set(raw) - KNOWN_KEYS)

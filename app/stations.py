"""Wo eine MultiPass-Ladung war und wer die Station betreibt.

Teslas Ladehistorie hat nur den Standortnamen, den der Stationsbetreiber vergeben hat („Neustadt - KiK“,
„Brunnenhausstr. 46, Neustadt“). Die Rechnung einer MultiPass-Ladung ergänzt die Adresse der Station,
nennt den Betreiber aber auch nicht:

    Ladestation
    Brunnenhausstr. 46, Neustadt
    Brunnenhausstraße 46
    12301 Neustadt DE

In Deutschland muss jeder öffentliche Ladepunkt bei der Bundesnetzagentur gemeldet sein, und deren
Register (offene Daten, monatlich aktualisiert) führt den Betreiber mit der Adresse. Für eine deutsche
Adresse sucht Ladecockpit die Station deshalb dort: gleiche Postleitzahl, gleiche Straße und dieselbe
oder die nächste Hausnummer. Das Register hat etwa 50 MB; es wird nur geladen, wenn eine Station noch
nicht bekannt ist (höchstens alle REGISTER_MIN_GAP), Zeile für Zeile gelesen, und nur die Zeilen der
gebrauchten Postleitzahlen bleiben. Außerhalb Deutschlands oder ohne Treffer im Register wird
OpenStreetMap gefragt (siehe osm.py); verrät auch das nichts, kommt der Betreiber aus dem
Standortnamen (eine bekannte Marke oder der Teil vor dem Bindestrich).
"""
from __future__ import annotations

import asyncio
import csv
import logging
import re
import tempfile
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from . import networks, operators

log = logging.getLogger("ladecockpit.stations")

# Seiten der Bundesnetzagentur, die das aktuelle Register verlinken (der Dateiname trägt sein Datum).
REGISTER_PAGES = (
    "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html",
    "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/DownloadundKontakt.html",
)
_REGISTER_LINK = re.compile(r"""(https?://data\.bundesnetzagentur\.de)?(/[^"'<>\s]*?Ladesaeulenregister[^"'<>\s]*?\.csv)""", re.I)
REGISTER_HEADER = "Ladeeinrichtungs-ID"
REGISTER_MIN_GAP = timedelta(hours=12)   # das Register nie öfter laden
RETRY_UNMATCHED = timedelta(days=30)     # eine Station, die das Register nicht hatte: danach erneut suchen
NEAR_NUMBER = 20                          # so nahe Hausnummern zählen als derselbe Standort
STREET_LIKENESS = 0.9                     # so ähnliche Straßennamen sind dieselbe Straße
MATCH_VERSION = 2                         # nach einer älteren Regel zugeordnete Stationen werden neu gesucht

# Beschriftungen des Stationsblocks in der Rechnung, je Sprache.
_STATION_LABELS = ("ladestation", "charging station", "station de recharge", "laadstation", "laadpaal",
                   "stazione di ricarica", "estación de carga", "ladestasjon", "laddstation", "ladestation:")
_TABLE_START = re.compile(r"^(event-datum|event date|date|datum|beschreibung|description)\b", re.I)
_POSTCODE_LINE = re.compile(r"^(?P<code>[A-Z]{0,2}-?\d{4,5}(?:\s?[A-Z]{2})?)\s+(?P<city>.+?)(?:\s+(?P<country>[A-Z]{2}))?$")
_STREET_LINE = re.compile(r"^(?P<street>.*?\D)[\s,]+(?P<number>\d+\s?[a-zA-Z]?(?:\s?[-/]\s?\d+\s?[a-zA-Z]?)?)$")


# --- the invoice ------------------------------------------------------------------------------------
def station_from_text(text: str) -> dict | None:
    """Name und Adresse der Station aus dem Text einer MultiPass-Rechnung, oder None.

    {"name", "street", "number", "postcode", "city", "country"}; Teile, die die Rechnung nicht hat,
    fehlen."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    for i, line in enumerate(lines):
        if line.casefold().rstrip(":") not in _STATION_LABELS:
            continue
        block = []
        for nxt in lines[i + 1:i + 6]:
            if not nxt or _TABLE_START.match(nxt):
                break
            block.append(nxt)
        if not block:
            return None
        out: dict = {"name": block[0]}
        for j in range(len(block) - 1, 0, -1):
            m = _POSTCODE_LINE.match(block[j])
            if not m:
                continue
            out["postcode"] = m.group("code").replace(" ", "")
            out["city"] = m.group("city").strip()
            if m.group("country"):
                out["country"] = m.group("country")
            street = block[j - 1] if j - 1 >= 1 else None
            if street:
                s = _STREET_LINE.match(street)
                if s:
                    out["street"], out["number"] = s.group("street").strip(" ,"), s.group("number").replace(" ", "")
                else:
                    out["street"] = street
            break
        return out
    return None


def address(station: dict | None) -> str | None:
    """„Brunnenhausstraße 46, Neustadt“ – Straße und Ort einer Station, soweit bekannt."""
    if not station:
        return None
    street = " ".join(filter(None, (station.get("street"), station.get("number"))))
    return ", ".join(filter(None, (street, station.get("city")))) or None


def full_address(station: dict | None) -> str | None:
    """"Brunnenhausstraße 46, 12301 Neustadt" – for a map search."""
    if not station:
        return None
    street = " ".join(filter(None, (station.get("street"), station.get("number"))))
    town = " ".join(filter(None, (station.get("postcode"), station.get("city"))))
    return ", ".join(filter(None, (street, town))) or None


# --- names --------------------------------------------------------------------------------------------
_LEGAL = re.compile(
    r"(,?\s*\b(?:gmbh\s*(?:&|und)\s*co\.?\s*kg(?:aa)?|ag\s*(?:&|und)\s*co\.?\s*kg|se\s*(?:&|und)\s*co\.?\s*o?hg|"
    r"(?:&|und)\s*co\.?\s*kg|co\.?\s*kg|gmbh|mbh|ggmbh|aktiengesellschaft|ag|se|kgaa|kg|ohg|gbr|e\.\s?v\.?|ev|"
    r"e\.\s?k\.?|ug\s*\(haftungsbeschränkt\)|ug|b\.\s?v\.?|bv|n\.\s?v\.?|nv|s\.\s?a\.?\s?s?|sas|s\.\s?r\.\s?l\.?|srl|"
    r"s\.\s?p\.\s?a\.?|spa|ltd\.?|limited|inc\.?|llc|aps|a/s|oy|ab)(?=$|[\s,.)]))", re.I)
# Public bodies carry their legal form in words: "Sparkasse X Anstalt des öffentlichen Rechts …"
_PUBLIC_BODY = re.compile(r"\s+(?:anstalt|körperschaft|zweckverband)\b", re.I)
MAX_NAME = 40
# Marken in einem Standortnamen, die Laden beherbergen statt betreiben: Das Register weiß besser, wer betreibt
HOST_BRANDS = {"Aldi", "Lidl", "Kaufland", "Stadtwerke", "Mobility+"}
# In einem Standortnamen genannte Marken, die zu allgemein sind, um für den Betreiber zu stehen
_GENERIC_BRANDS = {"Stadtwerke", "Mobility+"}


def clean_operator(name: str | None) -> str | None:
    """Der Betreiber, wie man ihn nennt: „SWN ENERGIE GmbH“ → „SWN ENERGIE“,
    „EnBW mobility+ AG und Co.KG“ → „EnBW“, „Allego GmbH“ → „Allego“,
    „Enel X Way Italia S.r.l.“ → „Enel X Way“ (siehe operators.ALIASES)."""
    name = " ".join((name or "").split())
    if not name:
        return None
    brand = networks.operator(name)
    if brand and brand not in _GENERIC_BRANDS and re.match(re.escape(brand.split()[0]), name, re.I):
        return brand
    short = name
    for _ in range(4):
        cut = _LEGAL.sub("", short).strip(" ,.-&")
        if cut == short:
            break
        short = cut
    short = re.sub(r"\s+(?:&|und)$", "", short).strip(" ,.-")
    short = _PUBLIC_BODY.split(short)[0].strip(" ,.-") or short
    known = operators.brand(short)
    if known:
        return known
    if len(short) > MAX_NAME:
        short = short[:MAX_NAME].rsplit(" ", 1)[0].strip(" ,.-&")
    return short or name


def registered_name(operator: str | None, shown: str | None) -> str | None:
    """Der Name eines Betreibers im Register: sein Kartenname, wenn das der Kurzname des Betreibers ist
    („SEW“ für „SEW Seestadt Energie und Wasser GmbH“, „ALDI SÜD“ für „ALDI SÜD Immobilien-
    verwaltungs-GmbH & Co. oHG“), sonst der Firmenname. Ein Kartenname, der etwas anderes nennt
    (ein Autohaus und seinen Ort), wird nicht genutzt."""
    operator, shown = (operator or "").strip(), (shown or "").strip()
    if shown and operator and shown.split()[0].casefold() in re.split(r"[\s&,/-]+", operator.casefold()):
        return shown
    return operator or shown or None


def operator_label(station: dict | None, site: str | None, places: frozenset[str] = frozenset()) -> str | None:
    """Wer eine MultiPass-Station betreibt: aus dem Register, wenn es die Adresse hat, sonst aus dem
    Standortnamen. Eine Marke im Standortnamen, die ihr erstes Wort mit dem gemeldeten Betreiber teilt,
    ist genauer („Aral pulse“ statt „Aral“) und gewinnt."""
    assigned = networks.assigned_operator(site, (station or {}).get("name"), full_address(station))
    if assigned:
        return assigned  # was der Nutzer von Hand gesetzt hat, hat das letzte Wort
    from_site = networks.operator_from_site(site, places)
    registered = registered_name((station or {}).get("operator"), (station or {}).get("operator_shown"))
    brand = networks.operator(site)
    if registered and brand and brand not in HOST_BRANDS:
        return brand
    if registered:
        label = clean_operator(registered)
        if from_site and label and from_site.split()[0].casefold() in label.casefold().split():
            return from_site
        return label
    return from_site


def describe(sessions: list[dict]) -> None:
    """"_operator" und "_address" an den MultiPass-Ladungen einer Liste setzen (direkt in der Liste)."""
    places = networks.place_names(x.get("site") for x in sessions)
    for x in sessions:
        if (x.get("network") or networks.SUPERCHARGER) == networks.MULTIPASS:
            x["_operator"] = operator_label(x.get("station"), x.get("site"), places)
            x["_address"] = address(x.get("station"))


# --- das Register der Bundesnetzagentur ---------------------------------------------------------
def norm_street(street: str | None) -> str:
    s = (street or "").casefold().replace("ß", "ss")
    s = re.sub(r"str(?:asse|\.|\b)", "str", s)
    return re.sub(r"[^0-9a-zäöü]+", "", s)


def norm_number(number: str | None) -> tuple[int | None, str]:
    """(first number, full text) of a house number: "27-29" → (27, "27-29")."""
    text = re.sub(r"\s+", "", (number or "").casefold())
    m = re.match(r"\d+", text)
    return (int(m.group(0)) if m else None), text


def _number_distance(a: str | None, b: str | None) -> int | None:
    (na, ta), (nb, tb) = norm_number(a), norm_number(b)
    if ta and ta == tb:
        return 0
    if na is None or nb is None:
        return None
    return abs(na - nb)


def _street_likeness(a: str, b: str) -> float:
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


def match_operator(station: dict, rows: list[dict]) -> dict | None:
    """Die Registerzeile zu einer Station: gleiche Postleitzahl und Straße (ähnlich geschrieben: Register und
    Rechnung sind sich bei „Brunnenhausstr.“ und „Brunnenhaustraße“ nicht immer einig), dann dieselbe oder die
    nächste Hausnummer (innerhalb von NEAR_NUMBER), dann die ähnlichere Schreibweise. None, wenn die Straße
    nicht im Register steht."""
    street = norm_street(station.get("street"))
    if not street:
        return None
    best = None
    for r in rows:
        if r["postcode"] != station.get("postcode"):
            continue
        like = _street_likeness(street, norm_street(r["street"]))
        if like < STREET_LIKENESS:
            continue
        d = _number_distance(station.get("number"), r["number"])
        if d is None:
            d = NEAR_NUMBER  # auf einer Seite keine Nummer: nur, wenn nichts Besseres da ist
        if d <= NEAR_NUMBER and (best is None or (d, -like) < best[0]):
            best = ((d, -like), r)
    return best[1] if best else None


def find_register_url(pages: list[str]) -> str | None:
    """Link zur neuesten Register-CSV auf den Seiten der Bundesnetzagentur."""
    found = []
    for html in pages:
        for host, path in _REGISTER_LINK.findall(html or ""):
            found.append((host or "https://data.bundesnetzagentur.de") + path)
    if not found:
        return None
    return max(found, key=lambda u: (re.findall(r"\d{4}-\d{2}-\d{2}", u) or [""])[-1])


def read_register(path: Path, postcodes: set[str]) -> list[dict]:
    """Zeilen der Register-CSV für die angegebenen Postleitzahlen (Betreiber, Straße, Nummer, PLZ, Ort)."""
    raw = path.read_bytes()[:200_000]
    try:
        raw.decode("utf-8")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        encoding = "cp1252"
    rows = []
    with open(path, encoding=encoding, errors="replace", newline="") as f:
        header = None
        for line in f:
            if line.lstrip('﻿"').startswith(REGISTER_HEADER):
                header = next(csv.reader([line], delimiter=";"))
                break
        if header is None:
            raise ValueError("register: header line not found")
        col = {name.strip(): i for i, name in enumerate(header)}
        need = ("Betreiber", "Straße", "Hausnummer", "Postleitzahl", "Ort")
        missing = [n for n in need if n not in col]
        if missing:
            raise ValueError(f"register: columns missing: {', '.join(missing)}")
        for cells in csv.reader(f, delimiter=";"):
            if len(cells) <= col["Ort"]:
                continue
            postcode = cells[col["Postleitzahl"]].strip()
            if postcode not in postcodes:
                continue
            shown = col.get("Anzeigename (Karte)")
            rows.append({"operator": cells[col["Betreiber"]].strip(),
                         "shown": cells[shown].strip() if shown is not None and shown < len(cells) else "",
                         "street": cells[col["Straße"]].strip(),
                         "number": cells[col["Hausnummer"]].strip(), "postcode": postcode,
                         "city": cells[col["Ort"]].strip()})
    return rows


class Register:
    """Sucht die Betreiber deutscher Stationen im Register der Bundesnetzagentur."""

    def __init__(self, data_dir: Path, transport: httpx.AsyncBaseTransport | None = None):
        self.data_dir = data_dir
        self.transport = transport
        self.last_download: datetime | None = None

    async def rows_for(self, postcodes: set[str]) -> list[dict] | None:
        """Registerzeilen für einige Postleitzahlen, oder None, wenn das Register gerade nicht verfügbar ist."""
        now = datetime.now(timezone.utc)
        if self.last_download and now - self.last_download < REGISTER_MIN_GAP:
            return None
        self.last_download = now
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=300), follow_redirects=True,
                                     transport=self.transport,
                                     headers={"User-Agent": "Ladecockpit (Home Assistant app)"}) as client:
            pages = []
            for url in REGISTER_PAGES:
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        pages.append(r.text)
                except httpx.HTTPError:
                    continue
            url = find_register_url(pages)
            if not url:
                log.warning("Charging station register: no download link found")
                return None
            folder = self.data_dir / "tmp"
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=folder, suffix=".csv", delete=False) as tmp:
                path = Path(tmp.name)
                try:
                    async with client.stream("GET", url) as r:
                        r.raise_for_status()
                        async for chunk in r.aiter_bytes(1 << 16):
                            tmp.write(chunk)
                except httpx.HTTPError as e:
                    log.warning("Charging station register: download failed (%s)", e)
                    path.unlink(missing_ok=True)
                    return None
        try:
            rows = await asyncio.to_thread(read_register, path, postcodes)
            log.info("Charging station register %s: %d rows for %d postcodes", url.rsplit("/", 1)[-1], len(rows), len(postcodes))
            return rows
        except (OSError, ValueError, csv.Error) as e:
            log.warning("Charging station register could not be read: %s", e)
            return None
        finally:
            path.unlink(missing_ok=True)


def due_for_lookup(station: dict | None, now: datetime) -> bool:
    """Eine deutsche Station, deren Betreiber noch nicht gesucht oder vor 30 Tagen nicht gefunden wurde."""
    if not station or not station.get("postcode") or not station.get("street"):
        return False
    if (station.get("country") or "DE") != "DE":
        return False
    checked = station.get("checked")
    if not checked or station.get("match_v", 1) < MATCH_VERSION:
        return True
    if station.get("operator"):
        return False
    try:
        return now - datetime.fromisoformat(checked) >= RETRY_UNMATCHED
    except ValueError:
        return True

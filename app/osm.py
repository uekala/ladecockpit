"""Wer eine Station betreibt, aus OpenStreetMap.

Außerhalb Deutschlands gibt es kein Register, das Ladecockpit lesen könnte, und das deutsche Register
hat nicht jede Station. OpenStreetMap verzeichnet Ladestationen in ganz Europa, die meisten mit
Betreiber. Für eine Station ohne Betreiber fragt Ladecockpit deshalb zwei öffentliche Dienste:

1. Nominatim macht aus der Adresse auf der Rechnung eine Koordinate.
2. Overpass listet die Ladestationen rund um diese Koordinate mit ihren Tags.

Der Betreiber wird nur übernommen, wenn die Karte keinen Zweifel lässt (siehe `pick`); sonst bleibt die
Station lieber ohne als mit falschem Namen. Beide Dienste sind kostenlos und geteilt: höchstens eine
Adresse pro Sekunde, wenige Adressen je Abgleich, jede Adresse nur einmal (nach RETRY erneut, wenn
nichts gefunden wurde). Gesendet wird nur die Adresse der Station.

Daten © OpenStreetMap-Mitwirkende, ODbL.
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta

import httpx

from . import __version__, networks

log = logging.getLogger("ladecockpit.osm")

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = f"Ladecockpit/{__version__} (+https://github.com/uekala/ladecockpit)"
PAUSE_S = 1.1                  # between two requests (Nominatim allows one per second)
PER_SYNC = 8                   # addresses looked up in one sync
RETRY = timedelta(days=30)     # eine Station, die die Karte nicht kannte: danach erneut suchen
VERSION = 2                    # nach einer älteren Regel gesuchte Stationen werden neu gesucht
WIDE_M = 400                   # wie weit rund um die Adresse Stationen betrachtet werden
CLEAR_M = 50                   # die nächste Station muss so nah sein und die übernächste so viel weiter
HOUSE_RANK = 28                # Nominatim: place_rank ab hier ist ein Haus oder ein Ort an einer Straße


class Unavailable(Exception):
    """Ein Kartendienst hat nicht geantwortet; beim nächsten Abgleich erneut versuchen."""


def due(station: dict | None, now: datetime, register_first: bool = True) -> bool:
    """Eine Station mit Adresse und ohne Betreiber, nach der die Karte noch nicht gefragt wurde oder
    vor RETRY ohne Ergebnis. Deutsche Stationen warten auf das Register, wenn es genutzt wird."""
    if not station or station.get("operator") or not station.get("street"):
        return False
    if not (station.get("city") or station.get("postcode")):
        return False
    german = (station.get("country") or "DE") == "DE" and station.get("postcode")
    if register_first and german and not station.get("checked"):
        return False
    checked = station.get("map_checked")
    if not checked or station.get("map_v", 0) < VERSION:
        return True
    try:
        return now - datetime.fromisoformat(checked) >= RETRY
    except ValueError:
        return True


def key(station: dict) -> tuple[str, ...]:
    """What makes two stations the same address."""
    return tuple(" ".join(str(station.get(k) or "").casefold().split())
                 for k in ("street", "number", "postcode", "city", "country"))


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(a))


def name_of(tags: dict) -> str | None:
    """Der Betreiber in den Tags einer Ladestation: die Marke, die man sieht, außer es ist der Laden,
    an dem die Station steht; dann wer sie betreibt, dann das Netz, zu dem sie gehört."""
    brand, operator, network = (" ".join((tags.get(k) or "").split()) for k in ("brand", "operator", "network"))
    if brand and networks.operator(brand) in {"Aldi", "Lidl", "Kaufland"} and operator:
        return operator
    return brand or operator or network or None


def _position(element: dict) -> tuple[float, float] | None:
    at = element if "lat" in element else element.get("center") or {}
    try:
        return float(at["lat"]), float(at["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def judge(elements: list[dict], lat: float, lon: float, exact: bool) -> tuple[dict | None, str]:
    """Der Betreiber der Station an einer Koordinate, oder None, wenn die Karte Zweifel lässt – und in
    beiden Fällen ein paar Worte zum Grund, fürs Log.

    Eine Station ohne Betreiber auf der Karte zählt als eigener Betreiber: Ist sie die nächste, lautet
    die Antwort „nicht bekannt“. Teslas eigene Stationen bleiben außen vor; dort war keine MultiPass-Ladung.

    - Alle Stationen innerhalb von WIDE_M haben einen Betreiber: dieser.
    - Mehrere Betreiber, Adresse bis aufs Haus gefunden: Die nächste gewinnt, wenn sie innerhalb von
      CLEAR_M liegt und der nächste Betreiber mindestens CLEAR_M weiter weg ist.
    - Mehrere Betreiber, Adresse nur bis zur Straße gefunden: nicht bekannt.
    """
    nearest: dict[str, tuple[float, str | None]] = {}
    for e in elements:
        pos = _position(e)
        if not pos:
            continue
        name = name_of(e.get("tags") or {})
        if name and networks._TESLA_WORDS.search(name):
            continue
        d = distance_m(lat, lon, *pos)
        if d > WIDE_M:
            continue
        k = name.casefold() if name else ""
        if k not in nearest or d < nearest[k][0]:
            nearest[k] = (d, name)
    ranked = sorted(nearest.values(), key=lambda x: x[0])
    if not ranked:
        return None, f"no charging station within {WIDE_M} m on the map"
    best_d, best = ranked[0]
    if len(ranked) > 1:
        clear = exact and best_d <= CLEAR_M and ranked[1][0] - best_d >= CLEAR_M
        if not clear:
            near = ", ".join(f"{name or 'no operator'} {round(d)} m" for d, name in ranked[:4])
            how = "" if exact else ", address found to the street only"
            return None, f"several operators nearby ({near}){how}"
    if not best:
        return None, f"the station {round(best_d)} m away has no operator on the map"
    return {"operator": best, "distance": round(best_d)}, f"{best}, {round(best_d)} m away"


def pick(elements: list[dict], lat: float, lon: float, exact: bool) -> dict | None:
    """Der Betreiber der Station an einer Koordinate, oder None, wenn die Karte Zweifel lässt (siehe judge)."""
    return judge(elements, lat, lon, exact)[0]


class Lookup:
    """Fragt Nominatim und Overpass nach dem Betreiber an einer Adresse."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, pause_s: float = PAUSE_S):
        self.transport = transport
        self.pause_s = pause_s
        self.why = ""  # ein paar Worte zur letzten Antwort, fürs Log

    async def operator(self, station: dict) -> dict | None:
        """{"operator", "distance"} für eine Station, None, wenn die Karte es nicht verrät.
        Wirft Unavailable, wenn ein Dienst nicht antwortet."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(40), transport=self.transport,
                                     headers={"User-Agent": USER_AGENT}) as client:
            try:
                spot = await self._locate(client, station)
                if not spot:
                    self.why = "the address was not found on the map"
                    return None
                await asyncio.sleep(self.pause_s)
                elements = await self._chargers(client, spot["lat"], spot["lon"])
            except (httpx.HTTPError, ValueError) as e:
                raise Unavailable(str(e) or type(e).__name__) from e
        hit, self.why = judge(elements, spot["lat"], spot["lon"], spot["exact"])
        return hit

    async def _locate(self, client: httpx.AsyncClient, station: dict) -> dict | None:
        street = " ".join(filter(None, (station.get("number"), station.get("street"))))
        town = " ".join(filter(None, (station.get("postcode"), station.get("city"))))
        country = (station.get("country") or "").lower()
        base = {"format": "jsonv2", "limit": "1", "addressdetails": "0"}
        if country:
            base["countrycodes"] = country
        structured = {**base, "street": street}
        if station.get("city"):
            structured["city"] = station["city"]
        if station.get("postcode"):
            structured["postalcode"] = station["postcode"]
        free = {**base, "q": ", ".join(filter(None, (" ".join(filter(None, (station.get("street"), station.get("number")))), town)))}
        for n, params in enumerate((structured, free)):
            if n:
                await asyncio.sleep(self.pause_s)
            r = await client.get(NOMINATIM, params=params)
            if r.status_code != 200:
                raise Unavailable(f"Nominatim answered {r.status_code}")
            found = r.json()
            if found:
                hit = found[0]
                return {"lat": float(hit["lat"]), "lon": float(hit["lon"]),
                        "exact": int(hit.get("place_rank") or 0) >= HOUSE_RANK}
        return None

    async def _chargers(self, client: httpx.AsyncClient, lat: float, lon: float) -> list[dict]:
        query = (f'[out:json][timeout:25];nwr(around:{WIDE_M},{lat:.6f},{lon:.6f})'
                 f'["amenity"="charging_station"];out center tags;')
        r = await client.post(OVERPASS, data={"data": query})
        if r.status_code != 200:
            raise Unavailable(f"Overpass answered {r.status_code}")
        return r.json().get("elements") or []

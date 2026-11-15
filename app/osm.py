"""Who runs a station, from OpenStreetMap.

Outside Germany there is no register Ladecockpit could read, and the German register does not have
every station. OpenStreetMap maps charging stations all over Europe, most with their operator. So
for a station without an operator Ladecockpit asks two public services:

1. Nominatim turns the address from the invoice into a coordinate.
2. Overpass lists the charging stations around that coordinate with their tags.

The operator is only taken when the map leaves no doubt (see `pick`); otherwise the station stays
without one rather than getting a wrong name. Both services are free and shared: one address per
second at most, a few addresses per sync, every address only once (again after RETRY when nothing
was found). Only the address of the station is sent.

Data © OpenStreetMap contributors, ODbL.
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
RETRY = timedelta(days=30)     # a station the map did not know: look again after this
VERSION = 1                    # stations looked up by an older rule are looked up again
WIDE_M = 400                   # how far around the address stations are looked at
CLEAR_M = 50                   # the nearest station must be this close, and the next this much farther
HOUSE_RANK = 28                # Nominatim: place_rank from here on is a house or a place on a street


class Unavailable(Exception):
    """A map service did not answer; try again with the next sync."""


def due(station: dict | None, now: datetime, register_first: bool = True) -> bool:
    """A station with an address and no operator that the map has not been asked about, or was
    asked RETRY ago without a result. German stations wait for the register when it is in use."""
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
    """The operator in the tags of a charging station: the brand people see, unless that is the
    shop the station stands at; then who runs it, then the network it belongs to."""
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


def pick(elements: list[dict], lat: float, lon: float, exact: bool) -> dict | None:
    """The operator of the station at a coordinate, or None when the map leaves a doubt.

    A station without an operator on the map counts as one of its own: when it is the nearest, the
    answer is "not known". Tesla's own stations are left out; a MultiPass session was not there.

    - All stations within WIDE_M are of one operator: that one.
    - Several operators, address found to the house: the nearest wins when it is within CLEAR_M and
      the next operator is at least CLEAR_M farther.
    - Several operators, address found to the street only: not known.
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
        return None
    best_d, best = ranked[0]
    if len(ranked) > 1:
        clear = exact and best_d <= CLEAR_M and ranked[1][0] - best_d >= CLEAR_M
        if not clear:
            return None
    return {"operator": best, "distance": round(best_d)} if best else None


class Lookup:
    """Asks Nominatim and Overpass for the operator at an address."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, pause_s: float = PAUSE_S):
        self.transport = transport
        self.pause_s = pause_s

    async def operator(self, station: dict) -> dict | None:
        """{"operator", "distance"} for a station, None when the map does not tell.
        Raises Unavailable when a service does not answer."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(40), transport=self.transport,
                                     headers={"User-Agent": USER_AGENT}) as client:
            try:
                spot = await self._locate(client, station)
                if not spot:
                    return None
                await asyncio.sleep(self.pause_s)
                elements = await self._chargers(client, spot["lat"], spot["lon"])
            except (httpx.HTTPError, ValueError) as e:
                raise Unavailable(str(e) or type(e).__name__) from e
        return pick(elements, spot["lat"], spot["lon"], spot["exact"])

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

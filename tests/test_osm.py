import asyncio
import dataclasses
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app import osm, stations
from app.sync import SyncService
from app.tesla import parse_session

REAL_LOOKUP = osm.Lookup.operator   # conftest ersetzt sie für jeden Test
NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
HAFEN = {"name": "Hafenstadt", "street": "Kadeweg", "number": "12", "postcode": "2980 AB", "city": "Hafenstadt", "country": "NL"}
LAT, LON = 51.9, 4.6


def charger(metres_north, **tags):
    return {"type": "node", "lat": LAT + metres_north / 111_195, "lon": LON, "tags": {"amenity": "charging_station", **tags}}


def test_which_stations_are_due():
    assert osm.due(HAFEN, NOW)
    assert not osm.due({**HAFEN, "operator": "Fastned"}, NOW)                      # hat schon einen
    assert not osm.due({"name": "x", "city": "Hafenstadt"}, NOW)                   # keine Straße zum Suchen
    assert not osm.due({**HAFEN, "map_checked": NOW.isoformat(), "map_v": osm.VERSION}, NOW)
    old = (NOW - osm.RETRY).isoformat()
    assert osm.due({**HAFEN, "map_checked": old, "map_v": osm.VERSION}, NOW)        # not found a month ago
    assert osm.due({**HAFEN, "map_checked": NOW.isoformat(), "map_v": 0}, NOW)      # older rule
    german = {"street": "Hauptstraße", "postcode": "12309", "city": "Neustadt"}
    assert not osm.due(german, NOW)                                                 # the register comes first
    assert osm.due({**german, "checked": NOW.isoformat()}, NOW)                     # … und hatte sie nicht
    assert osm.due(german, NOW, register_first=False)                               # register switched off


def test_one_operator_around_the_address():
    assert osm.pick([charger(20, operator="Fastned"), charger(180, brand="Fastned")], LAT, LON, True) == {"operator": "Fastned", "distance": 20}
    assert osm.pick([charger(300, operator="Fastned")], LAT, LON, False)["operator"] == "Fastned"   # street only
    assert osm.pick([charger(500, operator="Fastned")], LAT, LON, True) is None                    # too far
    assert osm.pick([], LAT, LON, True) is None


def test_several_operators_need_a_clear_nearest():
    near, far = charger(15, operator="Fastned"), charger(120, operator="Shell Recharge")
    assert osm.pick([near, far], LAT, LON, True)["operator"] == "Fastned"
    assert osm.pick([near, far], LAT, LON, False) is None                           # street only: no guess
    assert osm.pick([near, charger(40, operator="Allego")], LAT, LON, True) is None  # side by side
    assert osm.pick([charger(80, operator="Fastned"), charger(200, operator="Allego")], LAT, LON, True) is None  # nearest not close


def test_unnamed_and_tesla_stations():
    # eine nähere Station ohne Betreiber lässt den Zweifel
    assert osm.pick([charger(10), charger(30, operator="Allego")], LAT, LON, True) is None
    assert osm.pick([charger(10)], LAT, LON, True) is None
    # eine MultiPass-Ladung war nicht an einem Supercharger
    assert osm.pick([charger(10, operator="Tesla, Inc.", brand="Tesla Supercharger"), charger(60, operator="Fastned")], LAT, LON, True)["operator"] == "Fastned"


def test_name_from_the_tags():
    assert osm.name_of({"brand": "Aral pulse", "operator": "Aral AG"}) == "Aral pulse"
    assert osm.name_of({"brand": "Lidl", "operator": "Allego"}) == "Allego"         # der Laden beherbergt sie nur
    assert osm.name_of({"network": "Powerdot"}) == "Powerdot"
    assert osm.name_of({"amenity": "charging_station"}) is None


def test_company_names_become_brands():
    assert stations.clean_operator("Enel X Way Italia S.r.l.") == "Enel X Way"
    assert stations.clean_operator("The New Motion B.V.") == "Shell Recharge"
    assert stations.clean_operator("Aral AG") == "Aral pulse"
    assert stations.clean_operator("Fastned Nederland B.V.") == "Fastned"
    assert stations.operator_label({**HAFEN, "operator": "Fastned B.V.", "operator_src": "osm"}, "Hafenstadt") == "Fastned"


def lookup(handler):
    return osm.Lookup(transport=httpx.MockTransport(handler), pause_s=0)


def test_lookup_asks_both_services():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "nominatim.openstreetmap.org":
            return httpx.Response(200, json=[{"lat": str(LAT), "lon": str(LON), "place_rank": 30}])
        return httpx.Response(200, json={"elements": [{"type": "way", "center": {"lat": LAT, "lon": LON}, "tags": {"operator": "Fastned"}}]})

    assert asyncio.run(REAL_LOOKUP(lookup(handler), HAFEN)) == {"operator": "Fastned", "distance": 0}
    geo, around = seen
    assert dict(geo.url.params) == {"format": "jsonv2", "limit": "1", "addressdetails": "0", "countrycodes": "nl",
                                    "street": "12 Kadeweg", "city": "Hafenstadt", "postalcode": "2980 AB"}
    assert geo.headers["user-agent"].startswith("Ladecockpit/")
    assert around.url.host == "overpass-api.de" and b"charging_station" in around.content and b"around%3A400" in around.content


def test_lookup_falls_back_to_the_plain_address():
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "nominatim.openstreetmap.org":
            asked.append(dict(request.url.params))
            if "q" not in request.url.params:
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[{"lat": str(LAT), "lon": str(LON), "place_rank": 26}])
        return httpx.Response(200, json={"elements": [charger(15, operator="Fastned"), charger(120, operator="Allego")]})

    # nur bis zur Straße gefunden, dort zwei Betreiber: nicht bekannt
    assert asyncio.run(REAL_LOOKUP(lookup(handler), HAFEN)) is None
    assert asked[1]["q"] == "Kadeweg 12, 2980 AB Hafenstadt"


def test_lookup_unknown_address_and_busy_service():
    assert asyncio.run(REAL_LOOKUP(lookup(lambda r: httpx.Response(200, json=[])), HAFEN)) is None
    for answer in (httpx.Response(429), httpx.Response(200, text="<html>busy</html>")):
        with pytest.raises(osm.Unavailable):
            asyncio.run(REAL_LOOKUP(lookup(lambda r, a=answer: a), HAFEN))

    def down(request):
        raise httpx.ConnectError("no route")
    with pytest.raises(osm.Unavailable):
        asyncio.run(REAL_LOOKUP(lookup(down), HAFEN))


class FakeMap:
    pause_s = 0

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    async def operator(self, station):
        self.asked.append(station["street"])
        answer = self.answers[station["street"]]
        if isinstance(answer, Exception):
            raise answer
        return answer


def service(settings, db, answers, sessions):
    sync = SyncService(settings, db, None, None)
    sync.map = FakeMap(answers)
    for sid, station in sessions:
        add(db, sid, station)
    return sync


def add(db, sid, station):
    db.upsert_session(parse_session({"sessionId": sid, "siteLocationName": "Hafenstadt",
                                     "chargeStartDateTime": NOW.isoformat(), "fees": [], "invoices": []}), "backfill")
    db.set_station(sid, station)


def stations_of(db):
    return {s["session_id"]: s["station"] for s in db.sessions_with_station()}


def test_sync_asks_each_address_once(settings, db):
    other = {**HAFEN, "street": "Parkweg"}
    sync = service(settings, db, {"Kadeweg": {"operator": "Fastned B.V.", "distance": 12}, "Parkweg": None},
                   [("a", HAFEN), ("b", dict(HAFEN)), ("c", other)])
    assert asyncio.run(sync.lookup_on_map(NOW)) == 2
    assert sorted(sync.map.asked) == ["Kadeweg", "Parkweg"]
    got = stations_of(db)
    assert got["a"]["operator"] == got["b"]["operator"] == "Fastned B.V." and got["a"]["operator_src"] == "osm"
    assert "operator" not in got["c"] and got["c"]["map_v"] == osm.VERSION
    # jetzt ist nichts fällig, und eine spätere Ladung an einer bekannten Adresse wird nicht erneut gefragt
    assert asyncio.run(sync.lookup_on_map(NOW + timedelta(days=1))) == 0
    add(db, "d", dict(other))
    asyncio.run(sync.lookup_on_map(NOW + timedelta(days=2)))
    assert len(sync.map.asked) == 2 and stations_of(db)["d"]["map_checked"] == got["c"]["map_checked"]


def test_sync_leaves_stations_alone_when_the_map_is_down_or_off(settings, db):
    sync = service(settings, db, {"Kadeweg": osm.Unavailable("busy")}, [("a", HAFEN)])
    assert asyncio.run(sync.lookup_on_map(NOW)) == 0
    assert "map_checked" not in stations_of(db)["a"]            # beim nächsten Abgleich erneut gefragt
    sync.s = dataclasses.replace(settings, map_lookup=False)
    assert asyncio.run(sync.lookup_on_map(NOW)) == 0 and len(sync.map.asked) == 1


def test_sync_asks_a_few_addresses_per_sync(settings, db):
    many = [(f"s{i}", {**HAFEN, "street": f"Weg {i}"}) for i in range(osm.PER_SYNC + 3)]
    sync = service(settings, db, {st["street"]: None for _, st in many}, many)
    asyncio.run(sync.lookup_on_map(NOW))
    assert len(sync.map.asked) == osm.PER_SYNC


def test_judge_says_why():
    def station(lat, lon, **tags):
        return {"lat": lat, "lon": lon, "tags": {"amenity": "charging_station", **tags}}

    assert osm.judge([], 52.0, 5.0, True) == (None, "no charging station within 400 m on the map")
    hit, why = osm.judge([station(52.0001, 5.0, operator="Fastned")], 52.0, 5.0, True)
    assert hit["operator"] == "Fastned" and why.startswith("Fastned, ")
    hit, why = osm.judge([station(52.0001, 5.0)], 52.0, 5.0, True)
    assert hit is None and "has no operator on the map" in why
    two = [station(52.0001, 5.0, operator="Fastned"), station(52.0002, 5.0, operator="Allego")]
    hit, why = osm.judge(two, 52.0, 5.0, True)
    assert hit is None and why.startswith("several operators nearby (Fastned 11 m, Allego 22 m)")
    assert osm.judge(two, 52.0, 5.0, False)[1].endswith("address found to the street only")

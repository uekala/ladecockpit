import dataclasses
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from app import demo, networks
from app.analytics import build_dashboard, map_url
from app.entities import build_states


def test_operator_from_site_name():
    assert networks.operator("EnBW Ladepark Südstadt") == "EnBW"
    assert networks.operator("IONITY  Weiskirchen") == "IONITY"
    assert networks.operator("Tesla MultiPass · Shell   Recharge Nordstadt") == "Shell Recharge"
    assert networks.operator("Mainz, Germany") is None and networks.operator(None) is None


def test_map_url_is_a_plain_search_link():
    u = urlparse(map_url("EnBW Ladepark Südstadt & Co"))
    assert u.netloc == "www.google.com" and parse_qs(u.query) == {"api": ["1"], "query": ["EnBW Ladepark Südstadt & Co"]}


def _s(sid, site, day, kwh, total, network="multipass"):
    start = datetime(2026, 10, day, 15, tzinfo=timezone.utc)
    return {"session_id": sid, "site": site, "start_ts": start.isoformat(timespec="seconds"), "stop_ts": None,
            "kwh": kwh, "charge_cost": total, "idle_fee": 0.0, "total": total, "currency": "EUR",
            "price": total / kwh if kwh else None, "invoices": [], "push_state": "pushed", "network": network}


def _dash(settings, sessions):
    return build_dashboard(sessions=sessions, live={"values": {}, "units": {"odometer": "km"}},
                           readings={"soc": [], "soc_last": None, "range_last": None, "odometer": []},
                           settings=settings, meta={}, now=datetime(2026, 10, 24, 12, tzinfo=timezone.utc))


def test_stations_operators_and_entity(settings):
    sessions = [
        _s("a", "EnBW Ladepark Südstadt", 3, 30, 18.0),
        _s("b", "EnBW Ladepark Südstadt", 12, 20, 12.0),
        _s("c", "EnBW Schnelllader Weststadt", 8, 25, 16.25),
        _s("d", "Fastned Nordstadt", 20, 40, 26.0),
        _s("e", "Stadtpark", 1, 0, None),                       # no invoice amount yet: still counts as worked
        _s("f", "Mainz, Germany", 22, 35, 13.3, network="supercharger"),
    ]
    mp = _dash(settings, sessions)["multipass"]
    assert [s["site"] for s in mp["stations"]] == ["Fastned Nordstadt", "EnBW Ladepark Südstadt", "EnBW Schnelllader Weststadt", "Stadtpark"]
    suedstadt = mp["stations"][1]
    assert suedstadt["sessions"] == 2 and suedstadt["kwh"] == 50 and suedstadt["avg_price"] == 0.6
    assert suedstadt["first"] == "2026-10-03" and suedstadt["last"].startswith("2026-10-12") and suedstadt["last_label"] == "Oct 12, 2026"
    assert suedstadt["operator"] == "EnBW" and "Ladepark%20S%C3%BCdstadt" in suedstadt["map_url"]
    stadtpark = mp["stations"][-1]
    assert stadtpark["operator"] is None and stadtpark["sessions"] == 1 and stadtpark["avg_price"] is None
    assert [(o["name"], o["stations"], o["sessions"]) for o in mp["operators"]] == [("EnBW", 2, 3), ("Fastned", 1, 1)]
    assert mp["sessions"] == 5 and mp["kwh"] == 115
    assert mp["text"] == "MultiPass has worked at 4 stations so far – operators: EnBW, Fastned."

    d = _dash(settings, sessions)
    state, attrs = build_states(d, "en")["sensor.ladecockpit_multipass"]
    assert state == "4" and attrs["friendly_name"] == "Ladecockpit MultiPass stations"
    assert attrs["stations"][0] == {"site": "Fastned Nordstadt", "operator": "Fastned", "address": None, "sessions": 1, "kwh": 40.0,
                                    "avg_price": 0.65, "last": "2026-10-20T17:00:00+02:00", "last_label": "Oct 20, 2026",
                                    "map_url": map_url("Fastned Nordstadt")}
    assert attrs["operators"][0]["name"] == "EnBW" and attrs["sessions"] == 5 and attrs["text"] == mp["text"]


def test_operators_from_site_names_without_towns(settings):
    sessions = [
        _s("a", "Allego - ATU Neustadt", 3, 4.9, 3.57),
        _s("b", "Charging Station ALDI SÜD", 4, 1.5, 1.04),
        _s("c", "Brunnenhausstr. 46, Neustadt", 5, 1.2, 0.84),
        _s("d", "Green Energy Nord - AC E5", 6, 1.1, 0.77),
        _s("e", "Neustadt - KiK", 7, 1.2, 0.82),
        _s("f", "Bergstadt, Germany", 8, 30, 12.0, network="supercharger"),
    ]
    mp = _dash(settings, sessions)["multipass"]
    by_site = {s["site"]: s["operator"] for s in mp["stations"]}
    assert by_site == {"Allego - ATU Neustadt": "Allego", "Charging Station ALDI SÜD": "Aldi",
                       "Brunnenhausstr. 46, Neustadt": None, "Green Energy Nord - AC E5": "Green Energy Nord",
                       "Neustadt - KiK": None}
    assert [o["name"] for o in mp["operators"]] == ["Aldi", "Allego", "Green Energy Nord"]


def test_no_multipass_yet(settings):
    d = _dash(settings, [_s("f", "Mainz, Germany", 22, 35, 13.3, network="supercharger")])
    assert d["multipass"] is None
    state, attrs = build_states(d, "de")["sensor.ladecockpit_multipass"]
    assert state == "0" and attrs["stations"] == [] and attrs["text"].startswith("Noch keine MultiPass-Ladung")
    assert attrs["friendly_name"] == "Ladecockpit MultiPass-Stationen"


def test_demo_has_two_stations_in_german(settings):
    d = demo.build_demo(dataclasses.replace(settings, lang="de"))
    mp = d["multipass"]
    assert {s["site"] for s in mp["stations"]} == {"IONITY Weiskirchen", "EnBW Ladepark Darmstadt"}
    assert {o["name"] for o in mp["operators"]} == {"IONITY", "EnBW"}
    assert mp["text"].startswith("MultiPass hat bisher an 2 Stationen funktioniert – Anbieter: ")
    assert all(s["last_label"].count(".") == 2 for s in mp["stations"])   # 20.10.2026


def test_operator_and_address_from_invoice_and_register(settings):
    kw = {"street": "Brunnenhausstraße", "number": "46", "postcode": "12301", "city": "Neustadt", "country": "DE"}
    sessions = [
        {**_s("a", "Brunnenhausstr. 46, Neustadt", 20, 10, 7.0),
         "station": {"name": "Brunnenhausstr. 46, Neustadt", **kw, "operator": "SWN ENERGIE GmbH", "checked": "2026-10-21"}},
        {**_s("b", "Neustadt - KiK", 21, 10, 6.9),
         "station": {"name": "Neustadt - KiK", "street": "Gartenstraße", "number": "237", "postcode": "12309",
                     "city": "Neustadt", "country": "DE", "checked": "2026-10-22"}},       # not in the register
        _s("c", "Neustadt, Germany", 22, 30, 9.3, network="supercharger"),
        _s("d", "Bergstadt, Germany", 23, 30, 11.1, network="supercharger"),
        _s("e", "Bergstadt, Germany", 18, 30, 11.1, network="supercharger"),
    ]
    d = _dash(settings, sessions)
    by_site = {s["site"]: s for s in d["multipass"]["stations"]}
    swn = by_site["Brunnenhausstr. 46, Neustadt"]
    assert swn["operator"] == "SWN ENERGIE" and swn["address"] == "Brunnenhausstraße 46, Neustadt"
    assert swn["operator_source"] == "register" and "Brunnenhausstra%C3%9Fe%2046%2C%2012301%20Neustadt" in swn["map_url"]
    kik = by_site["Neustadt - KiK"]
    assert kik["operator"] is None and kik["address"] == "Gartenstraße 237, Neustadt"   # "Neustadt" is a town, not a network
    assert [o["name"] for o in d["multipass"]["operators"]] == ["SWN ENERGIE"]
    row = next(s for s in d["sessions"] if s["id"] == "a")
    assert row["operator"] == "SWN ENERGIE" and row["address"] == "Brunnenhausstraße 46, Neustadt"
    site = next(s for s in d["sites"] if s["site"] == "Brunnenhausstr. 46, Neustadt")
    assert site["label"] == "SWN ENERGIE (Brunnenhausstraße 46, Neustadt)"
    assert next(s for s in d["sites"] if s["site"] == "Bergstadt, Germany")["label"] == "Bergstadt"

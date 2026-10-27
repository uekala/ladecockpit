import dataclasses
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from app import demo, networks
from app.analytics import build_dashboard, map_url
from app.entities import build_states


def test_operator_from_site_name():
    assert networks.operator("EnBW Ladepark Hilden") == "EnBW"
    assert networks.operator("IONITY  Weiskirchen") == "IONITY"
    assert networks.operator("Tesla MultiPass · Shell   Recharge Venlo") == "Shell Recharge"
    assert networks.operator("Mainz, Germany") is None and networks.operator(None) is None


def test_map_url_is_a_plain_search_link():
    u = urlparse(map_url("EnBW Ladepark Hilden & Co"))
    assert u.netloc == "www.google.com" and parse_qs(u.query) == {"api": ["1"], "query": ["EnBW Ladepark Hilden & Co"]}


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
        _s("a", "EnBW Ladepark Hilden", 3, 30, 18.0),
        _s("b", "EnBW Ladepark Hilden", 12, 20, 12.0),
        _s("c", "EnBW Schnelllader Moers", 8, 25, 16.25),
        _s("d", "Fastned Venlo", 20, 40, 26.0),
        _s("e", "Stadtpark", 1, 0, None),                       # no invoice amount yet: still counts as worked
        _s("f", "Mainz, Germany", 22, 35, 13.3, network="supercharger"),
    ]
    mp = _dash(settings, sessions)["multipass"]
    assert [s["site"] for s in mp["stations"]] == ["Fastned Venlo", "EnBW Ladepark Hilden", "EnBW Schnelllader Moers", "Stadtpark"]
    hilden = mp["stations"][1]
    assert hilden["sessions"] == 2 and hilden["kwh"] == 50 and hilden["avg_price"] == 0.6
    assert hilden["first"] == "2026-10-03" and hilden["last"].startswith("2026-10-12") and hilden["last_label"] == "Oct 12, 2026"
    assert hilden["operator"] == "EnBW" and "Ladepark%20Hilden" in hilden["map_url"]
    stadtpark = mp["stations"][-1]
    assert stadtpark["operator"] is None and stadtpark["sessions"] == 1 and stadtpark["avg_price"] is None
    assert [(o["name"], o["stations"], o["sessions"]) for o in mp["operators"]] == [("EnBW", 2, 3), ("Fastned", 1, 1)]
    assert mp["sessions"] == 5 and mp["kwh"] == 115
    assert mp["text"] == "MultiPass has worked at 4 stations so far – operators: EnBW, Fastned."

    d = _dash(settings, sessions)
    state, attrs = build_states(d, "en")["sensor.ladecockpit_multipass"]
    assert state == "4" and attrs["friendly_name"] == "Ladecockpit MultiPass stations"
    assert attrs["stations"][0] == {"site": "Fastned Venlo", "operator": "Fastned", "sessions": 1, "kwh": 40.0,
                                    "avg_price": 0.65, "last": "2026-10-20T17:00:00+02:00", "last_label": "Oct 20, 2026",
                                    "map_url": map_url("Fastned Venlo")}
    assert attrs["operators"][0]["name"] == "EnBW" and attrs["sessions"] == 5 and attrs["text"] == mp["text"]


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

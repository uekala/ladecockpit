import dataclasses
from datetime import datetime, timedelta, timezone

from app import i18n
from app.analytics import build_dashboard
from app.demo import build_demo


def test_money_and_numbers():
    assert i18n.money("de", 1234.5, "EUR") == "1.234,50 €"
    assert i18n.money("en", 1234.5, "EUR") == "€1,234.50"
    assert i18n.money("en", 0.37, "USD") == "$0.37"
    assert i18n.money("en", 2, "CHF") == "2.00 CHF"
    assert i18n.num("de", 7.45, 1) == "7,5" or i18n.num("de", 7.45, 1) == "7,4"


def test_demo_dashboard_en_and_de(settings):
    for lang in ("en", "de"):
        d = build_demo(dataclasses.replace(settings, lang=lang))
        assert d["lang"] == lang
        assert d["last_charge"]["kwh"] == 18.0
        assert d["forecast"]["days_to_floor"] is not None
        assert len(d["slots"]) == 5
        # (monatsabhängige Werte werden nicht geprüft: Die Demo ist relativ zu „jetzt“)
        assert {i["kind"] for i in d["insights"]} >= {"slot", "site", "idle", "network", "speed"}
        assert d["reconcile"]["inv_sessions"] == 11
        assert set(d["totals"]["by_network"]) == {"supercharger", "multipass"}


def _session(sid, start, kwh, total):
    return {"session_id": sid, "site": "S", "start_ts": start.isoformat(timespec="seconds"),
            "stop_ts": None, "kwh": kwh, "charge_cost": total, "idle_fee": 0.0, "total": total,
            "currency": "EUR", "price": total / kwh, "invoices": [], "push_state": "pushed"}


def test_cost_per_100_only_counts_sessions_after_first_odometer_reading(settings):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    sessions = [
        _session("a", datetime(2026, 10, 3, 18, tzinfo=timezone.utc), 40, 20.0),   # before tracking
        _session("b", datetime(2026, 10, 15, 18, tzinfo=timezone.utc), 30, 12.0),  # after tracking
    ]
    readings = {
        "soc": [], "soc_last": None, "range_last": None,
        "odometer": [(datetime(2026, 10, 10, tzinfo=timezone.utc), 1000.0),
                     (datetime(2026, 10, 20, tzinfo=timezone.utc), 1200.0)],
    }
    d = build_dashboard(sessions=sessions, live={"values": {}, "units": {"odometer": "km"}},
                        readings=readings, settings=settings, meta={}, now=now)
    assert d["month"]["distance"] == 200
    assert d["month"]["per_100"] == 6.0          # 12 € / 200 km, session "a" left out
    assert d["month"]["cost"] == 32.0
    assert d["reconcile"] is None                  # no HA totals configured


def test_same_tesla_site_label_keeps_different_invoice_addresses_separate(settings):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    sessions = [
        {
            **_session("aldi-kleinewefers", now - timedelta(days=2), 20, 8.0),
            "site": "ALDI SÜD Krefeld",
            "network": "multipass",
            "station": {"street": "Kleinewefersstraße", "number": "1", "postcode": "47803",
                        "city": "Krefeld", "country": "DE"},
        },
        {
            **_session("aldi-hafen", now - timedelta(days=1), 30, 12.0),
            "site": "ALDI SÜD Krefeld",
            "network": "multipass",
            "station": {"street": "Hafenstraße", "number": "1", "postcode": "47809",
                        "city": "Krefeld", "country": "DE"},
        },
    ]
    d = build_dashboard(sessions=sessions, live={"values": {}, "units": {}},
                        readings={}, settings=settings, meta={}, now=now)

    assert len(d["sites"]) == 2
    assert {row["address"] for row in d["sites"]} == {
        "Kleinewefersstraße 1, Krefeld", "Hafenstraße 1, Krefeld"
    }
    assert all(row["sessions"] == 1 for row in d["sites"])
    assert len(d["multipass"]["stations"]) == 2
    assert {row["address"] for row in d["multipass"]["stations"]} == {
        "Kleinewefersstraße 1, Krefeld", "Hafenstraße 1, Krefeld"
    }


def test_forecast_from_readings(settings):
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    soc = [(now - timedelta(days=4 - i), 70 - 8 * i) for i in range(5)]   # 8 %/day over 4 days
    readings = {"soc": soc, "soc_last": soc[-1], "range_last": None, "odometer": []}
    d = build_dashboard(sessions=[], live={"values": {}}, readings=readings,
                        settings=dataclasses.replace(settings, soc_floor=10), meta={}, now=now)
    assert d["status"]["soc"] == 38 and d["status"]["soc_source"] == "last"
    assert d["forecast"]["rate_pct_day"] == 8.0
    assert d["forecast"]["days_to_floor"] == 3.5
    assert d["forecast"]["calendar_days"] == 4   # Oct 20 14:00 + 3.5 d = Oct 24 04:00 local


def test_the_cheapest_slot_says_when_it_rests_on_one_session(settings):
    from zoneinfo import ZoneInfo
    settings = dataclasses.replace(settings, lang="de", tz=ZoneInfo("Europe/Berlin"))
    now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)

    def session(day, hour_utc, price):
        return _session(f"s{day}-{hour_utc}", datetime(2026, 10, day, hour_utc, tzinfo=timezone.utc), 40, 40 * price)

    # 6 UTC = 8:00 in Berlin in October (one cheap morning session), 11 UTC = 13:00, 16 UTC = 18:00.
    sessions = ([session(1, 6, 0.30)] + [session(d, 11, 0.38) for d in range(2, 6)]
                + [session(d, 16, 0.41) for d in range(6, 12)])
    d = build_dashboard(sessions=sessions, live={"values": {}, "units": {}},
                        readings={"soc": [], "soc_last": None, "range_last": None, "odometer": []},
                        settings=settings, meta={}, now=now)
    slots = {s["id"]: s for s in d["slots"]}
    assert slots["morning"]["sessions"] == 1 and slots["morning"]["solid"] is False
    assert slots["midday"]["sessions"] == 4 and slots["midday"]["solid"] is True
    slot_text = next(i["text"] for i in d["insights"] if i["kind"] == "slot")
    assert slot_text.startswith("Morgens") and "erst 1× geladen" in slot_text


def _tariff_dashboard(settings, rows, lang="de", now=None, values=None, **options):
    """rows: (site, day, hour UTC, kWh, price per kWh), all in October 2026"""
    from zoneinfo import ZoneInfo
    sessions = []
    for n, (site, day, hour, kwh, price) in enumerate(rows):
        s = _session(f"t{n}", datetime(2026, 10, day, hour, tzinfo=timezone.utc), kwh, round(kwh * price, 2))
        s["site"] = site
        sessions.append(s)
    return build_dashboard(sessions=sessions, live={"values": values or {}, "units": {}},
                           readings={"soc": [], "soc_last": None, "range_last": None, "odometer": []},
                           settings=dataclasses.replace(settings, lang=lang, tz=ZoneInfo("Europe/Berlin"), **options),
                           meta={}, now=now or datetime(2026, 11, 1, 12, tzinfo=timezone.utc))


def test_tariffs_per_site(settings):
    # Moers: früh morgens und spät nachts günstig, tagsüber teuer (Zeiten in UTC, Berlin = +2 h).
    d = _tariff_dashboard(settings, [
        ("Moers, Germany", 1, 4, 30, 0.28), ("Moers, Germany", 2, 21, 20, 0.28),
        ("Moers, Germany", 3, 11, 40, 0.46), ("Moers, Germany", 4, 15, 10, 0.46),
        # Willich: nur ein Preis – kein Tarif.
        ("Willich, Germany", 5, 12, 30, 0.40), ("Willich, Germany", 6, 16, 30, 0.40),
        # Seestadt: Der Preis stieg, die günstige Ladung war tagsüber – eine Preisänderung, kein Tarif.
        ("Seestadt, Germany", 7, 10, 30, 0.42), ("Seestadt, Germany", 20, 12, 30, 0.52),
        # Bergstadt: only a few cents apart – no tariff.
        ("Bergstadt, Germany", 8, 4, 30, 0.44), ("Bergstadt, Germany", 9, 12, 30, 0.47),
    ])
    t = d["tariffs"]
    assert [s["site_name"] for s in t["sites"]] == ["Moers, Germany"]
    moers = t["sites"][0]
    assert (moers["offpeak"], moers["peak"]) == (0.28, 0.46)
    assert (moers["off_sessions"], moers["peak_sessions"]) == (2, 2)
    assert moers["off_times"] == ["06:00", "23:00"]
    assert moers["saving"] == round(50 * 0.18, 2) and t["saving"] == 9.0
    assert t["off_share"] == 0.5 and t["peak_kwh"] == 50.0
    tip = next(i["text"] for i in d["insights"] if i["kind"] == "tariff")
    assert "Moers" in tip and "0,28 €" in tip and "0,46 €" in tip and "9,00 €" in tip


def test_no_tariffs_without_both_prices(settings):
    d = _tariff_dashboard(settings, [("Moers, Germany", 1, 11, 30, 0.46), ("Moers, Germany", 2, 12, 30, 0.47)])
    assert d["tariffs"] == {"sites": []}
    assert not [i for i in d["insights"] if i["kind"] == "tariff"]


# Moers hat einen Preis in Neben- und Hauptzeit, Willich nur einen Preis (Zeiten in UTC, Berlin = +2 h).
_DAY_PRICE_ROWS = [
    ("Moers, Germany", 1, 4, 30, 0.28), ("Moers, Germany", 2, 21, 20, 0.28),
    ("Moers, Germany", 3, 11, 40, 0.46), ("Moers, Germany", 4, 15, 10, 0.46),
    ("Willich, Germany", 5, 2, 30, 0.40), ("Willich, Germany", 6, 16, 30, 0.40),
]
_OCTOBER = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)


def test_reference_price_from_the_invoices_is_the_day_price_of_the_sites(settings):
    d = _tariff_dashboard(settings, _DAY_PRICE_ROWS, now=_OCTOBER)
    c = d["compare"]
    assert c["reference_source"] == "invoices"
    # Die 50 kWh der Nebenzeit in Moers zählen zu seinem Tagespreis; alles andere zu seinem eigenen Preis –
    # auch Willich nachts, das keinen günstigeren Nachtpreis hat.
    listed = 30 * 0.28 + 20 * 0.28 + 40 * 0.46 + 10 * 0.46 + 30 * 0.40 + 30 * 0.40
    assert c["actual_cost"] == round(listed, 2)
    assert c["reference_saving"] == 9.0 and c["reference_off_kwh"] == 50.0
    assert c["reference_cost"] == round(listed + 9.0, 2)
    assert c["reference_price"] == round((listed + 9.0) / 160, 4)
    tip = next(i for i in d["insights"] if i["kind"] == "reference")
    assert tip["action"] == {"go": "month"}
    assert tip["text"].startswith("Nachts und früh zu laden hat dir diesen Monat 9,00 € gespart")
    assert "(Ø 0,44 €/kWh) wären es 70,00 € gewesen statt 61,00 €" in tip["text"] and "50 kWh" in tip["text"]


def test_reference_price_from_the_invoices_counts_only_this_month(settings):
    # Im November verraten die Oktober-Ladungen nur den Tagespreis; es gibt noch keine Ladung zum Vergleich.
    d = _tariff_dashboard(settings, _DAY_PRICE_ROWS)
    assert d["compare"]["reference_source"] is None and d["compare"]["reference_cost"] is None
    assert not [i for i in d["insights"] if i["kind"] == "reference"]


def test_no_saving_from_the_invoices_without_an_off_peak_price(settings):
    # Eine Preisänderung (später teuer, tagsüber günstig) ist keine Ersparnis, ebenso wenig ein Standort mit einem Preis.
    d = _tariff_dashboard(settings, [
        ("Seestadt, Germany", 7, 10, 30, 0.42), ("Seestadt, Germany", 20, 12, 30, 0.52),
        ("Willich, Germany", 5, 2, 30, 0.40), ("Willich, Germany", 6, 16, 30, 0.40),
    ], lang="en", now=_OCTOBER)
    c = d["compare"]
    assert c["reference_source"] == "invoices"
    assert c["reference_saving"] == 0.0 and c["reference_cost"] == c["actual_cost"]
    assert not [i for i in d["insights"] if i["kind"] == "reference"]


def test_own_reference_price_comes_first(settings):
    d = _tariff_dashboard(settings, _DAY_PRICE_ROWS, now=_OCTOBER, reference_price=0.49)
    c = d["compare"]
    assert (c["reference_source"], c["reference_price"]) == ("fixed", 0.49)
    assert c["reference_cost"] == round(160 * 0.49, 2) and "reference_saving" not in c
    tip = next(i["text"] for i in d["insights"] if i["kind"] == "reference")
    assert tip.startswith("Mit dem Referenzpreis von 0,49 €/kWh")

    d = _tariff_dashboard(settings, _DAY_PRICE_ROWS, now=_OCTOBER, values={"reference_price": 0.45},
                          ent_reference_price="input_number.supercharger_preis")
    assert (d["compare"]["reference_source"], d["compare"]["reference_price"]) == ("entity", 0.45)


def test_reference_price_zero_or_an_unavailable_entity_turns_the_comparison_off(settings):
    for options in ({"reference_price": 0.0}, {"ent_reference_price": "input_number.supercharger_preis"}):
        d = _tariff_dashboard(settings, _DAY_PRICE_ROWS, now=_OCTOBER, **options)
        assert d["compare"]["reference_cost"] is None and "reference_saving" not in d["compare"]
        assert not [i for i in d["insights"] if i["kind"] == "reference"]


# --- price changes per site -------------------------------------------------------------------
_NOVEMBER = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


def test_price_change_per_site(settings):
    # Willich: wochenlang ein Preis den ganzen Tag, dann teurer – auch abends, wo es vorher günstig war.
    d = _tariff_dashboard(settings, [
        ("Willich, Germany", 4, 12, 40, 0.37), ("Willich, Germany", 7, 17, 30, 0.3701),
        ("Willich, Germany", 15, 16, 30, 0.37), ("Willich, Germany", 22, 20, 6, 0.3704),
        ("Willich, Germany", 28, 19, 20, 0.3999),
        # Moers: night and day price – a tariff, no change.
        ("Moers, Germany", 1, 4, 30, 0.28), ("Moers, Germany", 2, 21, 20, 0.28),
        ("Moers, Germany", 3, 11, 40, 0.46), ("Moers, Germany", 4, 15, 10, 0.46),
    ], now=_NOVEMBER)
    assert [c["site_name"] for c in d["price_changes"]] == ["Willich, Germany"]
    c = d["price_changes"][0]
    assert (c["before"], c["now"], c["sessions_before"], c["sessions_now"]) == (0.37, 0.4, 4, 1)
    assert c["since"] == "2026-10-28T20:00:00+01:00"
    row = next(r for r in d["sites"] if r["site_name"] == "Willich, Germany")
    assert row["price_now"] == 0.4 and row["price_since"] == c["since"]
    assert next(r for r in d["sites"] if r["site_name"] == "Moers, Germany")["price_now"] is None
    tip = next(i for i in d["insights"] if i["kind"] == "price")
    assert tip["text"].startswith("Neuer Preis in Willich: Seit 28.10. kostet die kWh 0,40 € statt 0,37 € (+0,03 €/kWh).")
    assert tip["action"] == {"go": "radar", "site": "Willich, Germany"}


def test_latest_price_change_wins(settings):
    d = _tariff_dashboard(settings, [
        ("Krefeld, Germany", 1, 19, 30, 0.45), ("Krefeld, Germany", 3, 19, 30, 0.45),
        ("Krefeld, Germany", 10, 19, 30, 0.31), ("Krefeld, Germany", 12, 21, 30, 0.30),
        ("Krefeld, Germany", 20, 19, 30, 0.35), ("Krefeld, Germany", 25, 6, 30, 0.35),
    ], lang="en", now=_NOVEMBER)
    c = d["price_changes"][0]
    assert (c["before"], c["now"]) == (0.305, 0.35)
    tip = next(i["text"] for i in d["insights"] if i["kind"] == "price")
    assert tip.startswith("New price in Krefeld: since Oct 20 a kWh costs €0.35 instead of €0.30 (+€0.04/kWh).")


def test_no_price_change_from_a_different_time_of_day(settings):
    # Nur nachts günstig, nur nachmittags teuer: Das kann ein Tarif nach Tageszeit sein.
    d = _tariff_dashboard(settings, [
        ("Seestadt, Germany", 1, 1, 30, 0.30), ("Seestadt, Germany", 3, 2, 30, 0.30),
        ("Seestadt, Germany", 20, 15, 30, 0.45), ("Seestadt, Germany", 25, 16, 30, 0.45),
    ], now=_NOVEMBER)
    assert d["price_changes"] == []


def test_no_price_change_tip_when_too_old_or_too_few_sessions(settings):
    rows = [("Willich, Germany", 2, 12, 40, 0.37), ("Willich, Germany", 3, 13, 30, 0.37),
            ("Willich, Germany", 5, 12, 20, 0.40)]
    old = _tariff_dashboard(settings, rows, now=datetime(2027, 1, 15, 12, tzinfo=timezone.utc))
    assert len(old["price_changes"]) == 1 and not [i for i in old["insights"] if i["kind"] == "price"]
    few = _tariff_dashboard(settings, rows[1:], now=_NOVEMBER)
    assert few["price_changes"] == []

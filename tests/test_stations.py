import asyncio

import httpx

from app import stations

# Text of a real MultiPass invoice as pypdf reads it (customer made up)
INVOICE_TEXT = """Rech nu ng
Tesla Germany GmbH
Ludwig-Prandtl-Straße 27 - 29
12526 Berlin
Rechnungsnummer 4020MSP0000012345
Rechnungsdatum 2026/10/31
Kundennummer 3000000000
Verkauft an
Erika Muster
Musterweg 1
12345 Musterstadt DE
erika@example.com
Ladestation
Kleinewefersstr. 46, Krefeld
Kleinewefersstraße 46
47803 Krefeld DE
Event-Datum Beschreibung Preis/Einheit(EUR) Anzahl Steuern (%) Gesamt mtl. (EUR)
2026/10/31 Stromgebühr 0.585434 / kWh 1.2220 kWh 19 0.72
"""


def test_station_from_the_invoice():
    st = stations.station_from_text(INVOICE_TEXT)
    assert st == {"name": "Kleinewefersstr. 46, Krefeld", "street": "Kleinewefersstraße", "number": "46",
                  "postcode": "47803", "city": "Krefeld", "country": "DE"}
    assert stations.address(st) == "Kleinewefersstraße 46, Krefeld"
    assert stations.full_address(st) == "Kleinewefersstraße 46, 47803 Krefeld"
    assert stations.station_from_text("Rechnung\nSupercharger\nWillich, Germany") is None
    english = "Invoice\nCharging Station\nIONITY Marl\nBrassertstraße 124 a\n45768 Marl DE\nEvent Date Description"
    assert stations.station_from_text(english)["number"] == "124a"


def test_operator_names():
    assert stations.clean_operator("SWK ENERGIE GmbH") == "SWK ENERGIE"
    assert stations.clean_operator("EnBW mobility+ AG und Co.KG") == "EnBW"
    assert stations.clean_operator("Green Energy Hüls GmbH & Co. KG") == "Green Energy Hüls"
    assert stations.clean_operator("Stadtwerke Krefeld AG") == "Stadtwerke Krefeld"   # not just "Stadtwerke"
    assert stations.clean_operator("E.ON Drive Infrastructure GmbH") == "E.ON Drive"
    assert stations.clean_operator("") is None
    # the register wins over the site name, but a more specific brand of the same company stays
    assert stations.operator_label({"operator": "SWK ENERGIE GmbH"}, "Kleinewefersstr. 46, Krefeld") == "SWK ENERGIE"
    assert stations.operator_label({"operator": "Aral Aktiengesellschaft"}, "Aral pulse Brassertstraße 124") == "Aral pulse"
    assert stations.operator_label({"operator": "SWK ENERGIE GmbH"}, "Allego - Krefeld") == "SWK ENERGIE"
    assert stations.operator_label(None, "Green Energy Hüls - AC E5") == "Green Energy Hüls"
    assert stations.operator_label({}, "Krefeld - KiK", frozenset({"krefeld"})) is None


def test_the_registers_short_name():
    # The map name when it is the operator's short name, else the company name
    assert stations.registered_name("NEW Niederrhein Energie und Wasser GmbH", "NEW") == "NEW"
    assert stations.registered_name("ALDI SÜD Immobilienverwaltungs-GmbH & Co. oHG", "ALDI SÜD") == "ALDI SÜD"
    assert stations.registered_name("Stadtwerke Düsseldorf AG", "SWD AG") == "Stadtwerke Düsseldorf AG"
    assert stations.registered_name("Electra Germany GmbH", "") == "Electra Germany GmbH"
    assert stations.registered_name(None, None) is None
    assert stations.operator_label({"operator": "NEW Niederrhein Energie und Wasser GmbH", "operator_shown": "NEW"},
                                   "Musterstr. 46, Musterstadt") == "NEW"
    assert stations.operator_label({"operator": "Electra Germany GmbH"}, "Musterstadt - Markt") == "Electra"
    # public bodies and very long names are cut to what people call them
    assert stations.clean_operator("Sparkasse Musterstadt Anstalt des öffentlichen Rechts Zweckverbandssparkasse "
                                   "der Stadt Musterstadt und des Kreises Beispiel") == "Sparkasse Musterstadt"
    assert len(stations.clean_operator("Ein sehr langer Name einer Firma die Ladesäulen in vielen Städten betreibt GmbH")) <= stations.MAX_NAME


def test_matching_the_register():
    st = {"street": "Kleinewefersstraße", "number": "46", "postcode": "47803"}
    rows = [
        {"operator": "Andere GmbH", "street": "Kleinewefersstr.", "number": "120", "postcode": "47803"},
        {"operator": "SWK ENERGIE GmbH", "street": "Kleinewefers Straße", "number": "44-48", "postcode": "47803"},
        {"operator": "Falsch AG", "street": "Kleinewefersstraße", "number": "46", "postcode": "47800"},
    ]
    assert stations.match_operator(st, rows)["operator"] == "SWK ENERGIE GmbH"
    assert stations.match_operator({**st, "street": "Hafelsstraße"}, rows) is None
    assert stations.match_operator({**st, "number": "300"}, rows) is None          # too far along the street


REGISTER_CSV = (
    "Ladesäulenregister der Bundesnetzagentur;;;;;;;\n"
    "Stand: 01.11.2026;;;;;;;\n"
    ";;;;;;;\n"
    "Ladeeinrichtungs-ID;Betreiber;Anzeigename (Karte);Status;Straße;Hausnummer;Adresszusatz;Postleitzahl;Ort;Breitengrad;Längengrad\n"
    '1;"SWK ENERGIE GmbH";SWK;In Betrieb;Kleinewefersstraße;46;;47803;Krefeld;51,33;6,56\n'
    '2;"Muster; Partner GmbH";;In Betrieb;Hauptstraße;1;"Hof\nhinten";10115;Berlin;52,5;13,4\n'
    "3;Andere AG;;In Betrieb;Hafelsstraße;237;;47809;Krefeld;51,3;6,5\n"
)


def test_reading_the_register(tmp_path):
    path = tmp_path / "r.csv"
    path.write_bytes(REGISTER_CSV.encode("utf-8"))
    rows = stations.read_register(path, {"47803", "10115"})
    assert [r["operator"] for r in rows] == ["SWK ENERGIE GmbH", "Muster; Partner GmbH"]
    assert rows[0] == {"operator": "SWK ENERGIE GmbH", "shown": "SWK", "street": "Kleinewefersstraße", "number": "46",
                       "postcode": "47803", "city": "Krefeld"}
    path.write_bytes(REGISTER_CSV.encode("cp1252"))                                  # older files
    assert len(stations.read_register(path, {"47809"})) == 1


def test_finding_the_newest_register():
    html = ('<a href="https://data.bundesnetzagentur.de/Bundesnetzagentur/DE/X/Ladesaeulenregister_BNetzA_2026-09-01.csv">CSV</a>'
            '<a href="/Bundesnetzagentur/DE/X/Ladesaeulenregister_BNetzA_2026-10-01.csv">CSV</a>'
            '<a href="https://data.bundesnetzagentur.de/X/Ladesaeulenregister_BNetzA_2026-09-30.xlsx">XLSX</a>')
    assert stations.find_register_url([html]) == \
        "https://data.bundesnetzagentur.de/Bundesnetzagentur/DE/X/Ladesaeulenregister_BNetzA_2026-10-01.csv"
    assert stations.find_register_url(["nothing here"]) is None


def test_register_download(tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "www.bundesnetzagentur.de":
            return httpx.Response(200, text='<a href="https://data.bundesnetzagentur.de/a/Ladesaeulenregister_BNetzA_2026-10-01.csv">x</a>')
        return httpx.Response(200, content=REGISTER_CSV.encode("utf-8"))

    reg = stations.Register(tmp_path, transport=httpx.MockTransport(handler))
    rows = asyncio.run(reg.rows_for({"47803"}))
    assert [r["operator"] for r in rows] == ["SWK ENERGIE GmbH"]
    assert "data.bundesnetzagentur.de" in seen
    assert not list((tmp_path / "tmp").iterdir())                                  # the download is not kept
    assert asyncio.run(reg.rows_for({"47803"})) is None                              # not twice in a row


def test_due_for_lookup():
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 11, 2, tzinfo=timezone.utc)
    base = {"street": "Hauptstraße", "postcode": "47809", "country": "DE"}
    assert stations.due_for_lookup(base, now)
    assert not stations.due_for_lookup({**base, "country": "NL"}, now)
    assert not stations.due_for_lookup({**base, "checked": now.isoformat(), "operator": "X"}, now)
    assert not stations.due_for_lookup({**base, "checked": (now - timedelta(days=3)).isoformat()}, now)
    assert stations.due_for_lookup({**base, "checked": (now - timedelta(days=40)).isoformat()}, now)
    assert not stations.due_for_lookup({}, now) and not stations.due_for_lookup(None, now)

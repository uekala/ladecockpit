from app import networks


def test_home_country_is_the_most_common():
    sessions = [{"country": "DE"}, {"country": "de"}, {"country": "NL"}, {"country": None}]
    assert networks.home_country(sessions) == "DE"
    assert networks.home_country([{"site": "x"}]) is None


def test_place_drops_the_home_country_only():
    assert networks.place("Bergstadt, Germany", "DE", "DE") == "Bergstadt"
    assert networks.place("Seestadt - Center, Germany", "DE", "DE") == "Seestadt - Center"
    assert networks.place("Venlo, Netherlands", "NL", "DE") == "Venlo, Netherlands"
    assert networks.place("Brunnenhausstr. 46, Neustadt", "DE", "DE") == "Brunnenhausstr. 46, Neustadt"
    assert networks.place("Bergstadt, Germany", None, "DE") == "Bergstadt"
    assert networks.place("Bergstadt, Germany", "DE", None) == "Bergstadt"
    assert networks.place("", "DE", "DE") is None
    assert networks.place("Bergstadt", "DE", "DE") == "Bergstadt"


def test_operators_assigned_by_hand():
    from app import stations
    try:
        networks.configure(0.5, "Hafenstadt = Fastned ;\nparkhaus mitte=Stadtwerke; kaputt; =leer; nix=")
        assert networks.assigned_operator("Hafenstadt Oost") == "Fastned"
        assert networks.assigned_operator("x", None, "PARKHAUS  MITTE 3") == "Stadtwerke"
        assert networks.assigned_operator("Bergstadt, Germany") is None
        # Die Station zählt als MultiPass, außer die Rechnung sagt Supercharger.
        assert networks.classify({"siteLocationName": "Hafenstadt, Netherlands"})[0] == networks.MULTIPASS
        raw = {"siteLocationName": "Hafenstadt, Netherlands", "invoices": [{"fileName": "4020P0019025690_NL-NL.pdf"}]}
        assert networks.classify(raw)[0] == networks.SUPERCHARGER
        # Die Zuordnung schlägt Register und Standortnamen.
        station = {"name": "Laadplein", "street": "Havenweg", "number": "2", "city": "Hafenstadt", "operator": "Other B.V."}
        assert stations.operator_label(station, "Havenweg 2") == "Fastned"
        assert stations.operator_label(None, "IONITY Hafenstadt") == "Fastned"
    finally:
        networks.configure(0.5)
    assert networks.assigned_operator("Hafenstadt Oost") is None
    assert networks.classify({"siteLocationName": "Hafenstadt, Netherlands"})[0] == networks.SUPERCHARGER

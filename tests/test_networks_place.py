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

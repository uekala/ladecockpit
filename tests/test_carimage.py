import json
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app import carimage, demo
from app.carimage import CANVAS, CATALOG, PAINTS, TRIM_LABELS, VIEWS
from app.entities import build_states


def test_catalog_is_consistent():
    keys = [g.key for g in CATALOG]
    assert len(keys) == len(set(keys))
    for g in CATALOG:
        assert g.trims and g.views, g.key
        assert len({t.key for t in g.trims}) == len(g.trims), g.key
        assert not g.default_trim or g.default_trim in {t.key for t in g.trims}, g.key
        for t in g.trims:
            assert t.key in TRIM_LABELS, (g.key, t.key)
            assert t.wheels, (g.key, t.key)
            for wheel, fit in t.wheels.items():
                assert wheel in g.wheels and set(g.wheels[wheel]) == {"de", "en"}, (g.key, wheel)
                assert fit.paints and all(p in PAINTS for p in fit.paints), (g.key, t.key, wheel)
                assert len(set(fit.paints)) == len(fit.paints), (g.key, t.key, wheel)
                assert g.legacy or (t.code and fit.interior), (g.key, t.key, wheel)
        for view, crop in g.crop.items():
            assert view in VIEWS
            if g.legacy:
                assert crop is None  # the old image service ignores crop
                continue
            w, h, x, y = crop
            assert 0 <= x and 0 <= y and x + w <= CANVAS[0] and y + h <= CANVAS[1], (g.key, view)
            assert 1.8 < w / h < 3.2, (g.key, view)  # a car, not a sliver


def test_normalize_falls_back_and_keeps_paint():
    first = carimage.normalize(None)
    assert first == {"generation": "m3-2024", "trim": "rwd_lr", "paint": "PPSW", "wheel": "W38A", "view": "front"}
    junk = carimage.normalize({"generation": "nope", "trim": "x", "paint": "y", "wheel": "z", "view": "top"})
    assert junk == first
    # Solid Black only exists with the 19" Nova wheels on this trim: the wheels follow the paint.
    black = carimage.normalize({"generation": "m3-2024", "trim": "rwd_lr", "paint": "PBSB"})
    assert black["wheel"] == "W39S" and black["paint"] == "PBSB"
    # ...but chosen wheels win over the paint
    photon = carimage.normalize({"generation": "m3-2024", "trim": "rwd_lr", "paint": "PBSB", "wheel": "W38A"})
    assert photon["wheel"] == "W38A" and photon["paint"] == "PPSW"
    # a view the old image service does not have
    old = carimage.normalize({"generation": "ms-2012", "view": "rear"})
    assert old["view"] == "front" and old["trim"] == "any"


def test_url_configurator_and_legacy():
    choice = carimage.normalize({"generation": "m3-2024", "trim": "performance", "paint": "PR01", "wheel": "W30A"})
    u = urlparse(carimage.url(choice, 1400))
    q = parse_qs(u.query)
    assert u.netloc == "static-assets.tesla.com" and u.path == "/configurator/compositor"
    assert q["model"] == ["m3"] and q["view"] == ["STUD_3QTR"] and q["size"] == ["1440"]
    assert q["options"] == ["$MT381,$PR01,$W30A,$IPB14"] and q["bkba_opt"] == ["1"]
    assert q["crop"] == [",".join(map(str, carimage.generation("m3-2024").crop["front"]))]
    side = parse_qs(urlparse(carimage.url(choice, 720, "side")).query)
    assert side["view"] == ["STUD_SIDE"] and side["size"] == ["720"]
    old = carimage.normalize({"generation": "mx-2015", "paint": "PMNG", "wheel": "WT22"})
    lu = urlparse(carimage.url(old))
    lq = parse_qs(lu.query)
    assert lu.path == "/v1/compositor/" and lq["options"] == ["PMNG,WT22"] and "crop" not in lq


def test_from_vin():
    assert carimage.from_vin("5YJ3E7EB4MF123456").key == "m3-2017"   # Model 3, 2021
    assert carimage.from_vin("LRW3E7EB4RC123456").key == "m3-2024"   # Model 3, 2024
    assert carimage.from_vin("7SAYGDEE5SF123456").key == "my-2025"   # Model Y, 2025
    assert carimage.from_vin("5YJYGDEE1LF123456").key == "my-2020"   # Model Y, 2020
    assert carimage.from_vin("5YJSA1E26KF123456").key == "ms-2012"   # Model S, 2019
    assert carimage.from_vin("5YJXCBE20PF123456").key == "mx-2021"   # Model X, 2023
    assert carimage.from_vin("7G2CEHED1RA123456").key == "ct-2024"   # Cybertruck, 2024
    assert carimage.from_vin("5YJ3E7EB4") is None and carimage.from_vin("WVWZZZ1KZAW123456") is None
    assert carimage.normalize(None, "5YJYGDEE1LF123456")["generation"] == "my-2020"


def test_describe_and_catalog_in_both_languages():
    choice = carimage.normalize({"generation": "my-2025", "trim": "performance"})
    de = carimage.describe(choice, "de", auto=False)
    assert de["name"] == "Model Y Performance" and de["labels"]["generation"] == "Model Y (ab 2025)"
    assert set(de["views"]) == {"front", "side", "rear"} and de["url"] == de["views"]["front"]
    assert "size=720" in de["thumb"]
    en = carimage.describe(carimage.normalize({"generation": "m3-2024", "wheel": "W30P", "trim": "performance"}), "en", auto=True)
    assert en["labels"]["wheel"] == "20″ Warp, forged" and en["auto"] is True
    for lang in ("de", "en"):
        cat = carimage.catalog(lang)
        json.dumps(cat)
        assert [g["key"] for g in cat] == [g.key for g in CATALOG]
        assert all(w["paints"] for g in cat for t in g["trims"] for w in t["wheels"])


def test_storage_roundtrip(db):
    assert carimage.load_choice(db) is None
    assert carimage.current(db, None, "en")["auto"] is True
    carimage.save_choice(db, {"generation": "ct-2024", "trim": "cyberbeast", "paint": "PDD", "wheel": "WH0B", "view": "side"})
    car = carimage.current(db, None, "en")
    assert car["auto"] is False and car["name"] == "Cybertruck Cyberbeast" and "STUD_SIDE" in car["url"]
    db.kv_set(carimage.KV_KEY, "not json")
    assert carimage.load_choice(db) is None
    carimage.reset_choice(db)
    assert carimage.load_choice(db) is None


def test_entity(settings):
    d = demo.build_demo(settings)
    state, attrs = build_states(d, "en")["sensor.ladecockpit_car"]
    assert state == d["car"]["name"] and attrs["entity_picture"] == d["car"]["thumb"]
    assert attrs["image"] == d["car"]["url"] and attrs["image_side"] and attrs["friendly_name"] == "Ladecockpit Car"
    assert "sensor.ladecockpit_car" not in build_states({}, "en")


def test_api():
    from app.main import app, db

    carimage.reset_choice(db)
    with TestClient(app) as client:
        car = client.get("/api/car").json()
        assert car["auto"] is True and car["catalog"] and car["url"].startswith("https://static-assets.tesla.com/")
        preview = client.post("/api/car/preview", json={"generation": "ms-2021", "trim": "plaid", "paint": "PN02"}).json()
        assert preview["choice"]["trim"] == "plaid" and preview["choice"]["paint"] == "PPSW"  # no Lunar Silver Plaid
        assert client.get("/api/car").json()["auto"] is True                                 # preview saves nothing
        saved = client.put("/api/car", json={"generation": "my-2020", "trim": "performance", "paint": "PR01"}).json()
        assert saved["auto"] is False and saved["name"] == "Model Y Performance" and "catalog" in saved
        dash = client.get("/api/dashboard").json()
        assert dash["car"]["choice"]["generation"] == "my-2020" and "$PR01" in dash["car"]["url"]
        assert client.delete("/api/car").json()["auto"] is True

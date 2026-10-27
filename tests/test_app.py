from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parent.parent


def test_demo_endpoints():
    with TestClient(app) as client:
        assert client.get("/healthz").json()["mode"] == "demo"
        page = client.get("/")
        assert page.status_code == 200 and page.text.startswith("<!doctype html>")
        d = client.get("/api/dashboard").json()
        assert d["mode"] == "demo" and d["sessions"]
        flat = client.get("/api/ha").json()
        assert flat["month_cost"] is not None and flat["currency"] == "EUR"
        assert client.post("/api/sync").json()["demo"] is True
        assert client.get("/api/invoice/demo-1000").status_code == 404
        assert client.get("/api/invoices/2026-10.zip").status_code == 404
        assert client.get("/api/invoices/oops.zip").status_code == 400
        csv_text = client.get("/api/export.csv").text
        assert csv_text.lstrip("\ufeff").startswith("Date,Start") and csv_text.count("\n") >= 8
        assert client.get("/manifest.webmanifest").json()["short_name"] == "Ladecockpit"
        assert client.get("/icon-192.png").headers["content-type"] == "image/png"
        assert client.get("/icon-64.png").status_code == 404
        from app.main import FONTS
        for name in FONTS:
            font = client.get(f"/fonts/{name}")
            assert font.status_code == 200 and font.headers["content-type"] == "font/woff2" and font.content[:4] == b"wOF2", name
        assert client.get("/fonts/../main.py").status_code == 404
        assert client.get("/fonts/other.woff2").status_code == 404
        assert "fonts.googleapis.com" not in page.text


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor("!input", lambda loader, node: {"__input__": loader.construct_scalar(node)})


def _inputs(section):
    found = {}
    for key, value in section.items():
        if "input" in value and "selector" not in value:
            found.update(_inputs(value["input"]))
        else:
            found[key] = value
    return found


def _refs(node):
    if isinstance(node, dict):
        if "__input__" in node:
            yield node["__input__"]
        for v in node.values():
            yield from _refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _refs(v)


def test_blueprint_is_consistent():
    bp = yaml.load((ROOT / "blueprints/automation/ladecockpit/book_invoice.yaml").read_text(), Loader=_Loader)
    declared = _inputs(bp["blueprint"]["input"])
    body = {k: v for k, v in bp.items() if k != "blueprint"}
    used = set(_refs(body))
    assert used == set(declared), (used, set(declared))
    assert bp["triggers"][0]["event_type"] == "ladecockpit_invoice"


def test_look_is_saved():
    with TestClient(app) as client:
        assert client.get("/api/dashboard").json()["look"] == "classic"
        assert client.put("/api/look", json={"look": "modern"}).json() == {"look": "modern"}
        assert client.get("/api/dashboard").json()["look"] == "modern"
        assert client.put("/api/look", json={"look": "neon"}).status_code == 400
        assert client.put("/api/look", json={"look": "classic"}).status_code == 200
        assert client.get("/api/dashboard").json()["look"] == "classic"

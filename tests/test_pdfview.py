import struct
import zlib

from fastapi.testclient import TestClient
from fpdf import FPDF

from app import main, pdfview
from app.main import app


def _pdf(pages: int) -> bytes:
    pdf = FPDF()
    for i in range(pages):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, f"Tesla invoice page {i + 1}")
    return bytes(pdf.output())


def _png_size(png: bytes) -> tuple[int, int, int]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and png[12:16] == b"IHDR"
    width, height = struct.unpack(">II", png[16:24])
    return width, height, png[25]


def test_page_png_and_count():
    data = _pdf(2)
    assert pdfview.page_count(data) == 2
    png = pdfview.page_png(data, 2, width=600)
    width, height, color_type = _png_size(png)
    assert abs(width - 600) <= 1 and height > width and color_type == 2
    # One filter byte plus three bytes per pixel and row.
    idat_len = struct.unpack(">I", png[33:37])[0]
    assert png[37:41] == b"IDAT"
    assert len(zlib.decompress(png[41:41 + idat_len])) == height * (1 + width * 3)
    for bad in (0, 3):
        try:
            pdfview.page_png(data, bad)
        except IndexError:
            pass
        else:
            raise AssertionError(f"page {bad} should not exist")


def test_invoice_pages_endpoint(tmp_path, monkeypatch):
    path = tmp_path / "123.pdf"
    path.write_bytes(_pdf(2))

    async def source(session_id):
        return path, "supercharger-2026-10-01-Test-123.pdf"

    monkeypatch.setattr(main, "_invoice_source", source)
    with TestClient(app) as client:
        assert client.get("/api/invoice/123/pages").json() == {"pages": 2, "name": "supercharger-2026-10-01-Test-123.pdf"}
        r = client.get("/api/invoice/123/page/1.png")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert "max-age" in r.headers["cache-control"]
        assert (tmp_path / "123.p1.png").read_bytes() == r.content  # rendered once, then from disk
        assert client.get("/api/invoice/123/page/3.png").status_code == 404
        assert client.get("/api/invoice/123/page/x.png").status_code == 422


def test_invoice_pages_in_demo():
    with TestClient(app) as client:
        assert client.get("/api/invoice/demo-1000/pages").status_code == 404
        assert client.get("/api/invoice/demo-1000/page/1.png").status_code == 404


def test_report_pages_in_demo():
    with TestClient(app) as client:
        month = client.get("/api/dashboard").json()["month"]["key"]
        info = client.get(f"/api/report/{month}/pages").json()
        assert info["pages"] >= 1 and info["name"].endswith(f"{month}.pdf")
        r = client.get(f"/api/report/{month}/page/1.png")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert r.headers["cache-control"] == "no-store"
        assert client.get(f"/api/report/{month}/page/99.png").status_code == 404
        assert client.get("/api/report/1999-01/pages").status_code == 404
        assert client.get("/api/report/oops/pages").status_code == 400

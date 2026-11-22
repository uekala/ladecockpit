"""PDF-Seiten als PNG-Bilder, für die PDF-Ansicht in der Home-Assistant-App.

Die Companion-Apps von Home Assistant zeigen Ladecockpit in einer Web-Ansicht ohne PDF-Betrachter,
die neue Fenster ohne die Anmeldung von Home Assistant öffnet. Bilder der Seiten funktionieren
überall, weil die Web-App sie wie jedes andere Bild lädt.
"""
from __future__ import annotations

import struct
import zlib

import pypdfium2 as pdfium

# A4 in dieser Breite sind etwa 170 dpi – scharf auf Handys, klein genug zum schnellen Laden.
PAGE_WIDTH = 1400


def page_count(data: bytes) -> int:
    pdf = pdfium.PdfDocument(data)
    try:
        return len(pdf)
    finally:
        pdf.close()


def page_png(data: bytes, page: int, width: int = PAGE_WIDTH) -> bytes:
    """Seite `page` (ab 1 gezählt) als PNG, `width` Pixel breit. IndexError, wenn es die Seite nicht gibt."""
    pdf = pdfium.PdfDocument(data)
    try:
        if not 1 <= page <= len(pdf):
            raise IndexError(page)
        p = pdf[page - 1]
        try:
            bitmap = p.render(scale=width / p.get_width(), rev_byteorder=True)
            try:
                return _png(bitmap.width, bitmap.height, bitmap.n_channels, bitmap.stride, bitmap.buffer)
            finally:
                bitmap.close()
        finally:
            p.close()
    finally:
        pdf.close()


def _png(width: int, height: int, channels: int, stride: int, buffer) -> bytes:
    """Minimaler PNG-Encoder für Zeilen in 8-Bit-Grau, RGB oder RGBA (spart die Abhängigkeit von Pillow)."""
    color_type = {1: 0, 3: 2, 4: 6}[channels]
    raw = memoryview(buffer).cast("B")
    row = width * channels
    scanlines = b"".join(b"\x00" + raw[y * stride: y * stride + row].tobytes() for y in range(height))

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scanlines, 6))
            + chunk(b"IEND", b""))

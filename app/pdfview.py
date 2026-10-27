"""PDF pages as PNG images, for the PDF view inside the Home Assistant app.

The Home Assistant companion apps show Ladecockpit in a web view that has no PDF viewer and
opens new windows without the Home Assistant sign-in. Pictures of the pages work everywhere,
because the web app loads them like any other picture.
"""
from __future__ import annotations

import struct
import zlib

import pypdfium2 as pdfium

# A4 at this width is about 170 dpi – sharp on phones, small enough to load quickly.
PAGE_WIDTH = 1400


def page_count(data: bytes) -> int:
    pdf = pdfium.PdfDocument(data)
    try:
        return len(pdf)
    finally:
        pdf.close()


def page_png(data: bytes, page: int, width: int = PAGE_WIDTH) -> bytes:
    """Page `page` (counted from 1) as a PNG `width` pixels wide. IndexError if there is no such page."""
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
    """Minimal PNG encoder for 8-bit grey, RGB or RGBA rows (spares a dependency on Pillow)."""
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

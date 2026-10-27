"""Build a standalone preview page with embedded demo data.

    python -m scripts.build_preview preview.html          # English
    APP_LANG=de python -m scripts.build_preview vorschau.html
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_MODE", "demo")

from app.config import load  # noqa: E402
from app.demo import build_demo  # noqa: E402

PLACEHOLDER = '<script type="application/json" id="preview-data"></script>'


def main(out: str) -> None:
    page = (Path(__file__).resolve().parent.parent / "app" / "static" / "index.html").read_text(encoding="utf-8")
    data = json.dumps(build_demo(load()), ensure_ascii=False, default=str).replace("</", "<\\/")
    if PLACEHOLDER not in page:
        raise SystemExit("Placeholder for preview data not found in index.html.")
    page = page.replace(PLACEHOLDER, f'<script type="application/json" id="preview-data">{data}</script>')
    Path(out).write_text(page, encoding="utf-8")
    print(f"Preview written: {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "preview.html")

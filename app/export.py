"""CSV export of all sessions (Excel-friendly in both languages)."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from . import i18n
from .config import Settings


def _hours(s: dict) -> float | None:
    if not (s.get("start_ts") and s.get("stop_ts")):
        return None
    h = (datetime.fromisoformat(s["stop_ts"]) - datetime.fromisoformat(s["start_ts"])).total_seconds() / 3600
    return h if h >= 0.05 else None


def sessions_csv(sessions: list[dict], settings: Settings) -> str:
    lang, tz = settings.lang, settings.tz
    sep = ";" if lang == "de" else ","

    def dec(value, digits):
        if value is None:
            return ""
        text = f"{value:.{digits}f}"
        return text.replace(".", ",") if lang == "de" else text

    out = io.StringIO()
    writer = csv.writer(out, delimiter=sep, lineterminator="\r\n")
    writer.writerow(i18n.t(lang, "csv_header").split(sep))
    for s in sorted(sessions, key=lambda x: x.get("start_ts") or ""):
        start = datetime.fromisoformat(s["start_ts"]).astimezone(tz) if s.get("start_ts") else None
        stop = datetime.fromisoformat(s["stop_ts"]).astimezone(tz) if s.get("stop_ts") else None
        hours = _hours(s)
        writer.writerow([
            start.strftime("%d.%m.%Y" if lang == "de" else "%Y-%m-%d") if start else "",
            start.strftime("%H:%M") if start else "",
            stop.strftime("%H:%M") if stop else "",
            s.get("site") or i18n.t(lang, "unknown_site"),
            dec(s.get("kwh"), 3),
            dec(s.get("price"), 4),
            dec(s.get("charge_cost"), 2),
            dec(s.get("idle_fee"), 2),
            dec(s.get("total"), 2),
            s.get("currency") or "",
            dec(s["kwh"] / hours, 0) if s.get("kwh") and hours else "",
            s.get("session_id", ""),
        ])
    return "﻿" + out.getvalue()  # BOM so Excel detects UTF-8

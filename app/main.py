"""Ladecockpit – web app and API."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import secrets
import time
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from . import __version__, demo
from .analytics import build_dashboard
from .export import sessions_csv
from .config import settings
from .db import DB
from .homeassistant import HAClient
from .sync import SyncService
from .tesla import TeslaClient, TeslaError
from .watcher import Watcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ladecockpit")

STATIC = Path(__file__).parent / "static"

db = DB(settings.data_dir / "ladecockpit.db")
tesla = TeslaClient(settings, db)
ha = HAClient(settings)
sync = SyncService(settings, db, tesla, ha)
watcher = Watcher(settings, db, ha, sync)

_live_cache: dict = {"at": 0.0, "data": None}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks = []
    if not settings.demo:
        tasks.append(asyncio.create_task(sync.run_forever()))
        if ha.configured and ha.entities():
            tasks.append(asyncio.create_task(watcher.run_forever()))
    log.info("Ladecockpit %s started (%s, language %s)", __version__,
             "demo mode" if settings.demo else "live", settings.lang)
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(title="Ladecockpit", version=__version__, lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)


# --- optional password (HTTP Basic, user name ignored) ------------------------------
@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if settings.app_password and request.url.path != "/healthz":
        header = request.headers.get("authorization", "")
        ok = False
        if header.lower().startswith("basic "):
            try:
                _, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                ok = secrets.compare_digest(pw, settings.app_password)
            except Exception:  # noqa: BLE001
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Ladecockpit"'})
    return await call_next(request)


# --- pages ----------------------------------------------------------------------------
_SHELL = (
    '<!doctype html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    "<style>:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}</style>\n"
)


@app.get("/", include_in_schema=False)
async def index():
    # index.html holds only the page content (the same file doubles as a standalone preview),
    # so doctype and viewport are added here.
    body = (STATIC / "index.html").read_text(encoding="utf-8")
    return Response(_SHELL.format(lang=settings.lang) + body, media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-cache"})


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"ok": True, "version": __version__, "mode": "demo" if settings.demo else "live"}


# --- dashboard --------------------------------------------------------------------------
async def _live() -> dict:
    if watcher.latest is not None:
        return watcher.latest  # refreshed by the watcher every HA_POLL_SECONDS
    if time.time() - _live_cache["at"] < 30 and _live_cache["data"] is not None:
        return _live_cache["data"]
    data = await ha.live()
    _live_cache.update(at=time.time(), data=data)
    return data


async def _readings(now: datetime) -> dict:
    month_start = now.astimezone(settings.tz).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    odo_since = min(month_start - timedelta(days=160), now - timedelta(days=14))
    soc = db.readings_since("soc", now - timedelta(days=14))
    readings = {
        "soc": soc,
        "soc_last": db.last_reading("soc"),
        "range_last": db.last_reading("range"),
        "odometer": db.readings_since("odometer", odo_since),
    }
    if len(soc) < 3 and settings.ent_soc:
        # Fresh install: fall back to Home Assistant's own history for the forecast.
        readings["soc_ha"] = await ha.history(settings.ent_soc, now - timedelta(days=10))
    return readings


@app.get("/api/dashboard")
async def dashboard():
    if settings.demo:
        return demo.build_demo(settings)
    now = datetime.now(timezone.utc)
    live = await _live() if ha.configured else {"available": False, "values": {}, "units": {}}
    meta = {
        "mode": "live",
        "setup": {
            "tesla_configured": settings.tesla_configured,
            "tesla_connected": tesla.connected,
            "tesla_auth_error": tesla.auth_error,
            "ha_configured": ha.configured,
            "ha_ok": bool(live.get("available")),
            "ha_error": live.get("error"),
            "missing_entities": live.get("missing", []),
            "redirect_uri": settings.tesla_redirect_uri,
            "push_since": db.kv_get("push_since"),
            "entities": sorted(ha.entities()),
            "addon": settings.addon,
        },
        "sync": {"last": sync.last_sync, "next": sync.next_sync,
                 "error": sync.last_error, "burst": sync.bursting},
        "api_calls": db.calls_this_month(),
    }
    return build_dashboard(sessions=db.sessions(), live=live, readings=await _readings(now),
                           settings=settings, meta=meta, now=now)


@app.get("/api/ha")
async def ha_summary():
    """Flat values for a REST sensor in Home Assistant."""
    d = await dashboard()
    last = d.get("last_charge") or {}
    return {
        "next_charge_date": d["forecast"].get("date_floor"),
        "days_to_next_charge": d["forecast"].get("days_to_floor"),
        "consumption_pct_per_day": d["forecast"].get("rate_pct_day"),
        "month_cost": d["month"].get("cost"),
        "month_kwh": d["month"].get("kwh"),
        "month_price_per_kwh": d["month"].get("avg_price"),
        "month_cost_per_100": d["month"].get("per_100"),
        "last_charge_cost": last.get("cost"),
        "last_charge_price": last.get("price"),
        "last_charge_site": last.get("site"),
        "idle_fees_total": d["totals"].get("idle"),
        "currency": d.get("currency"),
        "tip": next((i["text"] for i in d["insights"] if i["kind"] == "slot"), None),
        "last_sync": d["sync"].get("last"),
    }


# --- sync -------------------------------------------------------------------------------
@app.post("/api/sync")
async def sync_after_charge():
    """Call after a charging session ended: looks for the new invoice at short intervals."""
    if settings.demo:
        return {"ok": True, "demo": True}
    sync.trigger_burst()
    return {"ok": True, "mode": "looking for invoice", "minutes": settings.burst_duration_min}


@app.post("/api/sync/now")
async def sync_now():
    if settings.demo:
        return {"ok": True, "demo": True, "new": 0}
    if not tesla.connected:
        raise HTTPException(409, "Not connected to Tesla yet.")
    try:
        new = await asyncio.wait_for(sync.sync_once(), timeout=90)
    except TeslaError as e:
        sync.last_error = str(e)
        raise HTTPException(502, str(e)) from e
    except asyncio.TimeoutError as e:
        raise HTTPException(504, "Tesla did not answer in time.") from e
    return {"ok": True, "new": new}


# --- invoices ------------------------------------------------------------------------------
async def _invoice_pdf(s: dict) -> Path:
    """Path of the cached invoice PDF of a session (fetched from Tesla on first use)."""
    cache_dir = settings.data_dir / "invoices"
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in s["session_id"] if c.isalnum() or c in "-_")
    path = cache_dir / f"{safe_id}.pdf"
    if not path.exists():
        path.write_bytes(await tesla.invoice_pdf(s["invoices"][0]["id"]))
    return path


def _pdf_name(s: dict) -> str:
    site = re.sub(r"[^A-Za-z0-9]+", "-", (s.get("site") or "supercharger")).strip("-")[:40]
    return f"supercharger-{(s.get('start_ts') or '')[:10]}-{site}-{s['session_id']}.pdf"


@app.get("/api/invoice/{session_id}")
async def invoice(session_id: str):
    if settings.demo:
        raise HTTPException(404, "The demo has no real invoices.")
    s = db.session(session_id)
    if not s or not s["invoices"]:
        raise HTTPException(404, "No invoice for this session (yet).")
    try:
        path = await _invoice_pdf(s)
    except TeslaError as e:
        raise HTTPException(502, str(e)) from e
    return FileResponse(path, media_type="application/pdf", filename=_pdf_name(s))


@app.get("/api/invoices/{month}.zip")
async def invoices_zip(month: str):
    """All invoices of one month (YYYY-MM, local time) as a ZIP file."""
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(400, "Use the format YYYY-MM.")
    if settings.demo:
        raise HTTPException(404, "The demo has no real invoices.")
    chosen = [s for s in db.sessions() if s.get("invoices") and s.get("start_ts")
              and datetime.fromisoformat(s["start_ts"]).astimezone(settings.tz).strftime("%Y-%m") == month]
    if not chosen:
        raise HTTPException(404, "No invoices in this month.")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in chosen:
            try:
                zf.write(await _invoice_pdf(s), _pdf_name(s))
            except TeslaError as e:
                raise HTTPException(502, str(e)) from e
    return Response(buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="supercharger-{month}.zip"'})


@app.get("/api/export.csv")
async def export_csv():
    sessions = demo.demo_sessions(settings, datetime.now(timezone.utc)) if settings.demo else db.sessions()
    return Response(sessions_csv(sessions, settings), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="ladecockpit-sessions.csv"'})


# --- installable web app (icon on the home screen) ----------------------------------------
@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest():
    return JSONResponse({
        "name": "Ladecockpit", "short_name": "Ladecockpit", "start_url": ".", "scope": ".",
        "display": "standalone", "background_color": "#0d1214", "theme_color": "#0d1214",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}],
    }, media_type="application/manifest+json")


@app.get("/icon-{size}.png", include_in_schema=False)
async def icon(size: int):
    if size not in (192, 512):
        raise HTTPException(404)
    return FileResponse(STATIC / f"icon-{size}.png", media_type="image/png",
                        headers={"Cache-Control": "max-age=86400"})


# --- Tesla connection -------------------------------------------------------------------------
@app.get("/auth/login", include_in_schema=False)
async def auth_login():
    if not settings.tesla_configured:
        raise HTTPException(400, "TESLA_CLIENT_ID and TESLA_CLIENT_SECRET are missing.")
    state = secrets.token_urlsafe(16)
    db.kv_set("oauth_state", state)
    return RedirectResponse(tesla.authorize_url(state))


@app.get("/auth/callback", include_in_schema=False)
async def auth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(f"/?error={error}")
    if not code or state != db.kv_get("oauth_state"):
        raise HTTPException(400, "Invalid response from Tesla (state mismatch). Please connect again.")
    await _finish_login(code)
    return RedirectResponse("/?connected=1")


class CodeIn(BaseModel):
    value: str


@app.post("/auth/code")
async def auth_code(body: CodeIn):
    """If the redirect does not land here: paste the full address or just the code."""
    value = body.value.strip()
    code = value
    if "code=" in value:
        query = urlparse(value).query or value.split("?", 1)[-1]
        code = (parse_qs(query).get("code") or [""])[0]
    if not code:
        raise HTTPException(400, "No code found.")
    await _finish_login(code)
    return {"ok": True}


async def _finish_login(code: str) -> None:
    try:
        await tesla.exchange_code(code)
    except TeslaError as e:
        raise HTTPException(400, str(e)) from e
    db.kv_del("oauth_state")
    sync.wake()


@app.post("/auth/logout")
async def auth_logout():
    tesla.disconnect()
    return {"ok": True}


# --- troubleshooting ----------------------------------------------------------------------------
@app.get("/api/debug/raw")
async def debug_raw():
    """Last raw response of the Tesla charging history (to check field names)."""
    return JSONResponse(tesla.last_raw if tesla.last_raw is not None else {"note": "No sync has run yet."})

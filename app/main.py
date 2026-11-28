"""Ladecockpit – web app and API."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import secrets
import tempfile
import time
import zipfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from starlette.background import BackgroundTask

from . import (
    __version__,
    analytics,
    backup,
    carimage,
    checks,
    demo,
    i18n,
    invoices,
    monthpdf,
    networks,
    pdfview,
    stations,
    yearpdf,
)
from .analytics import build_dashboard
from .config import settings
from .db import DB
from .entities import EntityPublisher
from .export import sessions_csv
from .homeassistant import HAClient
from .push import Ntfy
from .reports import MonthReporter
from .sync import SyncService
from .tesla import TeslaClient, TeslaError
from .watcher import Watcher

networks.configure(settings.multipass_min_price, settings.site_operators)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx schreibt jede Anfrage mit INFO ins Log – mit dem Home-Assistant-Watcher sind das etwa ein
# Dutzend Zeilen pro Minute, die echte Probleme verdecken. Fehler schreibt Ladecockpit weiter selbst.
logging.getLogger("httpx").setLevel(logging.WARNING)


class _SkipHealthCheck(logging.Filter):
    """Die Zustandsprüfung von Docker (jede Minute) aus dem Zugriffslog heraushalten."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/healthz" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_SkipHealthCheck())
log = logging.getLogger("ladecockpit")

STATIC = Path(__file__).parent / "static"

db = DB(settings.data_dir / "ladecockpit.db")
tesla = TeslaClient(settings, db)
ha = HAClient(settings)
push = Ntfy(settings)
sync = SyncService(settings, db, tesla, ha, push)
watcher = Watcher(settings, db, ha, sync)

_live_cache: dict = {"at": 0.0, "data": None}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.require_password and not settings.demo and not settings.app_password:
        raise RuntimeError(
            "APP_PASSWORD must be set for a live standalone installation. "
            "Set a strong password in .env, or explicitly set APP_REQUIRE_PASSWORD=false "
            "only when authentication is provided by a trusted reverse proxy."
        )
    tasks = []
    if not settings.demo:
        tasks.append(asyncio.create_task(sync.run_forever()))
        if ha.configured and ha.entities():
            tasks.append(asyncio.create_task(watcher.run_forever()))
        if ha.configured and settings.publish_entities:
            tasks.append(asyncio.create_task(EntityPublisher(settings, ha, dashboard).run_forever()))
        if ha.configured or push.configured:
            tasks.append(asyncio.create_task(MonthReporter(settings, db, ha, dashboard, push).run_forever()))
    log.info("Ladecockpit %s started (%s, language %s)", __version__,
             "demo mode" if settings.demo else "live", settings.lang)
    yield
    for task in tasks:
        task.cancel()
    # Sie ihr Aufräumen beenden lassen, bevor der Prozess endet.
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Ladecockpit", version=__version__, lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)


# --- access control: trusted Home Assistant Ingress or direct app password ----------
SUPERVISOR_INGRESS_IP = "172.30.32.2"


def _is_trusted_ingress(request: Request) -> bool:
    """Ingress nur vertrauen, wenn die TCP-Gegenstelle der Supervisor ist und seine Kennung vorliegt.

    Der Header allein reicht nicht: Direkte Clients können HTTP-Header fälschen.
    Home Assistant dokumentiert 172.30.32.2 als einzige Quelle, die eine
    Ingress-App erreichen darf. Für diese Entscheidung nie X-Forwarded-For nutzen.
    """
    peer = request.client.host if request.client else ""
    return (
        peer == SUPERVISOR_INGRESS_IP
        and request.headers.get("x-hass-source") == "core.ingress"
        and request.headers.get("x-ingress-path", "").startswith("/api/hassio_ingress/")
    )


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    # Keep the local container health check available.
    if request.url.path == "/healthz" and request.client and request.client.host in {
        "127.0.0.1", "::1", SUPERVISOR_INGRESS_IP
    }:
        return await call_next(request)

    # Ingress von Home Assistant hat den Nutzer schon angemeldet. Nur Anfragen
    # vertrauen, die wirklich von der festen Netzwerk-IP des Supervisors kommen.
    if _is_trusted_ingress(request):
        return await call_next(request)

    # Jede Anfrage ohne Ingress ist direkter Zugriff und braucht ein eigenes Passwort.
    if settings.addon and not settings.app_password:
        return Response(
            status_code=403,
            content="Direct access is disabled until an app password is configured.",
        )

    if settings.app_password:
        header = request.headers.get("authorization", "")
        ok = False
        if header.lower().startswith("basic "):
            try:
                _, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                ok = secrets.compare_digest(pw, settings.app_password)
            except Exception:
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
    # index.html enthält nur den Seiteninhalt (dieselbe Datei dient auch als eigenständige Vorschau),
    # deshalb werden Doctype und Viewport hier ergänzt.
    body = (STATIC / "index.html").read_text(encoding="utf-8")
    return Response(_SHELL.format(lang=settings.lang) + body, media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-cache"})


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"ok": True, "version": __version__, "mode": "demo" if settings.demo else "live"}


# --- dashboard --------------------------------------------------------------------------
async def _live() -> dict:
    if watcher.latest is not None:
        return watcher.latest  # vom Watcher alle HA_POLL_SECONDS aufgefrischt
    if time.time() - _live_cache["at"] < 30 and _live_cache["data"] is not None:
        return _live_cache["data"]
    data = await ha.live()
    _live_cache.update(at=time.time(), data=data)
    return data


def _home(since: datetime) -> list[tuple[datetime, float, float | None]]:
    """Schritte beim Laden zu Hause: (Zeit, kWh, Kosten oder None ohne Preis)."""
    costs = dict(db.readings_since("home_cost", since))
    return [(ts, kwh, costs.get(ts)) for ts, kwh in db.readings_since("home_kwh", since)]


async def _readings(now: datetime) -> dict:
    month_start = now.astimezone(settings.tz).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    odo_since = min(month_start - timedelta(days=160), now - timedelta(days=14))
    soc = db.readings_since("soc", now - timedelta(days=14))
    readings = {
        "soc": soc,
        "soc_last": db.last_reading("soc"),
        "range_last": db.last_reading("range"),
        "odometer": db.readings_since("odometer", min(odo_since, now - timedelta(days=365))),
        "soc_long": db.readings_since("soc", now - timedelta(days=365)),
        "range_long": db.readings_since("range", now - timedelta(days=365)),
        "temp": db.readings_since("temp", now - timedelta(days=365)),
        "home": _home(min(odo_since, now - timedelta(days=365))),
        "fuel_cost": db.readings_since("fuel_cost", now - timedelta(days=120)),
        "fuel_litres": db.readings_since("fuel_litres", now - timedelta(days=120)),
        "fuel_price": db.readings_since("fuel_price", min(odo_since, now - timedelta(days=200))),
    }
    if len(soc) < 3 and settings.ent_soc:
        # Neuinstallation: für die Prognose auf den eigenen Verlauf von Home Assistant zurückgreifen.
        readings["soc_ha"] = await ha.history(settings.ent_soc, now - timedelta(days=10))
    return readings


def _vin(sessions: list[dict] | None = None) -> str | None:
    """Die VIN des Autos: aus den Einstellungen, sonst aus der neuesten Ladung der Ladehistorie."""
    if settings.tesla_vin:
        return settings.tesla_vin
    return next((s["vin"] for s in (db.sessions() if sessions is None else sessions) if s.get("vin")), None)


def _car(sessions: list[dict] | None = None) -> dict:
    return carimage.current(db, None if settings.demo else _vin(sessions), settings.lang)


def _when(iso: str | None) -> str:
    """Eine Abgleichzeit für die Einrichtungsschritte in Ortszeit: "21.11. 08:14" / "Nov 21, 08:14"."""
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(iso).astimezone(settings.tz)
    except ValueError:
        return ""
    return f"{t:%d.%m. %H:%M}" if settings.lang == "de" else f"{t:%b} {t.day}, {t:%H:%M}"


@app.get("/api/dashboard")
async def dashboard():
    if settings.demo:
        years = yearpdf.years(demo.demo_sessions(settings, datetime.now(UTC)), settings.tz)
        return {**demo.build_demo(settings), "car": _car(), "look": _look(), "years": years}
    now = datetime.now(UTC)
    live = await _live() if ha.configured else {"available": False, "values": {}, "units": {}}
    meta = {
        "mode": "live",
        "setup": {
            "tesla_configured": settings.tesla_configured,
            "tesla_open_source": settings.tesla_open_source,
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
            "push": {"configured": push.configured, "host": push.topic_host, "error": push.last_error},
            "checks": None,
        },
        "sync": {"last": sync.last_sync, "next": sync.next_sync,
                 "error": sync.last_error, "burst": sync.bursting,
                 "problem": db.kv_get("problem_kind")},
        "api_calls": db.calls_this_month(),
    }
    sessions = db.sessions()
    car_last = db.last_reading("soc") or db.last_reading("odometer") or db.last_reading("range")
    meta["setup"]["checks"] = checks.report(settings, ha.entities(), live, {
        "tesla_connected": tesla.connected, "tesla_auth_error": tesla.auth_error,
        "last_sync": sync.last_sync, "sync_error": sync.last_error, "sessions": len(sessions),
        "ha_ok": bool(live.get("available")), "ha_error": live.get("error"),
        "when": _when(sync.last_sync), "car_when": _when(car_last[0].isoformat()) if car_last else None},
        hidden=_hidden_hints())
    d = build_dashboard(sessions=sessions, live=live, readings=await _readings(now),
                        settings=settings, meta=meta, now=now)
    d["car"] = _car(sessions)
    d["look"] = _look()
    d["years"] = yearpdf.years(sessions, settings.tz)
    return d


# --- Design der Web-App -----------------------------------------------------------------------------
LOOKS = ("classic", "dynamic")  # das erste ist der Standard
OLD_LOOKS = {"modern": "dynamic"}  # 0.9–0.10 had "modern" where "dynamic" is now


def _look() -> str:
    """Das Design der Web-App, in der Web-App gewählt und für jedes Gerät gespeichert."""
    look = db.kv_get("ui_look")
    look = OLD_LOOKS.get(look, look)
    return look if look in LOOKS else LOOKS[0]


class LookIn(BaseModel):
    look: str


@app.put("/api/look")
async def look_save(body: LookIn):
    look = OLD_LOOKS.get(body.look, body.look)
    if look not in LOOKS:
        raise HTTPException(400, f"Use one of: {', '.join(LOOKS)}.")
    db.kv_set("ui_look", look)
    return {"look": look}


# --- ausgeblendete Tipps der Einrichtungsprüfung ---------------------------------------------------
_HIDDEN_HINTS_KEY = "hints_hidden"


def _hidden_hints() -> set[str]:
    try:
        saved = json.loads(db.kv_get(_HIDDEN_HINTS_KEY) or "[]")
    except ValueError:
        saved = []
    return {str(x) for x in saved} if isinstance(saved, list) else set()


class HintIn(BaseModel):
    id: str
    hidden: bool = True


@app.put("/api/hint")
async def hint_save(body: HintIn):
    """Einen Tipp der Einrichtungsprüfung ausblenden (oder wieder zeigen). Nur Tipps lassen sich ausblenden:
    Eine halb eingerichtete Funktion bleibt in der Liste, bis sie behoben ist."""
    if settings.demo:
        raise HTTPException(404, "The demo keeps its tips.")
    if body.id not in checks.HINT_IDS:
        raise HTTPException(400, "Unknown tip.")
    hidden = _hidden_hints()
    if body.hidden:
        hidden.add(body.id)
    else:
        hidden.discard(body.id)
    db.kv_set(_HIDDEN_HINTS_KEY, json.dumps(sorted(hidden)))
    return {"hidden": sorted(hidden)}


@app.delete("/api/hints/hidden")
async def hints_show_all():
    """Show every hidden tip again."""
    if settings.demo:
        raise HTTPException(404, "The demo keeps its tips.")
    db.kv_set(_HIDDEN_HINTS_KEY, "[]")
    return {"hidden": []}


# --- operators assigned by hand ------------------------------------------------------------------
_ASSIGNED_KEY = "site_operators"


def _load_assigned_sites() -> dict[str, str]:
    try:
        saved = json.loads(db.kv_get(_ASSIGNED_KEY) or "{}")
    except ValueError:
        saved = {}
    return {str(k): str(v) for k, v in saved.items()} if isinstance(saved, dict) else {}


if not settings.demo:
    networks.set_assigned_sites(_load_assigned_sites())


class OperatorIn(BaseModel):
    site: str
    operator: str | None = None


@app.get("/api/operators")
async def operators_get():
    """Einzelnen Standorten zugeordnete Betreiber und die Namen, die zur Auswahl angeboten werden."""
    return {"assigned": {} if settings.demo else _load_assigned_sites(), "known": networks.known_operators()}


@app.put("/api/operator")
async def operator_save(body: OperatorIn):
    """Einem Standort einen Betreiber zuordnen (alle seine Ladungen, frühere und künftige); ein leerer Betreiber entfernt ihn."""
    if settings.demo:
        raise HTTPException(404, "The demo has no stations of your own to assign.")
    site = " ".join(body.site.split())
    name = " ".join((body.operator or "").split())
    if not site or len(site) > 200 or len(name) > 60:
        raise HTTPException(400, "Name the site and an operator of at most 60 characters.")
    assigned = {k: v for k, v in _load_assigned_sites().items() if k.casefold() != site.casefold()}
    if name:
        assigned[site] = name
    db.kv_set(_ASSIGNED_KEY, json.dumps(assigned, ensure_ascii=False))
    networks.set_assigned_sites(assigned)
    _report_cache.clear()
    return {"site": site, "operator": name or None, "assigned": assigned}


# --- Bild des Autos -------------------------------------------------------------------------------
class CarIn(BaseModel):
    generation: str | None = None
    trim: str | None = None
    paint: str | None = None
    wheel: str | None = None
    view: str | None = None


def _car_response(car: dict) -> dict:
    return {**car, "catalog": carimage.catalog(settings.lang)}


@app.get("/api/car")
async def car_get():
    """Das aktuelle Bild und alles, was sich wählen lässt."""
    return _car_response(_car())


@app.post("/api/car/preview")
async def car_preview(body: CarIn):
    """What a choice would look like – nothing is saved."""
    vin = None if settings.demo else _vin()
    return carimage.describe(carimage.normalize(body.model_dump(), vin), settings.lang, auto=False)


@app.put("/api/car")
async def car_save(body: CarIn):
    vin = None if settings.demo else _vin()
    carimage.save_choice(db, carimage.normalize(body.model_dump(), vin))
    return _car_response(_car())


@app.delete("/api/car")
async def car_reset():
    """Zurück zum Auto, das an der VIN erkannt wurde."""
    carimage.reset_choice(db)
    return _car_response(_car())


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
    """Nach dem Ende einer Ladung aufrufen: sucht in kurzen Abständen nach der neuen Rechnung."""
    if settings.demo:
        return {"ok": True, "demo": True}
    sync.trigger_burst()
    return {"ok": True, "mode": "looking for invoice", "minutes": settings.burst_duration_min}


@app.post("/api/push/test")
async def push_test():
    """Eine Testnachricht über ntfy senden, damit sich die Einrichtung in der Web-App prüfen lässt."""
    if not push.configured:
        raise HTTPException(400, "NTFY_URL is not set")
    ok = await push.send(i18n.t(settings.lang, "push_test_title"), i18n.t(settings.lang, "push_test"), tags=["bell"])
    if not ok:
        raise HTTPException(502, push.last_error or "ntfy did not accept the message")
    return {"ok": True}


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
    except TimeoutError as e:
        raise HTTPException(504, "Tesla did not answer in time.") from e
    return {"ok": True, "new": new}


# --- invoices ------------------------------------------------------------------------------
async def _invoice_pdf(s: dict) -> Path:
    """Pfad des zwischengespeicherten Rechnungs-PDFs einer Ladung (beim ersten Bedarf von Tesla geholt).
    Eine noch nicht geprüfte Ladung bekommt ihr Netz sofort aus der Rechnung."""
    path = await invoices.pdf_path(tesla, settings.data_dir, s)
    if s.get("invoice_network") is None:
        db.set_invoice_network(s["session_id"], invoices.network_from_pdf(path.read_bytes()))
    return path


def _pdf_name(s: dict) -> str:
    kind = "multipass" if s.get("network") == networks.MULTIPASS else "supercharger"
    site = re.sub(r"[^A-Za-z0-9]+", "-", (s.get("site") or kind)).strip("-")[:40]
    return f"{kind}-{(s.get('start_ts') or '')[:10]}-{site}-{s['session_id']}.pdf"


async def _invoice_source(session_id: str) -> tuple[Path, str]:
    """Zwischengespeichertes Rechnungs-PDF einer Ladung und sein Download-Name; HTTP-Fehler, wenn es keines gibt."""
    if settings.demo:
        raise HTTPException(404, "The demo has no real invoices.")
    s = db.session(session_id)
    if not s or not s["invoices"]:
        raise HTTPException(404, "No invoice for this session (yet).")
    try:
        return await _invoice_pdf(s), _pdf_name(s)
    except TeslaError as e:
        raise HTTPException(502, str(e)) from e


@app.get("/api/invoice/{session_id}")
async def invoice(session_id: str):
    path, name = await _invoice_source(session_id)
    return FileResponse(path, media_type="application/pdf", filename=name)


# --- PDF-Ansicht: Seiten als Bilder (die Home-Assistant-App hat keinen PDF-Betrachter) -----------
def _page_response(data: bytes, page: int, cache_path: Path | None = None) -> Response:
    if cache_path is not None and cache_path.exists():
        png = cache_path.read_bytes()
    else:
        try:
            png = pdfview.page_png(data, page)
        except IndexError as e:
            raise HTTPException(404, "No such page.") from e
        if cache_path is not None:
            cache_path.write_bytes(png)
    # Rechnungen ändern sich nie, der Monatsbericht schon; nur Rechnungsseiten dürfen zwischengespeichert werden.
    cache = "private, max-age=86400" if cache_path is not None else "no-store"
    return Response(png, media_type="image/png", headers={"Cache-Control": cache})


@app.get("/api/invoice/{session_id}/pages")
async def invoice_pages(session_id: str):
    path, name = await _invoice_source(session_id)
    return {"pages": pdfview.page_count(path.read_bytes()), "name": name}


@app.get("/api/invoice/{session_id}/page/{page}.png")
async def invoice_page(session_id: str, page: int):
    path, _ = await _invoice_source(session_id)
    return _page_response(path.read_bytes(), page, path.with_name(f"{path.stem}.p{page}.png"))


@app.get("/api/invoices/{month}.zip")
async def invoices_zip(month: str):
    """Alle Rechnungen eines Monats (JJJJ-MM, Ortszeit) als ZIP-Datei."""
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


@app.get("/api/report/{month}.pdf")
async def month_report_pdf(month: str):
    """Deckblatt mit allen Ladungen eines Monats (netto, MwSt., brutto, Gutschriften) plus Teslas Rechnungen."""
    data, name = await _month_report(month)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


# Die PDF-Ansicht fragt nach der Seitenzahl und dann nach jeder Seite; den Bericht für diese kurze
# Zeit behalten, statt ihn je Seite neu zu bauen.
_report_cache: dict[str, tuple[float, bytes, str]] = {}
_REPORT_TTL = 300


async def _month_report_cached(month: str) -> tuple[bytes, str]:
    now = time.monotonic()
    for key in [k for k, v in _report_cache.items() if now - v[0] > _REPORT_TTL]:
        del _report_cache[key]
    if month not in _report_cache:
        data, name = await _month_report(month)
        _report_cache[month] = (now, data, name)
    _, data, name = _report_cache[month]
    return data, name


@app.get("/api/report/{month}/pages")
async def month_report_pages(month: str):
    _report_cache.pop(month, None)  # das Öffnen der Ansicht zeigt immer die aktuellen Zahlen
    data, name = await _month_report_cached(month)
    return {"pages": pdfview.page_count(data), "name": name}


@app.get("/api/report/{month}/page/{page}.png")
async def month_report_page(month: str, page: int):
    data, _ = await _month_report_cached(month)
    return _page_response(data, page)


async def _month_report(month: str) -> tuple[bytes, str]:
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(400, "Use the format YYYY-MM.")
    now = datetime.now(UTC)
    sessions = demo.demo_sessions(settings, now) if settings.demo else db.sessions()
    chosen = sorted((s for s in sessions if s.get("start_ts") and s.get("total") is not None
                     and datetime.fromisoformat(s["start_ts"]).astimezone(settings.tz).strftime("%Y-%m") == month),
                    key=lambda s: s["start_ts"])
    stations.describe(sessions)  # benennt auch in `chosen` die Betreiber der MultiPass-Stationen
    d = await dashboard()
    entry = next((m for m in d.get("monthly") or [] if m["key"] == month), {})
    if not chosen and not entry.get("home_kwh"):
        raise HTTPException(404, "No sessions in this month.")
    home = {"kwh": entry.get("home_kwh"), "cost": entry.get("home_cost")} if entry.get("home_kwh") else None
    cover = monthpdf.cover(month, chosen, lang=settings.lang, tz=settings.tz, currency=d.get("currency") or "EUR",
                           home=home, distance=entry.get("distance"), unit=d.get("distance_unit") or "km", now=now)
    pdfs = []
    if not settings.demo:
        for s in chosen:
            if s.get("invoices"):
                try:
                    pdfs.append((await _invoice_pdf(s)).read_bytes())
                except TeslaError as e:
                    raise HTTPException(502, str(e)) from e
    name = f"ladekosten-{month}.pdf" if settings.lang == "de" else f"charging-{month}.pdf"
    return monthpdf.merge(cover, pdfs), name


# --- Jahresübersicht: eine Seite mit einer Zeile je Monat ------------------------------------------
def _year_report(year: int) -> tuple[bytes, str]:
    if not 2000 <= year <= 2100:
        raise HTTPException(400, "Use a four-digit year.")
    now = datetime.now(UTC)
    sessions = demo.demo_sessions(settings, now) if settings.demo else db.sessions()
    if not any(yearpdf.in_year(s, year, settings.tz) for s in sessions):
        raise HTTPException(404, "No sessions in this year.")
    start = datetime(year, 1, 1, tzinfo=settings.tz)
    end = datetime(year + 1, 1, 1, tzinfo=settings.tz)
    home = None if settings.demo else analytics._home_sum(_home(start), start, end)
    currency = next((s["currency"] for s in sessions if s.get("currency")), "EUR")
    data = yearpdf.cover(year, sessions, lang=settings.lang, tz=settings.tz, currency=currency,
                         home=home if home and home.get("kwh") else None, now=now)
    return data, (f"ladekosten-{year}.pdf" if settings.lang == "de" else f"charging-{year}.pdf")


@app.get("/api/year/{year}.pdf")
async def year_report_pdf(year: int):
    """Ladekosten eines Jahres: Ladungen, kWh, netto, MwSt., brutto und Gutschriften je Monat."""
    data, name = _year_report(year)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/year/{year}/pages")
async def year_report_pages(year: int):
    data, name = _year_report(year)
    return {"pages": pdfview.page_count(data), "name": name}


@app.get("/api/year/{year}/page/{page}.png")
async def year_report_page(year: int, page: int):
    data, _ = _year_report(year)
    return _page_response(data, page)


# --- backup and restore -------------------------------------------------------------------------
@app.get("/api/backup.zip")
async def backup_download():
    """Ladehistorie, Messwerte und zwischengespeicherte Rechnungen in einer Datei – ohne die Tesla-Anmeldung."""
    if settings.demo:
        raise HTTPException(404, "The demo has nothing to back up.")
    handle, path = tempfile.mkstemp(prefix="ladecockpit-backup-", suffix=".zip")
    target = Path(path)
    try:
        os.close(handle)
        await asyncio.to_thread(backup.create, db, settings.data_dir, __version__, target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    name = f"ladecockpit-backup-{datetime.now(settings.tz):%Y-%m-%d}.zip"
    return FileResponse(target, media_type="application/zip", filename=name,
                        headers={"Cache-Control": "no-store"},
                        background=BackgroundTask(target.unlink, missing_ok=True))


@app.post("/api/restore")
async def backup_restore(request: Request):
    """Die Ladehistorie durch eine Sicherung ersetzen. Der Inhalt der Anfrage ist die ZIP-Datei selbst."""
    if settings.demo:
        raise HTTPException(400, "The demo cannot restore a backup.")
    # Ein einfaches seitenübergreifendes Formular kann diesen Content-Type nicht senden, eine andere Website also nicht hierher posten.
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/zip":
        raise HTTPException(415, "Send the backup as application/zip.")
    handle, path = tempfile.mkstemp(prefix="ladecockpit-restore-", suffix=".zip")
    source = Path(path)
    try:
        size = 0
        with open(handle, "wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > backup.MAX_UPLOAD:
                    raise HTTPException(413, "The backup is too large.")
                out.write(chunk)
        try:
            result = await asyncio.to_thread(backup.restore, db, settings.data_dir, source)
        except backup.BackupError as e:
            raise HTTPException(400, str(e)) from e
    finally:
        source.unlink(missing_ok=True)
    sync.last_sync = db.kv_get("last_sync")
    networks.set_assigned_sites(_load_assigned_sites())
    _report_cache.clear()
    log.info("Backup restored: %s sessions, %s invoices", result["sessions"], result["invoices"])
    return {"ok": True, **result}


@app.get("/api/export.csv")
async def export_csv():
    sessions = demo.demo_sessions(settings, datetime.now(UTC)) if settings.demo else db.sessions()
    return Response(sessions_csv(sessions, settings), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="ladecockpit-sessions.csv"'})


# --- installierbare Web-App (Symbol auf dem Startbildschirm) ----------------------------------
@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest():
    return JSONResponse({
        "name": "Ladecockpit", "short_name": "Ladecockpit", "start_url": ".", "scope": ".",
        "display": "standalone", "background_color": "#000000", "theme_color": "#000000",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}],
    }, media_type="application/manifest+json")


FONTS = ("geist-latin.woff2", "geist-latin-ext.woff2",   # both looks
         "saira-latin.woff2", "saira-latin-ext.woff2")    # Ziffern des dynamischen Designs


@app.get("/fonts/{name}", include_in_schema=False)
async def font(name: str):
    """Die Schriften der Web-App (Geist, Saira – SIL Open Font License, siehe
    static/fonts/OFL-*.txt), hier ausgeliefert, damit die Seite keinen fremden Schriftdienst braucht.
    Ein Browser lädt nur die Dateien des genutzten Designs."""
    if name not in FONTS:
        raise HTTPException(404)
    return FileResponse(STATIC / "fonts" / name, media_type="font/woff2",
                        headers={"Cache-Control": "max-age=604800"})


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
        raise HTTPException(400, "TESLA_CLIENT_ID is missing.")
    state = secrets.token_urlsafe(16)
    db.kv_set("oauth_state", state)
    verifier = None
    if settings.tesla_open_source:
        # Kein Client-Secret: Die Anmeldung ist stattdessen an diesen Verifier gebunden (PKCE).
        verifier = secrets.token_urlsafe(64)
        db.kv_set("oauth_verifier", verifier)
    else:
        db.kv_del("oauth_verifier")
    return RedirectResponse(tesla.authorize_url(state, verifier))


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
    """Landet die Weiterleitung nicht hier: die ganze Adresse oder nur den Code einfügen."""
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
    verifier = db.kv_get("oauth_verifier") if settings.tesla_open_source else None
    if settings.tesla_open_source and not verifier:
        raise HTTPException(400, "This sign-in was not started here. Please connect to Tesla again.")
    try:
        await tesla.exchange_code(code, verifier)
    except TeslaError as e:
        raise HTTPException(400, str(e)) from e
    db.kv_del("oauth_state", "oauth_verifier")
    sync.wake()


@app.post("/auth/logout")
async def auth_logout():
    tesla.disconnect()
    return {"ok": True}


# --- troubleshooting ----------------------------------------------------------------------------
@app.get("/api/debug/raw")
async def debug_raw():
    """Letzte Rohantwort der Tesla-Ladehistorie (zum Prüfen der Feldnamen)."""
    return JSONResponse(tesla.last_raw if tesla.last_raw is not None else {"note": "No sync has run yet."})

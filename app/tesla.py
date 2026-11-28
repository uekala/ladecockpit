"""Tesla Fleet API – nur Anmeldung, Ladehistorie und Rechnungs-PDF.

Ladecockpit liest nur. Hier gibt es absichtlich keinen Code, der Befehle
ans Fahrzeug sendet oder das Auto weckt.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlencode

import httpx

from .config import AUTH_AUTHORIZE_URL, SCOPES, Settings
from .db import DB, utcnow_iso
from .pricing import fee_total

log = logging.getLogger("ladecockpit.tesla")

HISTORY_PATH = "/api/1/dx/charging/history"
INVOICE_PATH = "/api/1/dx/charging/invoice/{id}"
PAGE_SIZE = 50
MAX_PAGES = 20
# Abgelehnte Token-Erneuerungen in Folge, bevor Ladecockpit um eine neue Anmeldung bei Tesla bittet
REFRESH_FAILURES_FOR_SIGN_IN = 2
# Nach HTTP 429 ohne brauchbares Retry-After so lange warten; nie länger als einen Tag
RATE_LIMIT_DEFAULT_S = 300
RATE_LIMIT_MAX_S = 86400


class TeslaError(Exception):
    pass


class NotConnected(TeslaError):
    pass


class BudgetExceeded(TeslaError):
    pass


class RateLimited(TeslaError):
    pass


class Rejected(TeslaError):
    """Tesla hat eine Datenanfrage selbst abgelehnt (HTTP 4xx). Auch die Ablehnung zählt als bezahlte Anfrage."""


def retry_after_seconds(value: str | None, now: float | None = None) -> float:
    """Sekunden Wartezeit aus einem Retry-After-Header (Sekunden oder ein HTTP-Datum)."""
    now = time.time() if now is None else now
    wait: float | None = None
    if value:
        value = value.strip()
        try:
            wait = float(value)
        except ValueError:
            try:
                wait = parsedate_to_datetime(value).timestamp() - now
            except (TypeError, ValueError):
                wait = None
    if wait is None or wait != wait:  # fehlt, unlesbar oder NaN
        wait = RATE_LIMIT_DEFAULT_S
    return min(max(wait, 0.0), RATE_LIMIT_MAX_S)


def pkce_challenge(verifier: str) -> str:
    """Die S256-Code-Challenge zu einem PKCE-Code-Verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class TeslaClient:
    def __init__(self, settings: Settings, db: DB, transport: httpx.AsyncBaseTransport | None = None):
        self.s = settings
        self.db = db
        self._http = httpx.AsyncClient(timeout=30, transport=transport)
        self._lock = asyncio.Lock()
        self.last_raw: object | None = None

    # --- status --------------------------------------------------------------
    @property
    def connected(self) -> bool:
        return bool(self.db.kv_get("tesla_refresh_token"))

    @property
    def auth_error(self) -> str | None:
        return self.db.kv_get("tesla_auth_error")

    def calls_used(self) -> int:
        return sum(self.db.calls_this_month().values())

    # --- OAuth -----------------------------------------------------------------
    def authorize_url(self, state: str, code_verifier: str | None = None) -> str:
        """Wo sich der Nutzer anmeldet. Mit einem Code-Verifier ist die Anfrage per PKCE geschützt; so
        beweist eine App ohne Client-Secret, dass sie die Anmeldung begonnen hat."""
        params = {
            "response_type": "code",
            "client_id": self.s.tesla_client_id,
            "redirect_uri": self.s.tesla_redirect_uri,
            "scope": SCOPES,
            "state": state,
            "locale": self.s.locale,
            "prompt": "login",
        }
        if code_verifier:
            params["code_challenge"] = pkce_challenge(code_verifier)
            params["code_challenge_method"] = "S256"
        return f"{AUTH_AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"

    async def exchange_code(self, code: str, code_verifier: str | None = None) -> None:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.s.tesla_client_id,
            "code": code,
            "audience": self.s.fleet_base,
            "redirect_uri": self.s.tesla_redirect_uri,
        }
        # Entwickler-Apps weisen sich mit ihrem Secret aus, Open-Source-Apps mit dem Verifier.
        if self.s.tesla_client_secret:
            data["client_secret"] = self.s.tesla_client_secret
        if code_verifier:
            data["code_verifier"] = code_verifier
        r = await self._http.post(self.s.token_url, data=data)
        if r.status_code != 200:
            raise TeslaError(f"Tesla sign-in failed (HTTP {r.status_code}): {r.text[:300]}")
        self._store_tokens(r.json())
        if not self.db.kv_get("tesla_connected_at"):
            self.db.kv_set("tesla_connected_at", utcnow_iso())

    def _store_tokens(self, tok: dict) -> None:
        if "access_token" not in tok:
            raise TeslaError("Tesla did not return an access token.")
        self.db.kv_set("tesla_access_token", tok["access_token"])
        # Tesla-Refresh-Tokens gelten nur einmal – immer den neuesten behalten.
        if tok.get("refresh_token"):
            self.db.kv_set("tesla_refresh_token", tok["refresh_token"])
        expires = time.time() + int(tok.get("expires_in", 28800)) - 120
        self.db.kv_set("tesla_access_expires", str(expires))
        self.db.kv_del("tesla_auth_error", "tesla_refresh_failures")

    def disconnect(self) -> None:
        self.db.kv_del("tesla_access_token", "tesla_refresh_token",
                       "tesla_access_expires", "tesla_auth_error")

    async def _access_token(self, force_refresh: bool = False) -> str:
        async with self._lock:
            token = self.db.kv_get("tesla_access_token")
            expires = float(self.db.kv_get("tesla_access_expires", "0") or 0)
            if token and not force_refresh and time.time() < expires:
                return token
            refresh = self.db.kv_get("tesla_refresh_token")
            if not refresh:
                raise NotConnected("Not connected to Tesla.")
            r = await self._http.post(self.s.token_url, data={
                "grant_type": "refresh_token",
                "client_id": self.s.tesla_client_id,
                "refresh_token": refresh,
            })
            if r.status_code != 200:
                msg = f"Token refresh failed (HTTP {r.status_code}). Please connect to Tesla again."
                # Eine abgelehnte Erneuerung kann ein Aussetzer bei Tesla sein (nachts gesehen, danach normale
                # Abgleiche); erst eine zweite in Folge heißt, dass die Anmeldung weg ist und der Nutzer gebraucht wird.
                failures = int(self.db.kv_get("tesla_refresh_failures", "0") or 0) + 1
                self.db.kv_set("tesla_refresh_failures", str(failures))
                if 400 <= r.status_code < 500 and failures >= REFRESH_FAILURES_FOR_SIGN_IN:
                    self.db.kv_set("tesla_auth_error", msg)
                raise TeslaError(msg)
            self._store_tokens(r.json())
            return self.db.kv_get("tesla_access_token") or ""

    # --- API -------------------------------------------------------------------
    async def _get(self, path: str, params: dict | None = None, *, raw: bool = False):
        if self.calls_used() >= self.s.api_budget:
            raise BudgetExceeded(
                f"Monthly budget of {self.s.api_budget} Tesla requests reached – sync paused until next month."
            )
        retry_at = float(self.db.kv_get("tesla_retry_at", "0") or 0)
        if time.time() < retry_at:
            # Erneut fragen, solange Tesla uns noch begrenzt, kostet nur Anfragen und verlängert die Grenze.
            raise RateLimited("Tesla asked to wait (HTTP 429) until "
                              f"{datetime.fromtimestamp(retry_at, UTC).isoformat(timespec='seconds')}.")
        for attempt in (1, 2):
            token = await self._access_token(force_refresh=attempt == 2)
            r = await self._http.get(
                self.s.fleet_base + path,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            self.db.log_call(path.split("/invoice/")[0], "data", r.status_code)
            if r.status_code == 401 and attempt == 1:
                continue
            if r.status_code == 429:
                wait = retry_after_seconds(r.headers.get("retry-after"))
                self.db.kv_set("tesla_retry_at", str(time.time() + wait))
                log.warning("Tesla limits requests (HTTP 429) – pausing for %d s", round(wait))
                raise RateLimited(f"Tesla {path}: HTTP 429 – too many requests, waiting {round(wait)} s.")
            if r.status_code >= 400:
                error = Rejected if r.status_code < 500 else TeslaError
                raise error(f"Tesla {path}: HTTP {r.status_code} – {r.text[:200]}")
            return r.content if raw else r.json()
        raise TeslaError("Tesla rejected the credentials.")

    async def charging_history(self, start_time: datetime | None = None) -> list[dict]:
        """Die Supercharger-Historie holen. Mit start_time nur den jüngsten Teil."""
        base: dict = {"pageSize": PAGE_SIZE}
        if self.s.tesla_vin:
            base["vin"] = self.s.tesla_vin
        if start_time:
            base["startTime"] = start_time.astimezone(UTC).isoformat(timespec="seconds")

        try:
            first = await self._get(HISTORY_PATH, base)
        except TeslaError as e:
            # Lehnt Tesla das Format des Zeitfilters ab, einmal ohne versuchen.
            if start_time and "HTTP 400" in str(e):
                base.pop("startTime", None)
                first = await self._get(HISTORY_PATH, base)
            else:
                raise
        self.last_raw = first
        items, total = _unwrap(first)
        seen = {_sid(i) for i in items}

        # Seiten sind nur bei vielen Ladungen nötig. Ob Tesla Seiten ab 0 oder 1 zählt, ist egal:
        # Doppelte fallen weg, und eine kurze Seite beendet die Schleife.
        page = 1
        while len(items) < (total or 0) or (total is None and items and len(items) % PAGE_SIZE == 0):
            if page > MAX_PAGES:
                break
            body = await self._get(HISTORY_PATH, {**base, "pageNo": page})
            page_items, _ = _unwrap(body)
            fresh = [i for i in page_items if _sid(i) not in seen]
            items.extend(fresh)
            seen.update(_sid(i) for i in fresh)
            if len(page_items) < PAGE_SIZE:
                break
            if not fresh and page > 1:
                break
            page += 1
        return items

    async def invoice_pdf(self, content_id: str) -> bytes:
        return await self._get(INVOICE_PATH.format(id=quote(content_id, safe="")), raw=True)


# --- response parsing ------------------------------------------------------------
def _unwrap(body) -> tuple[list[dict], int | None]:
    payload = body.get("response", body) if isinstance(body, dict) else body
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, dict):
        data = payload.get("data") or []
        total = payload.get("totalResults")
        try:
            total = int(total) if total is not None else None
        except (TypeError, ValueError):
            total = None
        return list(data), total
    return [], None


def _sid(raw: dict) -> str:
    return str(raw.get("sessionId") or raw.get("session_id") or raw.get("id") or "")


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso(value) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def parse_session(raw: dict) -> dict | None:
    """Einen Eintrag der Tesla-Ladehistorie in unser Format umwandeln."""
    sid = _sid(raw)
    if not sid:
        return None

    kwh = charge_cost = idle_fee = other_fee = 0.0
    currency = None
    has_charging_fee = False

    for fee in raw.get("fees") or []:
        ftype = str(fee.get("feeType") or "").upper()
        total = fee_total(fee)
        currency = currency or fee.get("currencyCode")
        if ftype == "CHARGING":
            has_charging_fee = True
            if str(fee.get("uom") or "kwh").lower() == "kwh":
                kwh += sum(_num(fee.get(k)) or 0.0 for k in
                           ("usageBase", "usageTier1", "usageTier2", "usageTier3", "usageTier4"))
            charge_cost += total
        elif ftype in ("PARKING", "IDLE", "CONGESTION"):
            idle_fee += total
        else:
            other_fee += total

    invoices = [
        {"id": inv.get("contentId"), "name": inv.get("fileName"), "type": inv.get("invoiceType")}
        for inv in raw.get("invoices") or []
        if inv.get("contentId")
    ]
    final = has_charging_fee and kwh > 0
    return {
        "session_id": sid,
        "vin": raw.get("vin"),
        "site": raw.get("siteLocationName") or None,
        "country": raw.get("countryCode"),
        "start_ts": _iso(raw.get("chargeStartDateTime")),
        "stop_ts": _iso(raw.get("chargeStopDateTime")),
        "unlatch_ts": _iso(raw.get("unlatchDateTime")),
        "kwh": round(kwh, 3) if final else None,
        "charge_cost": round(charge_cost, 2) if final else None,
        "idle_fee": round(idle_fee, 2),
        "other_fee": round(other_fee, 2),
        "total": round(charge_cost + idle_fee + other_fee, 2) if final else None,
        "currency": currency or "EUR",
        "price": round(charge_cost / kwh, 4) if final else None,
        "invoices": json.dumps(invoices),
        "raw": json.dumps(raw, ensure_ascii=False),
    }

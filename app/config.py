"""Settings – from environment variables (see .env.example), or from the
Home Assistant app options (/data/options.json) when running as an HA app."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

FLEET_BASE = {
    "eu": "https://fleet-api.prd.eu.vn.cloud.tesla.com",
    "na": "https://fleet-api.prd.na.vn.cloud.tesla.com",
}
AUTH_AUTHORIZE_URL = "https://auth.tesla.com/oauth2/v3/authorize"
AUTH_TOKEN_URL = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"

# Only what we need: sign-in, refresh token, and the charging history incl. invoices.
# Tesla bundles charging history and charging commands into the same scope.
# Ladecockpit only calls read endpoints (see tesla.py) – there is no command code.
SCOPES = "openid offline_access vehicle_charging_cmds"

DEFAULT_LOCALES = {"de": "de-DE", "en": "en-US"}

ADDON_OPTIONS_PATH = Path(os.environ.get("ADDON_OPTIONS_PATH", "/data/options.json"))

# Option name of the Home Assistant app → environment variable
ADDON_OPTION_MAP = {
    "language": "APP_LANG",
    "locale": "APP_LOCALE",
    "tesla_client_id": "TESLA_CLIENT_ID",
    "tesla_client_secret": "TESLA_CLIENT_SECRET",
    "tesla_redirect_uri": "TESLA_REDIRECT_URI",
    "tesla_region": "TESLA_REGION",
    "tesla_vin": "TESLA_VIN",
    "entity_battery": "HA_ENT_SOC",
    "entity_range": "HA_ENT_RANGE",
    "entity_odometer": "HA_ENT_ODOMETER",
    "entity_charging": "HA_ENT_CHARGING",
    "charging_state": "HA_CHARGING_STATE",
    "entity_cost_total": "HA_ENT_COST_TOTAL",
    "entity_kwh_total": "HA_ENT_KWH_TOTAL",
    "entity_reference_price": "HA_ENT_REFERENCE_PRICE",
    "reference_price": "REFERENCE_PRICE",
    "entity_fuel_month": "HA_ENT_FUEL_MONTH",
    "fuel_label": "FUEL_LABEL",
    "soc_floor": "SOC_FLOOR",
    "soc_target": "SOC_TARGET",
    "notify_problems": "NOTIFY_PROBLEMS",
    "publish_entities": "PUBLISH_ENTITIES",
    "sync_interval_hours": "SYNC_INTERVAL_H",
    "api_budget_requests": "API_BUDGET_REQUESTS",
}


def addon_overlay() -> dict[str, str]:
    """When running as a Home Assistant app: map its options to our settings."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token or not ADDON_OPTIONS_PATH.exists():
        return {}
    try:
        options = json.loads(ADDON_OPTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    env = {"HA_URL": "http://supervisor/core", "HA_TOKEN": token,
           "DATA_DIR": str(ADDON_OPTIONS_PATH.parent), "ADDON": "1"}
    for key, var in ADDON_OPTION_MAP.items():
        value = options.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            value = "1" if value else "0"
        env[var] = str(value)
    return env


_OVERLAY: dict[str, str] = {}


def _env(name: str, default: str = "") -> str:
    value = _OVERLAY.get(name)
    if value is None:
        value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _bool(name: str, default: bool) -> bool:
    raw = _env(name).lower()
    if raw == "":
        return default
    return raw in ("1", "true", "yes", "on")


def _float(name: str, default: float | None) -> float | None:
    raw = _env(name)
    if raw == "":
        return default
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(float(_env(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    tz: ZoneInfo
    lang: str
    locale: str
    # Tesla
    tesla_client_id: str
    tesla_client_secret: str
    tesla_redirect_uri: str
    tesla_region: str
    tesla_vin: str
    # Home Assistant (all entities optional)
    ha_url: str
    ha_token: str
    ha_event: str
    ha_poll_seconds: int
    ent_soc: str
    ent_range: str
    ent_odometer: str
    ent_charging: str
    charging_value: str
    ent_cost_total: str
    ent_kwh_total: str
    ent_reference_price: str
    reference_price: float | None
    ent_fuel_month: str
    fuel_label: str
    # Behaviour
    soc_floor: int
    soc_target: int
    sync_interval_h: float
    burst_interval_min: float
    burst_duration_min: float
    push_max_age_h: float
    api_budget: int
    app_password: str
    force_demo: bool
    addon: bool
    notify_problems: bool
    publish_entities: bool
    # Development only: point the app at a mock server
    api_base_override: str = ""
    token_url_override: str = ""

    @property
    def fleet_base(self) -> str:
        return self.api_base_override or FLEET_BASE.get(self.tesla_region, FLEET_BASE["eu"])

    @property
    def token_url(self) -> str:
        return self.token_url_override or AUTH_TOKEN_URL

    @property
    def tesla_configured(self) -> bool:
        return bool(self.tesla_client_id and self.tesla_client_secret)

    @property
    def ha_configured(self) -> bool:
        return bool(self.ha_url and self.ha_token)

    @property
    def demo(self) -> bool:
        return self.force_demo or not (self.tesla_configured or self.ha_configured)


def load() -> Settings:
    global _OVERLAY
    _OVERLAY = addon_overlay()
    lang = _env("APP_LANG", "en").lower()[:2]
    if lang not in DEFAULT_LOCALES:
        lang = "en"
    return Settings(
        data_dir=Path(_env("DATA_DIR", "./data")),
        tz=ZoneInfo(_env("TZ", "Europe/Berlin")),
        lang=lang,
        locale=_env("APP_LOCALE", DEFAULT_LOCALES[lang]),
        tesla_client_id=_env("TESLA_CLIENT_ID"),
        tesla_client_secret=_env("TESLA_CLIENT_SECRET"),
        tesla_redirect_uri=_env("TESLA_REDIRECT_URI", "http://localhost:8077/auth/callback"),
        tesla_region=_env("TESLA_REGION", "eu").lower(),
        tesla_vin=_env("TESLA_VIN"),
        ha_url=_env("HA_URL").rstrip("/"),
        ha_token=_env("HA_TOKEN"),
        ha_event=_env("HA_EVENT", "ladecockpit_invoice"),
        ha_poll_seconds=max(15, _int("HA_POLL_SECONDS", 60)),
        ent_soc=_env("HA_ENT_SOC"),
        ent_range=_env("HA_ENT_RANGE"),
        ent_odometer=_env("HA_ENT_ODOMETER"),
        ent_charging=_env("HA_ENT_CHARGING"),
        charging_value=_env("HA_CHARGING_STATE", "charging"),
        ent_cost_total=_env("HA_ENT_COST_TOTAL"),
        ent_kwh_total=_env("HA_ENT_KWH_TOTAL"),
        ent_reference_price=_env("HA_ENT_REFERENCE_PRICE"),
        reference_price=_float("REFERENCE_PRICE", None),
        ent_fuel_month=_env("HA_ENT_FUEL_MONTH"),
        fuel_label=_env("FUEL_LABEL"),
        soc_floor=_int("SOC_FLOOR", 10),
        soc_target=_int("SOC_TARGET", 80),
        sync_interval_h=_float("SYNC_INTERVAL_H", 6) or 6,
        burst_interval_min=_float("BURST_INTERVAL_MIN", 10) or 10,
        burst_duration_min=_float("BURST_DURATION_MIN", 180) or 180,
        push_max_age_h=_float("PUSH_MAX_AGE_H", 72) or 72,
        api_budget=_int("API_BUDGET_REQUESTS", 1500),
        app_password=_env("APP_PASSWORD"),
        force_demo=_env("APP_MODE", "").lower() == "demo",
        addon=_env("ADDON") == "1",
        notify_problems=_bool("NOTIFY_PROBLEMS", True),
        publish_entities=_bool("PUBLISH_ENTITIES", True),
        api_base_override=_env("TESLA_API_BASE_OVERRIDE").rstrip("/"),
        token_url_override=_env("TESLA_TOKEN_URL_OVERRIDE"),
    )


settings = load()

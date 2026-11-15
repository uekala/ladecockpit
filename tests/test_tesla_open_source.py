"""Sign-in for Tesla "Open Source Apps": a client ID without a secret, protected by PKCE."""
import asyncio
import base64
import dataclasses
import hashlib
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException

from app import main
from app.config import AUTH_TOKEN_URL, AUTH_TOKEN_URL_OPEN_SOURCE
from app.db import DB
from app.tesla import TeslaClient, pkce_challenge


def configured(settings, tmp_path, **changes):
    return dataclasses.replace(
        settings, data_dir=tmp_path, tesla_client_id="open-client", tesla_client_secret="",
        ha_url="", ha_token="", force_demo=False, **changes)


def wire(monkeypatch, settings, tmp_path):
    """Point the app at a mocked Tesla and return what it was asked."""
    database = DB(tmp_path / "open.db")
    posted = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append((str(request.url), parse_qs(request.content.decode())))
        return httpx.Response(200, json={
            "access_token": "access", "refresh_token": "refresh", "expires_in": 28800})

    tesla = TeslaClient(settings, database, transport=httpx.MockTransport(handler))

    class Sync:
        woke = 0

        def wake(self):
            self.woke += 1

    sync = Sync()
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "db", database)
    monkeypatch.setattr(main, "tesla", tesla)
    monkeypatch.setattr(main, "sync", sync)
    return database, posted, sync


def test_challenge_matches_rfc_7636_example():
    assert pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == \
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_a_client_id_alone_is_enough(settings, tmp_path):
    open_source = configured(settings, tmp_path)
    assert open_source.tesla_configured and open_source.tesla_open_source
    assert open_source.demo is False
    assert open_source.token_url == AUTH_TOKEN_URL_OPEN_SOURCE
    with_secret = dataclasses.replace(open_source, tesla_client_secret="secret")
    assert with_secret.tesla_configured and not with_secret.tesla_open_source
    assert with_secret.token_url == AUTH_TOKEN_URL
    nothing = dataclasses.replace(open_source, tesla_client_id="")
    assert not nothing.tesla_configured and not nothing.tesla_open_source


def test_sign_in_without_secret_uses_pkce(settings, tmp_path, monkeypatch):
    settings = configured(settings, tmp_path)
    database, posted, sync = wire(monkeypatch, settings, tmp_path)

    redirect = asyncio.run(main.auth_login())
    query = parse_qs(urlparse(redirect.headers["location"]).query)
    verifier = database.kv_get("oauth_verifier")
    assert len(verifier) >= 43
    assert query["code_challenge_method"] == ["S256"]
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [expected]
    assert query["client_id"] == ["open-client"]

    asyncio.run(main.auth_callback(code="the-code", state=query["state"][0]))
    url, form = posted[0]
    assert url == AUTH_TOKEN_URL_OPEN_SOURCE
    assert form["code_verifier"] == [verifier]
    assert form["code"] == ["the-code"]
    assert "client_secret" not in form
    assert database.kv_get("tesla_refresh_token") == "refresh"
    # The verifier is single-use.
    assert database.kv_get("oauth_verifier") is None
    assert sync.woke == 1


def test_pasted_code_uses_the_stored_verifier(settings, tmp_path, monkeypatch):
    settings = configured(settings, tmp_path)
    database, posted, _sync = wire(monkeypatch, settings, tmp_path)
    asyncio.run(main.auth_login())
    verifier = database.kv_get("oauth_verifier")
    pasted = "http://localhost:8077/auth/callback?code=pasted-code&state=x"
    assert asyncio.run(main.auth_code(main.CodeIn(value=pasted))) == {"ok": True}
    assert posted[0][1]["code_verifier"] == [verifier]
    assert posted[0][1]["code"] == ["pasted-code"]


def test_code_without_started_sign_in_is_refused(settings, tmp_path, monkeypatch):
    settings = configured(settings, tmp_path)
    _database, posted, _sync = wire(monkeypatch, settings, tmp_path)
    with pytest.raises(HTTPException) as refused:
        asyncio.run(main.auth_code(main.CodeIn(value="stray-code")))
    assert refused.value.status_code == 400
    assert posted == []


def test_sign_in_with_secret_is_unchanged(settings, tmp_path, monkeypatch):
    settings = dataclasses.replace(configured(settings, tmp_path), tesla_client_secret="secret")
    database, posted, _sync = wire(monkeypatch, settings, tmp_path)
    database.kv_set("oauth_verifier", "left-over")

    redirect = asyncio.run(main.auth_login())
    query = parse_qs(urlparse(redirect.headers["location"]).query)
    assert "code_challenge" not in query
    assert database.kv_get("oauth_verifier") is None

    asyncio.run(main.auth_callback(code="the-code", state=query["state"][0]))
    url, form = posted[0]
    assert url == AUTH_TOKEN_URL
    assert form["client_secret"] == ["secret"]
    assert "code_verifier" not in form


def test_refresh_goes_to_the_open_source_endpoint(settings, tmp_path, monkeypatch):
    settings = configured(settings, tmp_path)
    database, posted, _sync = wire(monkeypatch, settings, tmp_path)
    database.kv_set("tesla_refresh_token", "old-refresh")
    tesla = main.tesla
    assert asyncio.run(tesla._access_token()) == "access"
    url, form = posted[0]
    assert url == AUTH_TOKEN_URL_OPEN_SOURCE
    assert form == {"grant_type": ["refresh_token"], "client_id": ["open-client"],
                    "refresh_token": ["old-refresh"]}

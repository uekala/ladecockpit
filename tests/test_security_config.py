from app.config import load


def _clear_connection(monkeypatch):
    for key in ("TESLA_CLIENT_ID", "TESLA_CLIENT_SECRET", "HA_URL", "HA_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)


def test_standalone_live_install_requires_password_by_default(monkeypatch):
    _clear_connection(monkeypatch)
    monkeypatch.delenv("ADDON", raising=False)
    monkeypatch.delenv("APP_REQUIRE_PASSWORD", raising=False)
    monkeypatch.delenv("APP_MODE", raising=False)
    monkeypatch.setenv("TESLA_CLIENT_ID", "client")
    monkeypatch.setenv("TESLA_CLIENT_SECRET", "secret")

    settings = load()

    assert not settings.demo
    assert settings.require_password is True


def test_demo_mode_does_not_require_password_at_startup(monkeypatch):
    _clear_connection(monkeypatch)
    monkeypatch.delenv("ADDON", raising=False)
    monkeypatch.delenv("APP_REQUIRE_PASSWORD", raising=False)
    monkeypatch.setenv("APP_MODE", "demo")

    settings = load()

    assert settings.demo
    assert settings.require_password is True  # the live-only startup check is skipped


def test_home_assistant_addon_uses_ingress_auth_by_default(monkeypatch):
    _clear_connection(monkeypatch)
    monkeypatch.setenv("ADDON", "1")
    monkeypatch.delenv("APP_REQUIRE_PASSWORD", raising=False)
    monkeypatch.setenv("TESLA_CLIENT_ID", "client")
    monkeypatch.setenv("TESLA_CLIENT_SECRET", "secret")

    settings = load()

    assert settings.addon
    assert settings.require_password is False


def test_password_requirement_can_be_explicitly_enabled_for_addon(monkeypatch):
    _clear_connection(monkeypatch)
    monkeypatch.setenv("ADDON", "1")
    monkeypatch.setenv("APP_REQUIRE_PASSWORD", "true")

    settings = load()

    assert settings.require_password is True


def test_password_requirement_can_be_explicitly_disabled_for_standalone(monkeypatch):
    _clear_connection(monkeypatch)
    monkeypatch.delenv("ADDON", raising=False)
    monkeypatch.setenv("APP_REQUIRE_PASSWORD", "false")
    monkeypatch.setenv("TESLA_CLIENT_ID", "client")
    monkeypatch.setenv("TESLA_CLIENT_SECRET", "secret")

    settings = load()

    assert settings.require_password is False

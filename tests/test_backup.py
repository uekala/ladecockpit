"""Backup and restore: the charging history moves, the Tesla sign-in stays."""
import asyncio
import dataclasses
import io
import json
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient
from fpdf import FPDF

from app import backup, main
from app.config import load
from app.db import DB


def _pdf() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Tesla invoice")
    return bytes(pdf.output())


def _session(session_id: str, start: str) -> dict:
    return {"session_id": session_id, "vin": "TESTVIN0000000001", "site": "Musterstadt, Germany", "country": "DE",
            "start_ts": start, "stop_ts": start, "kwh": 20.0, "charge_cost": 9.0, "idle_fee": 0.0, "other_fee": 0.0,
            "total": 9.0, "currency": "EUR", "price": 0.45, "invoices": json.dumps([{"id": "inv-" + session_id}]),
            "raw": "{}"}


def _filled(tmp_path, name="source"):
    folder = tmp_path / name
    db = DB(folder / "ladecockpit.db")
    db.upsert_session(_session("a1", "2026-10-01T10:00:00+00:00"), "pushed")
    db.upsert_session(_session("b2", "2026-10-02T10:00:00+00:00"), "backfill")
    db.add_reading("soc", 55)
    db.log_call("/history", "charging", 200)
    db.kv_set("ui_look", "dynamic")
    db.kv_set("push_since", "2026-10-01T00:00:00+00:00")
    db.kv_set("tesla_refresh_token", "SECRET-REFRESH")
    db.kv_set("tesla_access_token", "SECRET-ACCESS")
    db.kv_set("oauth_state", "SECRET-STATE")
    (folder / "invoices").mkdir()
    (folder / "invoices" / "a1.pdf").write_bytes(_pdf())
    (folder / "invoices" / "a1.p1.png").write_bytes(b"png cache, not part of a backup")
    return db, folder


def test_backup_leaves_the_tesla_sign_in_out(tmp_path):
    db, folder = _filled(tmp_path)
    target = tmp_path / "backup.zip"
    manifest = backup.create(db, folder, "9.9.9", target)
    assert manifest["sessions"] == 2 and manifest["invoices"] == 1 and manifest["version"] == "9.9.9"
    with zipfile.ZipFile(target) as zf:
        assert sorted(zf.namelist()) == ["invoices/a1.pdf", "ladecockpit.db", "manifest.json"]
        blob = b"".join(zf.read(n) for n in zf.namelist())
    assert b"SECRET" not in blob
    # The running installation still has its sign-in.
    assert db.kv_get("tesla_refresh_token") == "SECRET-REFRESH"


def test_restore_replaces_history_and_keeps_local_sign_in(tmp_path):
    source_db, source_dir = _filled(tmp_path)
    target = tmp_path / "backup.zip"
    backup.create(source_db, source_dir, "9.9.9", target)

    dest_dir = tmp_path / "dest"
    dest = DB(dest_dir / "ladecockpit.db")
    dest.upsert_session(_session("old", "2025-01-01T10:00:00+00:00"), "new")
    dest.kv_set("tesla_refresh_token", "LOCAL-TOKEN")
    dest.kv_set("ui_look", "classic")

    result = backup.restore(dest, dest_dir, target)
    assert result["sessions"] == 2 and result["readings"] == 1 and result["invoices"] == 1
    assert [s["session_id"] for s in dest.sessions()] == ["b2", "a1"]
    # Restored sessions keep their state, so nothing is reported to Home Assistant twice.
    assert {s["session_id"]: s["push_state"] for s in dest.sessions()} == {"a1": "pushed", "b2": "backfill"}
    assert dest.sessions_to_push() == []
    assert dest.kv_get("ui_look") == "dynamic" and dest.kv_get("push_since") == "2026-10-01T00:00:00+00:00"
    assert dest.kv_get("tesla_refresh_token") == "LOCAL-TOKEN"
    assert dest.kv_get("oauth_state") is None
    assert (dest_dir / "invoices" / "a1.pdf").read_bytes().startswith(b"%PDF-")
    assert dest.last_reading("soc")[1] == 55


def _zip(members: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize("payload", [
    b"not a zip at all",
    _zip({"something.txt": "hello"}),
    _zip({"manifest.json": "{broken", "ladecockpit.db": b"x"}),
    _zip({"manifest.json": json.dumps({"app": "other", "format": 1}), "ladecockpit.db": b"x"}),
    _zip({"manifest.json": json.dumps({"app": "ladecockpit", "format": 99}), "ladecockpit.db": b"x"}),
    _zip({"manifest.json": json.dumps({"app": "ladecockpit", "format": 1}), "ladecockpit.db": b"not sqlite"}),
])
def test_broken_backups_change_nothing(tmp_path, payload):
    db, folder = _filled(tmp_path)
    source = tmp_path / "upload.zip"
    source.write_bytes(payload)
    with pytest.raises(backup.BackupError):
        backup.restore(db, folder, source)
    assert [s["session_id"] for s in db.sessions()] == ["b2", "a1"]
    assert db.kv_get("ui_look") == "dynamic"


def test_foreign_database_and_unsafe_names_are_refused(tmp_path):
    db, folder = _filled(tmp_path)
    other = tmp_path / "other.db"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE notes(text TEXT)")
    conn.commit()
    conn.close()
    source = tmp_path / "upload.zip"
    source.write_bytes(_zip({"manifest.json": json.dumps({"app": "ladecockpit", "format": 1}),
                             "ladecockpit.db": other.read_bytes()}))
    with pytest.raises(backup.BackupError):
        backup.restore(db, folder, source)
    assert len(db.sessions()) == 2

    good = tmp_path / "good.zip"
    backup.create(db, folder, "9.9.9", good)
    with zipfile.ZipFile(good, "a") as zf:
        zf.writestr("../escape.pdf", _pdf())
        zf.writestr("invoices/../../escape2.pdf", _pdf())
        zf.writestr("invoices/fake.pdf", b"<html>not a pdf</html>")
        zf.writestr("invoices/sub/dir.pdf", _pdf())
    dest_dir = tmp_path / "dest"
    dest = DB(dest_dir / "ladecockpit.db")
    assert backup.restore(dest, dest_dir, good)["invoices"] == 1
    assert sorted(p.name for p in (dest_dir / "invoices").iterdir()) == ["a1.pdf"]
    assert not (tmp_path / "escape.pdf").exists() and not (tmp_path / "escape2.pdf").exists()


def test_endpoints_refuse_in_demo():
    with TestClient(main.app) as client:
        assert client.get("/api/backup.zip").status_code == 404
        assert client.post("/api/restore", content=b"x", headers={"Content-Type": "application/zip"}).status_code == 400


class _IdleSync:
    last_sync = None
    next_sync = None
    last_error = None
    bursting = False

    async def run_forever(self):
        await asyncio.Event().wait()


def test_endpoints_round_trip_in_live_mode(monkeypatch, tmp_path):
    db, folder = _filled(tmp_path)
    settings = dataclasses.replace(load(), data_dir=folder, tesla_client_id="id", tesla_client_secret="secret",
                                   app_password="pw", ha_url="", ha_token="", force_demo=False)
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "db", db)
    monkeypatch.setattr(main, "sync", _IdleSync())
    with TestClient(main.app) as client:
        assert client.get("/api/backup.zip").status_code == 401
        client.auth = ("ladecockpit", "pw")
        download = client.get("/api/backup.zip")
        assert download.status_code == 200 and download.headers["content-type"] == "application/zip"
        assert "ladecockpit-backup-" in download.headers["content-disposition"]
        assert b"SECRET" not in download.content

        db.upsert_session(_session("later", "2026-11-01T10:00:00+00:00"), "new")
        assert client.post("/api/restore", content=download.content).status_code == 415
        assert client.post("/api/restore", content=b"junk", headers={"Content-Type": "application/zip"}).status_code == 400
        assert len(db.sessions()) == 3
        restored = client.post("/api/restore", content=download.content, headers={"Content-Type": "application/zip"})
        assert restored.status_code == 200 and restored.json()["sessions"] == 2
        assert [s["session_id"] for s in db.sessions()] == ["b2", "a1"]
        assert db.kv_get("tesla_refresh_token") == "SECRET-REFRESH"

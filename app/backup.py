"""Backup and restore: charging history, readings, settings made in the web app and the cached
invoices in one ZIP file.

The Tesla sign-in is left out on purpose: a backup file must not hold the keys to a Tesla account.
After moving to another device, sign in with Tesla once. Restoring keeps the sign-in the
installation has."""
from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .db import DB
from .invoices import is_pdf

FORMAT = 1
DB_NAME = "ladecockpit.db"
MANIFEST = "manifest.json"
MAX_UPLOAD = 300 * 1024 * 1024      # the ZIP file itself
MAX_MEMBER = 60 * 1024 * 1024       # one invoice
MAX_DATABASE = 500 * 1024 * 1024
MAX_UNPACKED = 1024 * 1024 * 1024   # everything in the ZIP, unpacked
_INVOICE = re.compile(r"invoices/[A-Za-z0-9_-]{1,120}\.pdf")


class BackupError(ValueError):
    """The file is not a usable Ladecockpit backup."""


def create(db: DB, data_dir: Path, version: str, target: Path) -> dict:
    """Write a backup to `target` and return its manifest."""
    with tempfile.TemporaryDirectory(prefix="ladecockpit-backup-") as tmp:
        snapshot = Path(tmp) / DB_NAME
        counts = db.snapshot(snapshot)
        invoices = sorted((data_dir / "invoices").glob("*.pdf")) if (data_dir / "invoices").is_dir() else []
        manifest = {"app": "ladecockpit", "format": FORMAT, "version": version,
                    "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "sessions": counts["sessions"], "readings": counts["readings"], "invoices": len(invoices)}
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST, json.dumps(manifest, indent=2))
            zf.write(snapshot, DB_NAME)
            for pdf in invoices:
                zf.write(pdf, f"invoices/{pdf.name}")
    return manifest


def restore(db: DB, data_dir: Path, source: Path) -> dict:
    """Replace the charging history with the one in the backup at `source`.

    The database is checked before anything changes and swapped in one transaction, so a broken
    file leaves the installation as it was. Invoices in the backup are added to the cache."""
    try:
        zf = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as e:
        raise BackupError("This is not a ZIP file.") from e
    with zf:
        names = {i.filename: i for i in zf.infolist()}
        if MANIFEST not in names or DB_NAME not in names:
            raise BackupError("This ZIP file is not a Ladecockpit backup.")
        if sum(i.file_size for i in names.values()) > MAX_UNPACKED or names[DB_NAME].file_size > MAX_DATABASE:
            raise BackupError("The backup is too large.")
        try:
            manifest = json.loads(zf.read(MANIFEST))
        except (ValueError, UnicodeDecodeError) as e:
            raise BackupError("The backup has no readable manifest.") from e
        if not isinstance(manifest, dict) or manifest.get("app") != "ladecockpit":
            raise BackupError("This ZIP file is not a Ladecockpit backup.")
        if manifest.get("format") != FORMAT:
            raise BackupError("This backup was made by a newer Ladecockpit. Update first, then restore.")
        with tempfile.TemporaryDirectory(prefix="ladecockpit-restore-") as tmp:
            snapshot = Path(tmp) / DB_NAME
            with zf.open(DB_NAME) as src, snapshot.open("wb") as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
            try:
                counts = db.restore_from(snapshot)
            except sqlite3.Error as e:
                raise BackupError("The database in the backup cannot be read.") from e
        restored = 0
        folder = data_dir / "invoices"
        for name, info in names.items():
            if not _INVOICE.fullmatch(name) or info.file_size > MAX_MEMBER:
                continue
            data = zf.read(name)
            if not is_pdf(data):
                continue
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / name.split("/", 1)[1]
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_bytes(data)
            tmp_path.replace(path)
            restored += 1
    return {**counts, "invoices": restored, "created": manifest.get("created"), "version": manifest.get("version")}

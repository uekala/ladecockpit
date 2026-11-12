"""SQLite storage: tokens, charging sessions (invoices), readings, API counter."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import networks
from .pricing import price_details

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    vin         TEXT,
    site        TEXT,
    country     TEXT,
    start_ts    TEXT,
    stop_ts     TEXT,
    unlatch_ts  TEXT,
    kwh         REAL,
    charge_cost REAL,
    idle_fee    REAL,
    other_fee   REAL,
    total       REAL,
    currency    TEXT,
    price       REAL,
    invoices    TEXT,
    raw         TEXT,
    first_seen  TEXT NOT NULL,
    push_state  TEXT NOT NULL DEFAULT 'new',   -- new | pushed | backfill | stale
    pushed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_ts);
CREATE TABLE IF NOT EXISTS readings (
    ts    TEXT NOT NULL,
    key   TEXT NOT NULL,     -- soc | range | odometer
    value REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_key_ts ON readings(key, ts);
CREATE TABLE IF NOT EXISTS api_calls (
    ts       TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    category TEXT NOT NULL,
    status   INTEGER
);
"""

# Fields that may still change after the first fetch (Tesla may finalise billing later).
_MUTABLE = ("site", "stop_ts", "unlatch_ts", "kwh", "charge_cost", "idle_fee",
            "other_fee", "total", "currency", "price", "invoices", "raw")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(sessions)")}
            if "invoice_network" not in cols:  # 0.11.1: the network as the invoice tells it
                self._conn.execute("ALTER TABLE sessions ADD COLUMN invoice_network TEXT")
            if "station" not in cols:  # 0.12: name, address and operator of a MultiPass station (JSON)
                self._conn.execute("ALTER TABLE sessions ADD COLUMN station TEXT")
            self._conn.commit()

    # --- key/value -----------------------------------------------------------
    def kv_get(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def kv_set(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            self._conn.commit()

    def kv_del(self, *keys: str) -> None:
        with self._lock:
            self._conn.executemany("DELETE FROM kv WHERE key=?", [(k,) for k in keys])
            self._conn.commit()

    # --- backup and restore ---------------------------------------------------
    # The Tesla sign-in stays with the installation: it is neither written to a backup nor
    # replaced by one.
    _LOCAL_KV = "key LIKE 'tesla\\_%' ESCAPE '\\' OR key = 'oauth_state'"
    _TABLES = ("sessions", "readings", "api_calls")

    def snapshot(self, target: Path) -> dict:
        """A consistent copy of the database without the Tesla sign-in. Returns row counts."""
        with self._lock:
            dest = sqlite3.connect(target)
            try:
                self._conn.backup(dest)
                dest.execute(f"DELETE FROM kv WHERE {self._LOCAL_KV}")
                dest.commit()
                dest.execute("PRAGMA journal_mode=DELETE")  # one plain file, no -wal beside it
                dest.execute("VACUUM")
                counts = {t: dest.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in self._TABLES}
            finally:
                dest.close()
        return counts

    def restore_from(self, source: Path) -> dict:
        """Replace sessions, readings, the API counter and the settings with those of a snapshot,
        in one transaction. Raises sqlite3.Error when the snapshot is not a Ladecockpit database."""
        src = sqlite3.connect(source)
        src.row_factory = sqlite3.Row
        try:
            if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("integrity check failed")
            tables = {r["name"] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"kv", *self._TABLES} <= tables:
                raise sqlite3.DatabaseError("not a Ladecockpit database")
            plan = []
            for table in self._TABLES:
                theirs = [r["name"] for r in src.execute(f"PRAGMA table_info({table})")]
                with self._lock:
                    ours = {r["name"] for r in self._conn.execute(f"PRAGMA table_info({table})")}
                cols = [c for c in theirs if c in ours]
                if table == "sessions" and not {"session_id", "first_seen"} <= set(cols):
                    raise sqlite3.DatabaseError("not a Ladecockpit database")
                plan.append((table, cols, src.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()))
            kv = src.execute(f"SELECT key, value FROM kv WHERE NOT ({self._LOCAL_KV})").fetchall()
        finally:
            src.close()
        with self._lock:
            try:
                for table, cols, rows in plan:
                    self._conn.execute(f"DELETE FROM {table}")
                    self._conn.executemany(
                        f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",
                        [tuple(r) for r in rows])
                self._conn.execute(f"DELETE FROM kv WHERE NOT ({self._LOCAL_KV})")
                self._conn.executemany("INSERT INTO kv(key, value) VALUES(?, ?)", [tuple(r) for r in kv])
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise
        return {table: len(rows) for table, _cols, rows in plan}

    # --- charging sessions ---------------------------------------------------
    def upsert_session(self, s: dict, push_state: str) -> bool:
        """Insert or update a session. Returns True if it was new."""
        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM sessions WHERE session_id=?", (s["session_id"],)
            ).fetchone()
            if exists:
                sets = ", ".join(f"{k}=?" for k in _MUTABLE)
                self._conn.execute(
                    f"UPDATE sessions SET {sets} WHERE session_id=?",
                    [s.get(k) for k in _MUTABLE] + [s["session_id"]],
                )
                self._conn.commit()
                return False
            cols = ["session_id", "vin", "country", "start_ts", *_MUTABLE, "first_seen", "push_state"]
            vals = [s.get(c) for c in cols[:-2]] + [utcnow_iso(), push_state]
            self._conn.execute(
                f"INSERT INTO sessions({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",
                vals,
            )
            self._conn.commit()
            return True

    def sessions(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM sessions ORDER BY start_ts DESC").fetchall()
        return [self._row(r) for r in rows]

    def session(self, session_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        return self._row(row) if row else None

    def latest_start(self) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT MAX(start_ts) AS m FROM sessions").fetchone()
        return row["m"] if row else None

    def sessions_to_push(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE push_state='new' ORDER BY start_ts ASC"
            ).fetchall()
        return [self._row(r) for r in rows]

    def sessions_to_check(self, since: str, limit: int) -> list[dict]:
        """Sessions with an invoice whose network has not been read from the invoice yet."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE invoice_network IS NULL AND invoices NOT IN ('', '[]') "
                "AND start_ts >= ? ORDER BY start_ts DESC LIMIT ?", (since, limit)
            ).fetchall()
        return [self._row(r) for r in rows]

    def sessions_without_station(self, since: str, limit: int) -> list[dict]:
        """Sessions with an invoice whose station has not been read from it yet."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE station IS NULL AND invoices NOT IN ('', '[]') "
                "AND start_ts >= ? ORDER BY start_ts DESC LIMIT ?", (since, limit)
            ).fetchall()
        return [self._row(r) for r in rows]

    def sessions_with_station(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions WHERE station IS NOT NULL AND station NOT IN ('', '{}')"
            ).fetchall()
        return [self._row(r) for r in rows]

    def set_station(self, session_id: str, station: dict) -> None:
        with self._lock:
            self._conn.execute("UPDATE sessions SET station=? WHERE session_id=?",
                               (json.dumps(station, ensure_ascii=False), session_id))
            self._conn.commit()

    def set_invoice_network(self, session_id: str, network: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE sessions SET invoice_network=? WHERE session_id=?", (network, session_id))
            self._conn.commit()

    def set_push_state(self, session_id: str, state: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET push_state=?, pushed_at=? WHERE session_id=?",
                (state, utcnow_iso() if state == "pushed" else None, session_id),
            )
            self._conn.commit()

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["invoices"] = json.loads(d.get("invoices") or "[]")
        except json.JSONDecodeError:
            d["invoices"] = []
        try:
            d["station"] = json.loads(d["station"]) if d.get("station") else None
        except (json.JSONDecodeError, TypeError):
            d["station"] = None
        raw = d.pop("raw", None)
        if "raw" in row.keys():
            try:
                record = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                record = None
            d["network"], d["network_reason"] = networks.classify(record)
            # The invoice has the last word: its number says MultiPass or Supercharger.
            if d.get("invoice_network") in (networks.MULTIPASS, networks.SUPERCHARGER) and d["invoice_network"] != d["network"]:
                d["network"], d["network_reason"] = d["invoice_network"], "invoice number"
            d.update(price_details(record))
            if d["list_cost"] is None and d.get("charge_cost") is not None:
                d["list_cost"] = d["charge_cost"]
            d["list_price"] = round(d["list_cost"] / d["kwh"], 4) if d.get("kwh") and d["list_cost"] is not None else None
        return d

    # --- readings (battery, range, odometer) --------------------------------
    def add_reading(self, key: str, value: float, ts: datetime | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO readings(ts, key, value) VALUES(?, ?, ?)",
                (iso(ts) if ts else utcnow_iso(), key, float(value)),
            )
            self._conn.commit()

    def last_reading(self, key: str) -> tuple[datetime, float] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT ts, value FROM readings WHERE key=? ORDER BY ts DESC LIMIT 1", (key,)
            ).fetchone()
        return (datetime.fromisoformat(row["ts"]), row["value"]) if row else None

    def readings_since(self, key: str, since: datetime) -> list[tuple[datetime, float]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, value FROM readings WHERE key=? AND ts>=? ORDER BY ts ASC",
                (key, iso(since)),
            ).fetchall()
        return [(datetime.fromisoformat(r["ts"]), r["value"]) for r in rows]

    def prune_readings(self, before: datetime) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM readings WHERE ts<?", (iso(before),))
            self._conn.commit()

    # --- API counter -----------------------------------------------------------
    def log_call(self, endpoint: str, category: str, status: int | None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO api_calls(ts, endpoint, category, status) VALUES(?, ?, ?, ?)",
                (utcnow_iso(), endpoint, category, status),
            )
            self._conn.commit()

    def calls_this_month(self) -> dict[str, int]:
        month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
        with self._lock:
            rows = self._conn.execute(
                "SELECT category, COUNT(*) AS n FROM api_calls WHERE ts LIKE ? GROUP BY category",
                (f"{month_prefix}%",),
            ).fetchall()
        return {r["category"]: r["n"] for r in rows}

"""SQLite storage: tokens, charging sessions (invoices), readings, API counter."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import networks

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
        raw = d.pop("raw", None)
        if "raw" in row.keys():
            try:
                record = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                record = None
            d["network"], d["network_reason"] = networks.classify(record)
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

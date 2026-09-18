"""SQLite-lagret. Inget ORM - schemat ar litet nog att hallas for hand."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "aktiekoll.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS instrument (
    ticker      TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    currency    TEXT NOT NULL DEFAULT 'SEK',
    sector      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS watchlist (
    ticker        TEXT PRIMARY KEY REFERENCES instrument(ticker) ON DELETE CASCADE,
    target_weight REAL NOT NULL DEFAULT 0,      -- onskad portfoljandel, 0-1
    max_buy_price REAL,                          -- din kopgrans i instrumentets valuta
    thesis        TEXT NOT NULL DEFAULT '',
    added_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS txn (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker    TEXT NOT NULL REFERENCES instrument(ticker) ON DELETE CASCADE,
    kind      TEXT NOT NULL CHECK (kind IN ('BUY','SELL','DIVIDEND','SPLIT')),
    trade_date TEXT NOT NULL,
    quantity  REAL NOT NULL DEFAULT 0,           -- SPLIT: ny/gammal-forhallande
    price     REAL NOT NULL DEFAULT 0,           -- per aktie; DIVIDEND: per aktie
    fee       REAL NOT NULL DEFAULT 0,
    note      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS txn_ticker_date ON txn(ticker, trade_date, id);

CREATE TABLE IF NOT EXISTS quote_cache (
    ticker     TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    payload    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bar_cache (
    key        TEXT PRIMARY KEY,           -- ticker|intervall|dagar
    fetched_at TEXT NOT NULL,
    payload    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker     TEXT NOT NULL,
    direction  TEXT NOT NULL CHECK (direction IN ('LONG','SHORT')),
    setup      TEXT NOT NULL DEFAULT '',   -- din egen benamning pa uppstallningen
    opened_at  TEXT NOT NULL,
    closed_at  TEXT,                        -- NULL = affaren ar oppen
    entry      REAL NOT NULL,
    stop       REAL NOT NULL,               -- planerad stopp vid ingang, styr R
    exit       REAL,
    quantity   REAL NOT NULL,
    fees       REAL NOT NULL DEFAULT 0,
    note       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS trade_opened ON trade(opened_at, id);

CREATE TABLE IF NOT EXISTS setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "base_currency": "SEK",
    "min_dividend_yield": "0.03",   # 3 % direktavkastning som lagsta niva
    "max_pe": "20",
    "max_position_pct": "0.15",     # ingen post storre an 15 % av portfoljen
    "courtage_min": "1",            # kr per order
    "courtage_pct": "0.0025",       # 0,25 %
    "max_courtage_pct_of_order": "0.005",  # avbryt kop dar courtaget ater mer an 0,5 %
    "monthly_budget": "5000",
    # Daytrading: kontostorlek och hur mycket av den en enskild affar far riskera.
    "account_size": "100000",
    "risk_per_trade_pct": "0.01",
    "default_interval": "5m",
    # Intradag begransas av risken, inte av exponeringen: en daytrade kan vara
    # halva kontot med 1 % risk. Darfor ett eget, hogre tak an langsiktstaket.
    "max_intraday_position_pct": "0.5",
}


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or os.environ.get("AKTIEKOLL_DB") or DEFAULT_DB_PATH
    if path != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO setting (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


@contextmanager
def session(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()


def get_settings(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM setting").fetchall()
    merged = dict(DEFAULT_SETTINGS)
    merged.update({r["key"]: r["value"] for r in rows})
    return merged


def put_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO setting (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()


def setting_float(settings: dict[str, str], key: str, fallback: float = 0.0) -> float:
    try:
        return float(settings.get(key, DEFAULT_SETTINGS.get(key, fallback)))
    except (TypeError, ValueError):
        return fallback

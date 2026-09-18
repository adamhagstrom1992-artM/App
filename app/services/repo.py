"""Tunn atkomst till tabellerna. Haller SQL:en pa ett stalle."""
from __future__ import annotations

import sqlite3
from datetime import date

from .holdings import Transaction


def upsert_instrument(conn: sqlite3.Connection, ticker: str, name: str = "",
                      currency: str = "SEK", sector: str = "") -> None:
    conn.execute(
        "INSERT INTO instrument (ticker, name, currency, sector) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(ticker) DO UPDATE SET "
        "  name = CASE WHEN excluded.name <> '' THEN excluded.name ELSE instrument.name END,"
        "  currency = CASE WHEN excluded.currency <> '' THEN excluded.currency ELSE instrument.currency END,"
        "  sector = CASE WHEN excluded.sector <> '' THEN excluded.sector ELSE instrument.sector END",
        (ticker.upper(), name, currency.upper(), sector),
    )
    conn.commit()


def get_instrument(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM instrument WHERE ticker = ?", (ticker.upper(),)).fetchone()


def list_instruments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM instrument ORDER BY ticker").fetchall()


# --- bevakningslista -------------------------------------------------------

def list_watchlist(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT w.*, i.name, i.currency, i.sector FROM watchlist w "
        "JOIN instrument i ON i.ticker = w.ticker ORDER BY w.ticker"
    ).fetchall()


def get_watch(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM watchlist WHERE ticker = ?", (ticker.upper(),)).fetchone()


def add_watch(conn: sqlite3.Connection, ticker: str, target_weight: float = 0.0,
              max_buy_price: float | None = None, thesis: str = "") -> None:
    conn.execute(
        "INSERT INTO watchlist (ticker, target_weight, max_buy_price, thesis, added_at) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(ticker) DO UPDATE SET "
        "target_weight = excluded.target_weight, max_buy_price = excluded.max_buy_price, "
        "thesis = excluded.thesis",
        (ticker.upper(), target_weight, max_buy_price, thesis, date.today().isoformat()),
    )
    conn.commit()


def remove_watch(conn: sqlite3.Connection, ticker: str) -> None:
    conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
    conn.commit()


# --- transaktioner ---------------------------------------------------------

def list_transactions(conn: sqlite3.Connection, ticker: str | None = None) -> list[Transaction]:
    if ticker:
        rows = conn.execute(
            "SELECT * FROM txn WHERE ticker = ? ORDER BY trade_date DESC, id DESC", (ticker.upper(),)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM txn ORDER BY trade_date DESC, id DESC").fetchall()
    return [
        Transaction(id=r["id"], ticker=r["ticker"], kind=r["kind"], trade_date=r["trade_date"],
                    quantity=r["quantity"], price=r["price"], fee=r["fee"], note=r["note"])
        for r in rows
    ]


def add_transaction(conn: sqlite3.Connection, ticker: str, kind: str, trade_date: str,
                    quantity: float, price: float, fee: float = 0.0, note: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO txn (ticker, kind, trade_date, quantity, price, fee, note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ticker.upper(), kind.upper(), trade_date, quantity, price, fee, note),
    )
    conn.commit()
    return int(cur.lastrowid)


def delete_transaction(conn: sqlite3.Connection, txn_id: int) -> None:
    conn.execute("DELETE FROM txn WHERE id = ?", (txn_id,))
    conn.commit()


def tracked_tickers(conn: sqlite3.Connection) -> list[str]:
    """Allt appen behover kurser for: bevakat plus allt du nagonsin agt."""
    rows = conn.execute(
        "SELECT ticker FROM watchlist UNION SELECT ticker FROM txn ORDER BY 1"
    ).fetchall()
    return [r[0] for r in rows]

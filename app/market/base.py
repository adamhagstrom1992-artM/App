"""Marknadsdata bakom ett smalt granssnitt.

Tva implementationer: Yahoo (skarp) och Demo (offline). Appen valjer sjalv och
faller tillbaka pa demo om natet inte gar fram, sa att den alltid startar.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

CACHE_TTL = timedelta(minutes=15)


@dataclass
class Quote:
    ticker: str
    name: str = ""
    currency: str = "SEK"
    price: float | None = None
    previous_close: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    pe: float | None = None
    eps: float | None = None
    dividend_per_share: float | None = None
    dividend_yield: float | None = None
    payout_ratio: float | None = None
    market_cap: float | None = None
    sector: str = ""
    source: str = "demo"
    fetched_at: str = ""

    @property
    def change_pct(self) -> float | None:
        if self.price is None or not self.previous_close:
            return None
        return (self.price - self.previous_close) / self.previous_close

    @property
    def pos_in_52w_range(self) -> float | None:
        """0 = arslagsta, 1 = arshogsta. Sager var i spannet kursen star."""
        if self.price is None or self.high_52w is None or self.low_52w is None:
            return None
        span = self.high_52w - self.low_52w
        if span <= 0:
            return None
        return max(0.0, min(1.0, (self.price - self.low_52w) / span))


class Provider(Protocol):
    name: str

    def fetch(self, ticker: str) -> Quote | None: ...

    def fx_rate(self, base: str, quote: str) -> float | None: ...


@dataclass
class MarketData:
    """Cachande fasad. Sparar svar i SQLite sa att vi inte hamrar kallan."""

    provider: Provider
    conn: sqlite3.Connection | None = None
    _fx: dict[tuple[str, str], float] = field(default_factory=dict)

    @property
    def source(self) -> str:
        return self.provider.name

    def _cached(self, ticker: str) -> Quote | None:
        if self.conn is None:
            return None
        row = self.conn.execute(
            "SELECT fetched_at, payload FROM quote_cache WHERE ticker = ?", (ticker,)
        ).fetchone()
        if row is None:
            return None
        try:
            fetched = datetime.fromisoformat(row["fetched_at"])
        except ValueError:
            return None
        if datetime.now(timezone.utc) - fetched > CACHE_TTL:
            return None
        return Quote(**json.loads(row["payload"]))

    def _store(self, quote: Quote) -> None:
        if self.conn is None:
            return
        self.conn.execute(
            "INSERT INTO quote_cache (ticker, fetched_at, payload) VALUES (?, ?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET fetched_at = excluded.fetched_at, "
            "payload = excluded.payload",
            (quote.ticker, quote.fetched_at, json.dumps(asdict(quote))),
        )
        self.conn.commit()

    def quote(self, ticker: str, refresh: bool = False) -> Quote | None:
        ticker = ticker.strip().upper()
        if not refresh:
            hit = self._cached(ticker)
            if hit is not None:
                return hit
        fetched = self.provider.fetch(ticker)
        if fetched is None:
            return self._cached_any(ticker)
        fetched.fetched_at = datetime.now(timezone.utc).isoformat()
        self._store(fetched)
        return fetched

    def _cached_any(self, ticker: str) -> Quote | None:
        """Sista utvag: gammal cache ar battre an ingen kurs alls."""
        if self.conn is None:
            return None
        row = self.conn.execute(
            "SELECT payload FROM quote_cache WHERE ticker = ?", (ticker,)
        ).fetchone()
        return Quote(**json.loads(row["payload"])) if row else None

    def quotes(self, tickers: list[str], refresh: bool = False) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for t in tickers:
            q = self.quote(t, refresh=refresh)
            if q is not None:
                out[q.ticker] = q
        return out

    def to_base(self, amount: float | None, currency: str, base: str = "SEK") -> float | None:
        """Vaxlar ett belopp till basvalutan. Returnerar None om kursen saknas."""
        if amount is None:
            return None
        currency = (currency or base).upper()
        base = base.upper()
        if currency == base:
            return amount
        key = (currency, base)
        if key not in self._fx:
            rate = self.provider.fx_rate(currency, base)
            if rate is None:
                return None
            self._fx[key] = rate
        return amount * self._fx[key]


def build_provider(prefer: str | None = None) -> Provider:
    """Valjer kalla. AKTIEKOLL_SOURCE=demo tvingar offline-lage."""
    choice = (prefer or os.environ.get("AKTIEKOLL_SOURCE") or "auto").lower()
    from .demo import DemoProvider

    if choice == "demo":
        return DemoProvider()

    from .yahoo import YahooProvider

    yahoo = YahooProvider()
    if choice == "yahoo":
        return yahoo
    return yahoo if yahoo.reachable() else DemoProvider()

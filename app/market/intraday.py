"""Intradagsstaplar (OHLCV) for studie och utvardering.

VIKTIGT om fordrojning: Yahoo levererar de flesta borser med cirka 15 minuters
fordrojning. Staplarna duger till att studera setups, rakna indikatorer och
utvardera avslutade affarer - de duger INTE som beslutsunderlag i realtid.
Granssnittet skriver ut fordrojningen vid varje graf.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

# Yahoos egna tak for hur langt bak varje upplosning gar att hamta.
MAX_DAYS = {"1m": 7, "2m": 59, "5m": 59, "15m": 59, "30m": 59, "60m": 729, "1d": 3650}
INTERVALS = ["1m", "5m", "15m", "60m"]
INTERVAL_LABEL = {"1m": "1 minut", "5m": "5 minuter", "15m": "15 minuter", "60m": "1 timme"}
BAR_CACHE_TTL = timedelta(seconds=90)


@dataclass
class Bar:
    ts: str          # ISO-tidpunkt for stapelns borjan
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def is_up(self) -> bool:
        return self.close >= self.open

    @property
    def typical(self) -> float:
        """Typisk kurs (HLC/3) - det VWAP viktas pa."""
        return (self.high + self.low + self.close) / 3

    @property
    def clock(self) -> str:
        return self.ts[11:16] if len(self.ts) >= 16 else self.ts


class YahooBars:
    name = "yahoo"
    delayed_minutes = 15

    def bars(self, ticker: str, interval: str = "5m", days: int = 5) -> list[Bar]:
        days = min(days, MAX_DAYS.get(interval, 59))
        try:
            import yfinance as yf

            frame = yf.Ticker(ticker).history(period=f"{days}d", interval=interval)
            if frame is None or frame.empty:
                return []
            out: list[Bar] = []
            for ts, row in frame.iterrows():
                values = [row.get("Open"), row.get("High"), row.get("Low"), row.get("Close")]
                if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in values):
                    continue
                out.append(Bar(
                    ts=ts.isoformat(),
                    open=float(row["Open"]), high=float(row["High"]),
                    low=float(row["Low"]), close=float(row["Close"]),
                    volume=float(row.get("Volume") or 0),
                ))
            return out
        except Exception as exc:
            log.warning("Kunde inte hamta staplar for %s (%s): %s", ticker, interval, exc)
            return []


class DemoBars:
    """Syntetiska staplar, deterministiska per ticker och dag.

    Finns for att graferna och indikatorerna ska ga att bygga och testa utan
    natverk. Det ar brus, inte marknad - ingenting har gar att dra slutsatser av.
    """

    name = "demo"
    delayed_minutes = 0

    def bars(self, ticker: str, interval: str = "5m", days: int = 5) -> list[Bar]:
        step = {"1m": 1, "5m": 5, "15m": 15, "60m": 60}.get(interval, 5)
        per_day = max(1, (8 * 60 + 25) // step)          # 09:00-17:25, Stockholmsbors
        seed = int(hashlib.sha256(ticker.encode()).hexdigest()[:8], 16)
        price = 80 + (seed % 400) / 2
        state = seed

        def rnd() -> float:
            """Enkel LCG - vi vill ha upprepbart brus, inte kryptografi."""
            nonlocal state
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            return state / 0x7FFFFFFF - 0.5

        start = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0)
        start -= timedelta(days=days - 1)
        out: list[Bar] = []
        for day in range(days):
            day_start = start + timedelta(days=day)
            drift = rnd() * 0.004
            for i in range(per_day):
                ts = day_start + timedelta(minutes=i * step)
                move = price * (drift + rnd() * 0.006)
                o = price
                c = max(1.0, o + move)
                h = max(o, c) * (1 + abs(rnd()) * 0.003)
                l = min(o, c) * (1 - abs(rnd()) * 0.003)
                out.append(Bar(ts=ts.isoformat(), open=round(o, 2), high=round(h, 2),
                               low=round(l, 2), close=round(c, 2),
                               volume=round(1000 + abs(rnd()) * 8000)))
                price = c
        return out


class BarFeed:
    """Cachande fasad. Intradagsdata andras standigt, sa TTL:en ar kort."""

    def __init__(self, provider, conn: sqlite3.Connection | None = None) -> None:
        self.provider = provider
        self.conn = conn

    @property
    def source(self) -> str:
        return self.provider.name

    @property
    def delayed_minutes(self) -> int:
        return getattr(self.provider, "delayed_minutes", 0)

    def _key(self, ticker: str, interval: str, days: int) -> str:
        return f"{ticker}|{interval}|{days}"

    def bars(self, ticker: str, interval: str = "5m", days: int = 5,
             refresh: bool = False) -> list[Bar]:
        ticker = ticker.strip().upper()
        key = self._key(ticker, interval, days)
        if self.conn is not None and not refresh:
            row = self.conn.execute(
                "SELECT fetched_at, payload FROM bar_cache WHERE key = ?", (key,)
            ).fetchone()
            if row:
                try:
                    fresh = datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
                    if fresh <= BAR_CACHE_TTL:
                        return [Bar(**b) for b in json.loads(row["payload"])]
                except ValueError:
                    pass

        bars = self.provider.bars(ticker, interval=interval, days=days)
        if bars and self.conn is not None:
            self.conn.execute(
                "INSERT INTO bar_cache (key, fetched_at, payload) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET fetched_at = excluded.fetched_at, "
                "payload = excluded.payload",
                (key, datetime.now(timezone.utc).isoformat(),
                 json.dumps([asdict(b) for b in bars])),
            )
            self.conn.commit()
        return bars


def build_bar_provider(prefer: str | None = None):
    import os

    choice = (prefer or os.environ.get("AKTIEKOLL_SOURCE") or "auto").lower()
    if choice == "demo":
        return DemoBars()
    yahoo = YahooBars()
    if choice == "yahoo":
        return yahoo
    return yahoo if yahoo.bars("AAPL", interval="5m", days=1) else DemoBars()

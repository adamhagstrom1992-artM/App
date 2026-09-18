"""Sammanstallningen som nastan alla vyer behover.

Slar ihop transaktioner, kurser och dina regler till en rad per aktie, samt
portfoljsummor - pa ett stalle, sa att dashboard, bevakning och plan visar
exakt samma siffror.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..db import get_settings, setting_float
from ..market.base import MarketData, Quote
from . import repo
from .analysis import Analysis, evaluate
from .holdings import Position, compute_positions, portfolio_totals
from .planner import Candidate


@dataclass
class Row:
    ticker: str
    name: str
    currency: str = "SEK"
    quote: Quote | None = None
    position: Position | None = None
    price_native: float | None = None
    price_base: float | None = None      # omraknad till basvaluta
    value_base: float | None = None      # marknadsvarde i basvaluta
    weight: float = 0.0
    analysis: Analysis | None = None
    watch: sqlite3.Row | None = None

    @property
    def is_held(self) -> bool:
        return bool(self.position and self.position.quantity > 0)

    @property
    def is_watched(self) -> bool:
        return self.watch is not None


@dataclass
class Overview:
    rows: list[Row] = field(default_factory=list)
    totals: dict[str, float] = field(default_factory=dict)
    settings: dict[str, str] = field(default_factory=dict)
    source: str = "demo"
    missing: list[str] = field(default_factory=list)   # tickers utan kurs

    def by_ticker(self, ticker: str) -> Row | None:
        ticker = ticker.upper()
        return next((r for r in self.rows if r.ticker == ticker), None)

    @property
    def held(self) -> list[Row]:
        return sorted([r for r in self.rows if r.is_held],
                      key=lambda r: r.value_base or 0, reverse=True)

    @property
    def watched(self) -> list[Row]:
        return sorted([r for r in self.rows if r.is_watched], key=lambda r: r.ticker)

    @property
    def buy_signals(self) -> list[Row]:
        from .analysis import BUY
        return [r for r in self.watched if r.analysis and r.analysis.verdict == BUY]


def build_overview(conn: sqlite3.Connection, md: MarketData, refresh: bool = False) -> Overview:
    settings = get_settings(conn)
    base = settings.get("base_currency", "SEK")
    min_yield = setting_float(settings, "min_dividend_yield", 0.03)
    max_pe = setting_float(settings, "max_pe", 20)
    max_pos = setting_float(settings, "max_position_pct", 0.15)

    tickers = repo.tracked_tickers(conn)
    quotes = md.quotes(tickers, refresh=refresh)
    positions = compute_positions(repo.list_transactions(conn))
    watches = {w["ticker"]: w for w in repo.list_watchlist(conn)}
    instruments = {i["ticker"]: i for i in repo.list_instruments(conn)}

    # Forsta passet: priser och marknadsvarden, sa att vikterna gar att rakna.
    rows: list[Row] = []
    missing: list[str] = []
    for ticker in tickers:
        quote = quotes.get(ticker)
        inst = instruments.get(ticker)
        currency = (quote.currency if quote else None) or (inst["currency"] if inst else base)
        name = (quote.name if quote and quote.name else None) or (inst["name"] if inst else "") or ticker
        price_native = quote.price if quote else None
        price_base = md.to_base(price_native, currency, base)
        position = positions.get(ticker)
        value = position.quantity * price_base if (position and price_base is not None) else None
        if price_native is None:
            missing.append(ticker)
        rows.append(Row(ticker=ticker, name=name, currency=currency, quote=quote,
                        position=position, price_native=price_native, price_base=price_base,
                        value_base=value, watch=watches.get(ticker)))

    total_value = sum(r.value_base or 0 for r in rows)

    # Andra passet: vikter och checklista, som bada beror av totalen.
    for row in rows:
        row.weight = (row.value_base / total_value) if (total_value and row.value_base) else 0.0
        if row.is_watched or row.is_held:
            watch = row.watch
            row.analysis = evaluate(
                row.quote,
                max_buy_price=(watch["max_buy_price"] if watch else None),
                min_yield=min_yield,
                max_pe=max_pe,
                max_position_pct=max_pos,
                current_weight=row.weight if row.is_held else None,
            )

    prices_base = {r.ticker: r.price_base for r in rows}
    totals = portfolio_totals(positions, prices_base)

    return Overview(rows=rows, totals=totals, settings=settings, source=md.source, missing=missing)


def candidates_from(overview: Overview) -> list[Candidate]:
    """Bevakade aktier med malvikt, redo for planeraren."""
    out = []
    for row in overview.watched:
        if row.price_base is None:
            continue
        out.append(Candidate(
            ticker=row.ticker,
            name=row.name,
            price=row.price_base,
            target_weight=float(row.watch["target_weight"] or 0),
            max_buy_price=row.watch["max_buy_price"],
            price_native=row.price_native,
            currency=row.currency,
        ))
    return out

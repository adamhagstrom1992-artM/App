"""Skarp marknadsdata via yfinance.

Kraver utgaende natverk mot Yahoo Finance. Gar det inte fram rapporterar
reachable() False och appen faller tillbaka pa demokallan.
"""
from __future__ import annotations

import logging

from .base import Quote

log = logging.getLogger(__name__)


def _num(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


class YahooProvider:
    name = "yahoo"

    def __init__(self) -> None:
        self._reachable: bool | None = None

    def reachable(self) -> bool:
        if self._reachable is None:
            self._reachable = self.fetch("AAPL") is not None
        return self._reachable

    def fetch(self, ticker: str) -> Quote | None:
        try:
            import yfinance as yf

            t = yf.Ticker(ticker)
            info = t.info or {}
            if not info:
                return None
            price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
            if price is None:
                fast = t.fast_info
                price = _num(fast.get("lastPrice"))
            if price is None:
                return None

            # Yahoo levererar direktavkastning ibland som procent, ibland som andel.
            raw_yield = _num(info.get("dividendYield"))
            if raw_yield is not None and raw_yield > 1:
                raw_yield = raw_yield / 100

            return Quote(
                ticker=ticker.upper(),
                name=info.get("longName") or info.get("shortName") or ticker.upper(),
                currency=(info.get("currency") or "SEK").upper(),
                price=price,
                previous_close=_num(info.get("previousClose")),
                high_52w=_num(info.get("fiftyTwoWeekHigh")),
                low_52w=_num(info.get("fiftyTwoWeekLow")),
                pe=_num(info.get("trailingPE")),
                eps=_num(info.get("trailingEps")),
                dividend_per_share=_num(info.get("dividendRate")),
                dividend_yield=raw_yield,
                payout_ratio=_num(info.get("payoutRatio")),
                market_cap=_num(info.get("marketCap")),
                sector=info.get("sector") or "",
                source=self.name,
            )
        except Exception as exc:  # natverk, rate limit, andrat API
            log.warning("Yahoo-hamtning misslyckades for %s: %s", ticker, exc)
            return None

    def fx_rate(self, base: str, quote: str) -> float | None:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return 1.0
        pair = f"{base}{quote}=X"
        try:
            import yfinance as yf

            fast = yf.Ticker(pair).fast_info
            return _num(fast.get("lastPrice"))
        except Exception as exc:
            log.warning("FX-hamtning misslyckades for %s: %s", pair, exc)
            return None

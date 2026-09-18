"""Offlinekälla med påhittade men rimliga siffror.

Används när nätet inte går fram, och i tester. Siffrorna är INTE riktiga kurser –
gränssnittet flaggar tydligt när appen kör i det här läget.
"""
from __future__ import annotations

from .base import Quote

# ticker: (namn, valuta, kurs, gårdagens kurs, 52v högsta, 52v lägsta, P/E, EPS,
#          utdelning/aktie, utdelningsandel, börsvärde, sektor)
FIXTURES: dict[str, tuple] = {
    "VOLV-B.ST": ("Volvo B", "SEK", 268.0, 271.5, 312.0, 221.0, 11.4, 23.5, 18.0, 0.62, 5.4e11, "Industri"),
    "INVE-B.ST": ("Investor B", "SEK", 282.0, 279.0, 295.0, 214.0, 7.1, 39.7, 4.6, 0.12, 8.6e11, "Investmentbolag"),
    "ERIC-B.ST": ("Ericsson B", "SEK", 78.5, 79.9, 92.0, 55.0, 16.2, 4.8, 2.7, 0.55, 2.6e11, "Teknik"),
    "HM-B.ST": ("Hennes & Mauritz B", "SEK", 148.0, 150.2, 195.0, 132.0, 19.8, 7.5, 6.5, 0.85, 2.4e11, "Sällanköp"),
    "ATCO-A.ST": ("Atlas Copco A", "SEK", 172.0, 170.4, 215.0, 148.0, 26.5, 6.5, 2.8, 0.43, 8.4e11, "Industri"),
    "SHB-A.ST": ("Handelsbanken A", "SEK", 112.0, 111.2, 126.0, 92.0, 8.2, 13.6, 7.0, 0.51, 2.2e11, "Bank"),
    "TELIA.ST": ("Telia Company", "SEK", 31.4, 31.1, 34.5, 25.8, 15.1, 2.1, 2.0, 0.95, 1.3e11, "Telekom"),
    "SAND.ST": ("Sandvik", "SEK", 218.0, 220.5, 245.0, 172.0, 18.4, 11.8, 5.5, 0.47, 2.7e11, "Industri"),
    "SKF-B.ST": ("SKF B", "SEK", 205.0, 203.0, 240.0, 168.0, 12.9, 15.9, 8.0, 0.50, 9.3e10, "Industri"),
    "CAST.ST": ("Castellum", "SEK", 132.0, 134.0, 158.0, 108.0, 14.5, 9.1, 3.0, 0.33, 6.5e10, "Fastighet"),
    "AAPL": ("Apple Inc.", "USD", 228.0, 226.4, 260.0, 164.0, 34.8, 6.55, 1.00, 0.15, 3.4e12, "Teknik"),
    "MSFT": ("Microsoft Corp.", "USD", 416.0, 419.8, 468.0, 362.0, 33.1, 12.6, 3.00, 0.24, 3.1e12, "Teknik"),
    "JNJ": ("Johnson & Johnson", "USD", 158.0, 157.2, 168.0, 140.0, 22.4, 7.05, 4.96, 0.70, 3.8e11, "Hälsovård"),
    "KO": ("Coca-Cola Co.", "USD", 68.5, 68.1, 73.5, 57.0, 25.6, 2.68, 1.94, 0.72, 2.9e11, "Dagligvaror"),
}

FX = {("USD", "SEK"): 10.45, ("EUR", "SEK"): 11.35, ("SEK", "USD"): 1 / 10.45, ("SEK", "EUR"): 1 / 11.35}


class DemoProvider:
    name = "demo"

    def fetch(self, ticker: str) -> Quote | None:
        row = FIXTURES.get(ticker.upper())
        if row is None:
            return None
        name, cur, price, prev, hi, lo, pe, eps, dps, payout, cap, sector = row
        return Quote(
            ticker=ticker.upper(),
            name=name,
            currency=cur,
            price=price,
            previous_close=prev,
            high_52w=hi,
            low_52w=lo,
            pe=pe,
            eps=eps,
            dividend_per_share=dps,
            dividend_yield=(dps / price) if price else None,
            payout_ratio=payout,
            market_cap=cap,
            sector=sector,
            source=self.name,
        )

    def fx_rate(self, base: str, quote: str) -> float | None:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return 1.0
        return FX.get((base, quote))

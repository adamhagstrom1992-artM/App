"""Checklista per aktie, mot dina egna regler.

Appen ger inga rekommendationer. Den kontrollerar en aktie mot de kriterier du
själv har ställt upp i inställningarna och på bevakningslistan, och visar vilka
som är uppfyllda. Omdömet är en sammanfattning av dina regler, inte ett råd.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..format import num as fmt_num, pct as fmt_pct
from ..market.base import Quote

BUY = "KOPVARD"
WATCH = "BEVAKA"
HOLD_OFF = "AVVAKTA"
UNKNOWN = "OKAND"

VERDICT_LABEL = {
    BUY: "Köpvärd",
    WATCH: "Bevaka",
    HOLD_OFF: "Avvakta",
    UNKNOWN: "Okänd",
}


@dataclass
class Check:
    label: str
    ok: bool | None          # None = uppgiften saknas
    detail: str
    blocking: bool = False   # ett ouppfyllt blockerande krav stoppar köp


@dataclass
class Analysis:
    ticker: str
    verdict: str = UNKNOWN
    checks: list[Check] = field(default_factory=list)
    fair_value: float | None = None       # vad din egen P/E-gräns motsvarar i kronor
    upside_to_limit: float | None = None  # hur långt kursen har kvar till din gräns

    @property
    def verdict_label(self) -> str:
        return VERDICT_LABEL.get(self.verdict, self.verdict)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def relevant(self) -> int:
        return sum(1 for c in self.checks if c.ok is not None)


def evaluate(
    quote: Quote | None,
    *,
    max_buy_price: float | None = None,
    min_yield: float = 0.03,
    max_pe: float = 20.0,
    max_position_pct: float = 0.15,
    current_weight: float | None = None,
) -> Analysis:
    a = Analysis(ticker=quote.ticker if quote else "?")
    if quote is None or quote.price is None:
        a.checks.append(Check("Kursdata", None, "Ingen kurs hittad för tickern.", blocking=True))
        return a

    price = quote.price

    # 1. Din egen köpgräns – det enda kravet du sätter per aktie.
    if max_buy_price:
        under = price <= max_buy_price
        a.upside_to_limit = (max_buy_price - price) / price
        a.checks.append(Check(
            "Under din köpgräns",
            under,
            f"Kurs {fmt_num(price)} mot gräns {fmt_num(max_buy_price)} "
            f"({'under' if under else 'över'} med {fmt_num(abs(price - max_buy_price))})",
            blocking=True,
        ))
    else:
        a.checks.append(Check("Under din köpgräns", None, "Ingen köpgräns satt.", blocking=False))

    # 2. Direktavkastning.
    dy = quote.dividend_yield
    a.checks.append(Check(
        "Direktavkastning",
        None if dy is None else dy >= min_yield,
        f"{fmt_pct(dy)} mot ditt krav {fmt_pct(min_yield)}",
    ))

    # 3. Värdering.
    a.checks.append(Check(
        "P/E-tal",
        None if quote.pe is None else quote.pe <= max_pe,
        f"{fmt_num(quote.pe, 1)} mot ditt tak {fmt_num(max_pe, 0)}" if quote.pe is not None else "Saknas",
    ))

    # 4. Hållbarhet i utdelningen.
    payout = quote.payout_ratio
    a.checks.append(Check(
        "Utdelningsandel",
        None if payout is None else payout <= 0.8,
        f"{fmt_pct(payout)} av vinsten delas ut" if payout is not None else "Saknas",
    ))

    # 5. Var i årsspannet kursen står – ren information, inget krav.
    pos = quote.pos_in_52w_range
    a.checks.append(Check(
        "Läge i 52-veckorsspann",
        None,
        f"{fmt_pct(pos)} upp från årslägsta "
        f"({fmt_num(quote.low_52w)}–{fmt_num(quote.high_52w)})" if pos is not None else "Saknas",
    ))

    # 6. Koncentrationsrisk – blockerar påfyllning i en redan för stor post.
    if current_weight is not None:
        room = current_weight < max_position_pct
        a.checks.append(Check(
            "Utrymme i portföljen",
            room,
            f"Posten är {fmt_pct(current_weight)} av portföljen, ditt tak är {fmt_pct(max_position_pct)}",
            blocking=True,
        ))

    if quote.eps and quote.eps > 0:
        a.fair_value = max_pe * quote.eps

    blocked = any(c.blocking and c.ok is False for c in a.checks)
    quality = [c.ok for c in a.checks if not c.blocking and c.ok is not None]
    if blocked:
        a.verdict = HOLD_OFF
    elif quality and all(quality):
        a.verdict = BUY
    elif not quality:
        a.verdict = UNKNOWN
    else:
        a.verdict = WATCH
    return a

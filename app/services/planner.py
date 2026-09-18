"""Från månadsbudget till konkret orderunderlag.

Planeraren svarar på den fråga som faktiskt är svår när man ska köpa: givet att
jag har X kronor, vilka av mina bevakade aktier ligger längst under sin önskade
andel – och hur många hela aktier räcker pengarna till efter courtage?
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..format import num as fmt_num, pct as fmt_pct


@dataclass
class Candidate:
    ticker: str
    name: str
    price: float                       # i basvalutan (SEK)
    target_weight: float               # önskad andel av portföljen, 0–1
    max_buy_price: float | None = None  # din köpgräns, i instrumentets egen valuta
    price_native: float | None = None   # kurs i instrumentets egen valuta
    currency: str = "SEK"


@dataclass
class Order:
    ticker: str
    name: str
    shares: int
    price: float
    amount: float
    courtage: float
    weight_before: float
    weight_after: float

    @property
    def total(self) -> float:
        return self.amount + self.courtage

    @property
    def courtage_pct(self) -> float:
        return self.courtage / self.amount if self.amount else 0.0


@dataclass
class Plan:
    orders: list[Order] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)   # (ticker, skäl)
    budget: float = 0.0
    spent: float = 0.0

    @property
    def leftover(self) -> float:
        return self.budget - self.spent

    @property
    def total_courtage(self) -> float:
        return sum(o.courtage for o in self.orders)


def courtage_for(amount: float, minimum: float, pct: float) -> float:
    return max(minimum, amount * pct)


def build_plan(
    budget: float,
    candidates: list[Candidate],
    current_values: dict[str, float],
    *,
    courtage_min: float = 1.0,
    courtage_pct: float = 0.0025,
    max_courtage_pct_of_order: float = 0.005,
    max_position_pct: float = 0.15,
) -> Plan:
    plan = Plan(budget=budget)
    if budget <= 0 or not candidates:
        return plan

    portfolio_value = sum(current_values.values())
    total_after = portfolio_value + budget

    gaps: list[tuple[float, Candidate, float]] = []
    for c in candidates:
        if c.price is None or c.price <= 0:
            plan.skipped.append((c.ticker, "Ingen kurs tillgänglig."))
            continue
        if c.target_weight <= 0:
            plan.skipped.append((c.ticker, "Ingen önskad portföljandel angiven."))
            continue
        native = c.price_native if c.price_native is not None else c.price
        if c.max_buy_price and native > c.max_buy_price:
            plan.skipped.append((
                c.ticker,
                f"Kursen {fmt_num(native)} ligger över din gräns {fmt_num(c.max_buy_price)}.",
            ))
            continue

        held = current_values.get(c.ticker, 0.0)
        target_weight = min(c.target_weight, max_position_pct)
        gap = target_weight * total_after - held
        if gap <= 0:
            plan.skipped.append((
                c.ticker,
                f"Redan på eller över sin målvikt ({fmt_pct(held / total_after)})."
                if total_after else "Redan på målvikt.",
            ))
            continue
        gaps.append((gap, c, held))

    # Störst underskott först – det är där pengarna gör mest för balansen.
    gaps.sort(key=lambda g: g[0], reverse=True)

    remaining = budget
    for gap, c, held in gaps:
        allocation = min(gap, remaining)
        shares = int(math.floor(allocation / c.price))

        # Krymp ordern tills den ryms i budgeten, courtaget inräknat.
        while shares >= 1:
            amount = shares * c.price
            fee = courtage_for(amount, courtage_min, courtage_pct)
            if amount + fee <= remaining + 1e-9:
                break
            shares -= 1

        if shares < 1:
            plan.skipped.append((
                c.ticker,
                f"Budgeten räcker inte till en hel aktie ({fmt_num(c.price)} kr styck).",
            ))
            continue

        amount = shares * c.price
        fee = courtage_for(amount, courtage_min, courtage_pct)
        if amount and fee / amount > max_courtage_pct_of_order:
            plan.skipped.append((
                c.ticker,
                f"Courtaget hade ätit {fmt_pct(fee / amount, 2)} av ordern – handla för ett större belopp.",
            ))
            continue

        plan.orders.append(Order(
            ticker=c.ticker,
            name=c.name,
            shares=shares,
            price=c.price,
            amount=amount,
            courtage=fee,
            weight_before=(held / total_after) if total_after else 0.0,
            weight_after=((held + amount) / total_after) if total_after else 0.0,
        ))
        remaining -= amount + fee
        plan.spent += amount + fee

    return plan

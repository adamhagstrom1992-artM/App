"""Innehav räknade ur transaktionshistoriken enligt genomsnittsmetoden.

Detta är appens kärna. Genomsnittsmetoden innebär att varje köp räknas in i ett
viktat genomsnittligt omkostnadsbelopp (GAV), och att en försäljning inte rubbar
GAV utan bara minskar antalet aktier.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Transaction:
    ticker: str
    kind: str          # BUY | SELL | DIVIDEND | SPLIT
    trade_date: str    # ISO-datum, styr ordningen
    quantity: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    id: int | None = None
    note: str = ""


@dataclass
class Position:
    ticker: str
    quantity: float = 0.0
    cost_basis: float = 0.0      # samlat omkostnadsbelopp för kvarvarande aktier
    realized_pl: float = 0.0     # realiserat resultat, efter courtage
    dividends: float = 0.0       # mottagna utdelningar, efter avgifter
    fees: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def avg_cost(self) -> float:
        """GAV – genomsnittligt omkostnadsbelopp per aktie."""
        return self.cost_basis / self.quantity if self.quantity else 0.0

    def market_value(self, price: float | None) -> float | None:
        return None if price is None else self.quantity * price

    def unrealized_pl(self, price: float | None) -> float | None:
        mv = self.market_value(price)
        return None if mv is None else mv - self.cost_basis

    def unrealized_pct(self, price: float | None) -> float | None:
        pl = self.unrealized_pl(price)
        return None if pl is None or not self.cost_basis else pl / self.cost_basis

    def yield_on_cost(self, dividend_per_share: float | None) -> float | None:
        """Direktavkastning räknad på vad du betalade, inte på dagens kurs."""
        if not dividend_per_share or not self.avg_cost:
            return None
        return dividend_per_share / self.avg_cost


def _sort_key(t: Transaction) -> tuple:
    return (t.trade_date, t.id if t.id is not None else 0)


def compute_positions(transactions: list[Transaction]) -> dict[str, Position]:
    """Spelar upp alla transaktioner i datumordning och returnerar innehaven."""
    positions: dict[str, Position] = {}

    for txn in sorted(transactions, key=_sort_key):
        pos = positions.setdefault(txn.ticker, Position(ticker=txn.ticker))
        kind = txn.kind.upper()

        if kind == "BUY":
            pos.cost_basis += txn.quantity * txn.price + txn.fee
            pos.quantity += txn.quantity
            pos.fees += txn.fee

        elif kind == "SELL":
            qty = txn.quantity
            if qty > pos.quantity:
                pos.warnings.append(
                    f"Försäljning {qty:g} st {txn.trade_date} överstiger innehavet "
                    f"{pos.quantity:g} st – justerad nedåt."
                )
                qty = pos.quantity
            if qty <= 0:
                continue
            gav = pos.avg_cost
            proceeds = qty * txn.price - txn.fee
            pos.realized_pl += proceeds - qty * gav
            pos.cost_basis -= qty * gav
            pos.quantity -= qty
            pos.fees += txn.fee
            if pos.quantity <= 1e-9:      # allt sålt – städa bort avrundningsrester
                pos.quantity = 0.0
                pos.cost_basis = 0.0

        elif kind == "DIVIDEND":
            # quantity = antal aktier som fick utdelning; 0 betyder "hela innehavet"
            shares = txn.quantity if txn.quantity > 0 else pos.quantity
            pos.dividends += shares * txn.price - txn.fee
            pos.fees += txn.fee

        elif kind == "SPLIT":
            ratio = txn.quantity
            if ratio <= 0:
                pos.warnings.append(f"Ogiltig splitkvot {ratio:g} den {txn.trade_date} – ignorerad.")
                continue
            # Omkostnadsbeloppet är oförändrat, det fördelas på fler (eller färre) aktier.
            pos.quantity *= ratio

    return positions


def portfolio_totals(
    positions: dict[str, Position],
    prices: dict[str, float | None],
) -> dict[str, float]:
    """Summerar portföljen. Priserna ska redan vara omräknade till basvalutan."""
    cost = value = 0.0
    realized = dividends = 0.0
    priced_cost = 0.0
    for ticker, pos in positions.items():
        realized += pos.realized_pl
        dividends += pos.dividends
        if pos.quantity <= 0:
            continue
        cost += pos.cost_basis
        price = prices.get(ticker)
        if price is not None:
            value += pos.quantity * price
            priced_cost += pos.cost_basis
    unrealized = value - priced_cost
    return {
        "cost_basis": cost,
        "market_value": value,
        "unrealized_pl": unrealized,
        "unrealized_pct": (unrealized / priced_cost) if priced_cost else 0.0,
        "realized_pl": realized,
        "dividends": dividends,
        "total_return": unrealized + realized + dividends,
    }

"""Positionsstorlek utifrån risk, inte utifrån magkänsla.

Den enda fråga som verkligen avgör om ett handelskonto överlever är hur mycket
en enskild affär får kosta. Antalet aktier är då inte ett val utan ett resultat:
kontostorlek × risk per affär, delat med avståndet till stoppen.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

LONG = "LONG"
SHORT = "SHORT"


@dataclass
class TradePlan:
    direction: str = LONG
    entry: float = 0.0
    stop: float = 0.0
    shares: int = 0
    risk_per_share: float = 0.0
    risk_budget: float = 0.0        # vad du tillåtit affären att kosta
    risk_actual: float = 0.0        # vad den faktiskt kostar, courtage inräknat
    position_value: float = 0.0
    fees: float = 0.0
    capped_by_position_limit: bool = False
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers and self.shares > 0

    @property
    def position_pct(self) -> float | None:
        return None

    def target(self, r: float) -> float:
        """Kursen där affären gett r gånger den risk du tog."""
        move = self.risk_per_share * r
        return self.entry + move if self.direction == LONG else self.entry - move

    @property
    def breakeven(self) -> float:
        """Kursen där courtaget är intjänat och affären går jämnt ut."""
        if not self.shares:
            return self.entry
        per_share = self.fees / self.shares
        return self.entry + per_share if self.direction == LONG else self.entry - per_share


def courtage_for(amount: float, minimum: float, pct: float) -> float:
    return max(minimum, amount * pct)


def r_multiple(entry: float, stop: float, exit_price: float, direction: str = LONG) -> float | None:
    """Resultatet mätt i den risk du tog. +2R = du tjänade två gånger risken.

    R är det enda måttet som gör två olika stora affärer jämförbara, och därför
    det enda som är meningsfullt att bygga statistik på.
    """
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    move = (exit_price - entry) if direction == LONG else (entry - exit_price)
    return move / risk


def plan_trade(
    *,
    account_size: float,
    risk_pct: float,
    entry: float,
    stop: float,
    direction: str = LONG,
    courtage_min: float = 1.0,
    courtage_pct: float = 0.0025,
    max_position_pct: float = 1.0,
    atr: float | None = None,
) -> TradePlan:
    plan = TradePlan(direction=direction, entry=entry, stop=stop)

    if entry <= 0:
        plan.blockers.append("Ingångskursen måste vara större än noll.")
        return plan
    if stop <= 0:
        plan.blockers.append("Stoppen måste vara större än noll.")
        return plan
    if direction == LONG and stop >= entry:
        plan.blockers.append("I en lång affär måste stoppen ligga under ingången.")
        return plan
    if direction == SHORT and stop <= entry:
        plan.blockers.append("I en kort affär måste stoppen ligga över ingången.")
        return plan
    if account_size <= 0 or risk_pct <= 0:
        plan.blockers.append("Kontostorlek och risk per affär måste vara större än noll.")
        return plan

    plan.risk_per_share = abs(entry - stop)
    plan.risk_budget = account_size * risk_pct

    shares = int(math.floor(plan.risk_budget / plan.risk_per_share))

    # Riskregeln kan tillåta en position som är orimligt stor i sig själv –
    # en mycket tät stopp ger ett enormt antal aktier. Taket bryter det.
    max_value = account_size * max_position_pct
    if shares * entry > max_value:
        shares = int(math.floor(max_value / entry))
        plan.capped_by_position_limit = True

    if shares < 1:
        plan.blockers.append(
            "Risken räcker inte till en hel aktie. Höj risken per affär, "
            "flytta stoppen längre bort eller välj en billigare aktie."
        )
        return plan

    plan.shares = shares
    plan.position_value = shares * entry
    plan.fees = courtage_for(plan.position_value, courtage_min, courtage_pct) * 2  # in och ut
    plan.risk_actual = shares * plan.risk_per_share + plan.fees

    if plan.capped_by_position_limit:
        plan.warnings.append(
            "Antalet är nedkapat av ditt tak för positionsstorlek, så affären "
            "riskerar mindre än din riskregel tillåter."
        )
    if plan.risk_actual > plan.risk_budget * 1.25:
        plan.warnings.append(
            "Courtaget gör att affären riskerar betydligt mer än din riskregel. "
            "Handla för ett större belopp eller acceptera den högre risken medvetet."
        )
    if atr and plan.risk_per_share < atr * 0.5:
        plan.warnings.append(
            "Stoppen ligger närmare än halva ATR. Den träffas sannolikt av "
            "marknadens normala brus, inte av att du hade fel."
        )
    if atr and plan.risk_per_share > atr * 4:
        plan.warnings.append(
            "Stoppen ligger mer än fyra ATR bort. Det ger få aktier och en "
            "vinst som måste bli mycket stor för att väga upp förlusterna."
        )
    return plan

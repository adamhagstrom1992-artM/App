"""Handelsjournal och statistiken som gör den användbar.

En journal är inte bokföring, den är diagnos. Poängen är att kunna se att en
uppställning tjänar pengar och tre andra förlorar dem – vilket är omöjligt att
minnas rätt, och trivialt att räkna fram.

Allt mäts i R, alltså i den risk affären tog, eftersom det är det enda som gör
en affär på 500 kr jämförbar med en på 5 000 kr.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from .risk import LONG, r_multiple

WEEKDAYS = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]


@dataclass
class Trade:
    ticker: str
    direction: str
    entry: float
    stop: float
    quantity: float
    opened_at: str
    closed_at: str | None = None
    exit: float | None = None
    setup: str = ""
    fees: float = 0.0
    note: str = ""
    id: int | None = None

    @property
    def is_open(self) -> bool:
        return self.exit is None or self.closed_at is None

    @property
    def risk_amount(self) -> float:
        """Vad affären var tänkt att kosta om stoppen träffades."""
        return abs(self.entry - self.stop) * self.quantity

    @property
    def gross_pl(self) -> float | None:
        if self.exit is None:
            return None
        move = (self.exit - self.entry) if self.direction == LONG else (self.entry - self.exit)
        return move * self.quantity

    @property
    def pl(self) -> float | None:
        """Resultat efter courtage – det som faktiskt landar på kontot."""
        gross = self.gross_pl
        return None if gross is None else gross - self.fees

    @property
    def r(self) -> float | None:
        """Resultatet i R, räknat på kurserna. Avgifterna syns i kronorna."""
        if self.exit is None:
            return None
        return r_multiple(self.entry, self.stop, self.exit, self.direction)

    @property
    def is_win(self) -> bool:
        pl = self.pl
        return pl is not None and pl > 0

    @property
    def is_loss(self) -> bool:
        pl = self.pl
        return pl is not None and pl < 0

    @property
    def opened_date(self) -> date | None:
        return _parse_date(self.opened_at)

    @property
    def weekday(self) -> str | None:
        d = self.opened_date
        return WEEKDAYS[d.weekday()] if d else None

    @property
    def hour(self) -> int | None:
        dt = _parse_dt(self.opened_at)
        return dt.hour if dt else None

    @property
    def held_minutes(self) -> float | None:
        start, end = _parse_dt(self.opened_at), _parse_dt(self.closed_at or "")
        if start is None or end is None:
            return None
        return max(0.0, (end - start).total_seconds() / 60)


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    for text in (value, value.replace(" ", "T")):
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_date(value: str) -> date | None:
    dt = _parse_dt(value)
    return dt.date() if dt else None


@dataclass
class Stats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    scratches: int = 0            # gick jämnt ut
    total_pl: float = 0.0
    total_fees: float = 0.0
    gross_win: float = 0.0
    gross_loss: float = 0.0       # positivt tal
    sum_r: float = 0.0
    best_r: float | None = None
    worst_r: float | None = None
    max_drawdown: float = 0.0
    longest_win_streak: int = 0
    longest_loss_streak: int = 0
    equity: list[tuple[str, float]] = field(default_factory=list)
    r_values: list[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float | None:
        decided = self.wins + self.losses
        return self.wins / decided if decided else None

    @property
    def expectancy_r(self) -> float | None:
        """Genomsnittligt utfall i R. Under noll ar strategin forlustbringande.

        Avrundas till tva decimaler: summan av +2R, -1R och -1R blir 4e-15 i
        flyttal, och en "expectancy" pa 0,000000000000004R ar inte en uppgift.
        """
        if not self.r_values:
            return None
        return round(self.sum_r / len(self.r_values), 4)

    @property
    def avg_win(self) -> float | None:
        return self.gross_win / self.wins if self.wins else None

    @property
    def avg_loss(self) -> float | None:
        return self.gross_loss / self.losses if self.losses else None

    @property
    def profit_factor(self) -> float | None:
        """Vunna kronor delat med förlorade. Under 1,0 betyder att du betalar
        för att få handla."""
        if self.gross_loss > 0:
            return self.gross_win / self.gross_loss
        return None if self.gross_win == 0 else float("inf")

    @property
    def payoff_ratio(self) -> float | None:
        """Snittvinst delat med snittförlust – halva bilden; träffsäkerheten
        är den andra."""
        aw, al = self.avg_win, self.avg_loss
        return aw / al if aw and al else None


def summarize(trades: list[Trade]) -> Stats:
    """Räkna statistik på avslutade affärer. Öppna affärer hoppas över."""
    closed = sorted([t for t in trades if not t.is_open],
                    key=lambda t: (t.closed_at or "", t.id or 0))
    s = Stats(trades=len(closed))

    equity = 0.0
    peak = 0.0
    win_streak = loss_streak = 0
    for t in closed:
        pl = t.pl or 0.0
        s.total_pl += pl
        s.total_fees += t.fees
        if pl > 0:
            s.wins += 1
            s.gross_win += pl
            win_streak += 1
            loss_streak = 0
        elif pl < 0:
            s.losses += 1
            s.gross_loss += -pl
            loss_streak += 1
            win_streak = 0
        else:
            s.scratches += 1
            win_streak = loss_streak = 0
        s.longest_win_streak = max(s.longest_win_streak, win_streak)
        s.longest_loss_streak = max(s.longest_loss_streak, loss_streak)

        r = t.r
        if r is not None:
            s.r_values.append(r)
            s.sum_r += r
            s.best_r = r if s.best_r is None else max(s.best_r, r)
            s.worst_r = r if s.worst_r is None else min(s.worst_r, r)

        equity += pl
        peak = max(peak, equity)
        s.max_drawdown = max(s.max_drawdown, peak - equity)
        s.equity.append((t.closed_at or t.opened_at, equity))

    return s


def group_stats(trades: list[Trade], key) -> list[tuple[str, Stats]]:
    """Samma statistik, uppdelad på setup, veckodag eller vad du nu vill se.

    Sorteras efter summa R, så att det som drar ned resultatet hamnar sist och
    inte går att missa.
    """
    buckets: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        if t.is_open:
            continue
        label = key(t)
        buckets[str(label) if label is not None else "–"].append(t)
    out = [(label, summarize(group)) for label, group in buckets.items()]
    out.sort(key=lambda pair: pair[1].sum_r, reverse=True)
    return out


def r_histogram(r_values: list[float], edges: tuple[float, ...] = (-2, -1, 0, 1, 2, 3)) -> list[tuple[str, int]]:
    """Fördelning av utfall i R. Formen säger mer än medelvärdet: många små
    förluster och få stora vinster är en helt annan strategi än tvärtom."""
    if not r_values:
        return []
    labels = [f"< {edges[0]:g}"]
    counts = [0] * (len(edges) + 1)
    for i in range(len(edges) - 1):
        # "…" istallet for bindestreck: "-2–-1" gar inte att lasa.
        labels.append(f"{edges[i]:g}…{edges[i + 1]:g}")
    labels.append(f"> {edges[-1]:g}")

    for r in r_values:
        if r < edges[0]:
            counts[0] += 1
        elif r >= edges[-1]:
            counts[-1] += 1
        else:
            for i in range(len(edges) - 1):
                if edges[i] <= r < edges[i + 1]:
                    counts[i + 1] += 1
                    break
    return list(zip(labels, counts))

"""Tekniska indikatorer.

Alla funktioner returnerar en lista lika lång som inmatningen, med None under
uppvärmningsperioden. Det gör att en indikator alltid kan ritas rakt mot samma
x-axel som staplarna, utan att man behöver hålla reda på någon förskjutning.
"""
from __future__ import annotations

from ..market.intraday import Bar

Series = list[float | None]


def sma(values: list[float], period: int) -> Series:
    """Enkelt glidande medelvärde."""
    if period < 1:
        raise ValueError("perioden måste vara minst 1")
    out: Series = [None] * len(values)
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= period:
            total -= values[i - period]
        if i >= period - 1:
            out[i] = total / period
    return out


def ema(values: list[float], period: int) -> Series:
    """Exponentiellt glidande medelvärde, seedat med SMA över första perioden."""
    if period < 1:
        raise ValueError("perioden måste vara minst 1")
    out: Series = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def vwap(bars: list[Bar]) -> Series:
    """Volymviktad snittkurs, nollställd vid varje ny handelsdag.

    VWAP är ett dagsmått – att låta det löpa över flera dagar gör det
    meningslöst, därför nollställningen.
    """
    out: Series = []
    day = None
    cum_pv = cum_v = 0.0
    for bar in bars:
        bar_day = bar.ts[:10]
        if bar_day != day:
            day, cum_pv, cum_v = bar_day, 0.0, 0.0
        cum_pv += bar.typical * bar.volume
        cum_v += bar.volume
        out.append(cum_pv / cum_v if cum_v else bar.typical)
    return out


def rsi(values: list[float], period: int = 14) -> Series:
    """Relative Strength Index enligt Wilders utjämning."""
    out: Series = [None] * len(values)
    if len(values) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def true_range(bars: list[Bar]) -> list[float]:
    out: list[float] = []
    for i, bar in enumerate(bars):
        if i == 0:
            out.append(bar.high - bar.low)
            continue
        prev_close = bars[i - 1].close
        out.append(max(bar.high - bar.low,
                       abs(bar.high - prev_close),
                       abs(bar.low - prev_close)))
    return out


def atr(bars: list[Bar], period: int = 14) -> Series:
    """Average True Range – hur mycket aktien typiskt rör sig per stapel.

    Används framför allt för att sätta stoppen på ett avstånd som marknadens
    normala brus inte råkar träffa.
    """
    tr = true_range(bars)
    out: Series = [None] * len(bars)
    if len(tr) < period:
        return out
    prev = sum(tr[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(tr)):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def opening_range(bars: list[Bar], minutes: int = 15,
                  interval_minutes: int = 5) -> tuple[float, float] | None:
    """Högsta och lägsta under dagens första minuter.

    Genombrott ur öppningsrangen är en av de vanligaste intradagsuppställningarna,
    och rangen är också ett rimligt ställe att lägga stoppen bakom.
    """
    if not bars:
        return None
    last_day = bars[-1].ts[:10]
    todays = [b for b in bars if b.ts[:10] == last_day]
    count = max(1, minutes // max(1, interval_minutes))
    window = todays[:count]
    if not window:
        return None
    return (max(b.high for b in window), min(b.low for b in window))


def latest(series: Series) -> float | None:
    """Sista värde som inte är None – det är nästan alltid det man vill visa."""
    for value in reversed(series):
        if value is not None:
            return value
    return None

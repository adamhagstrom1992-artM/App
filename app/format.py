"""Svensk sifferformatering, pa ett stalle.

Bade tjansterna och mallarna formaterar tal, och gor de det var for sig blir det
punkt pa ett stalle och komma pa ett annat. Darfor bor allt ga genom de har.
"""
from __future__ import annotations

NBSP = " "
DASH = "–"


def num(value, decimals: int = 2) -> str:
    """1234.5 -> '1 234,50'. Tusentalsavgransare ar hart mellanslag."""
    if value is None:
        return DASH
    try:
        s = f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return DASH
    return s.replace(",", NBSP).replace(".", ",")


def kr(value, decimals: int = 0) -> str:
    return DASH if value is None else f"{num(value, decimals)}{NBSP}kr"


def pct(value, decimals: int = 1) -> str:
    """Tar en andel (0.065) och skriver den som procent ('6,5 %')."""
    return DASH if value is None else f"{num(float(value) * 100, decimals)}{NBSP}%"


def signed_pct(value, decimals: int = 1) -> str:
    if value is None:
        return DASH
    return f"{'+' if value >= 0 else ''}{pct(value, decimals)}"


def cap(value) -> str:
    """Borsvarde i lasbar storlek: 5.4e11 -> '540,0 mdr'."""
    if value is None:
        return DASH
    for limit, suffix in ((1e12, "bn"), (1e9, "mdr"), (1e6, "mn")):
        if abs(value) >= limit:
            return f"{num(value / limit, 1)}{NBSP}{suffix}"
    return num(value, 0)

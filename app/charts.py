"""Grafer som ren SVG, byggda pa servern.

Inget byggsteg och inga externa bibliotek: graferna ar strangar som mallarna
skriver ut direkt. Hovringen ligger i app.js och laser geometrin ur
data-attributen som funktionerna har satter.

Fargval: upp/ned bars av bade farg OCH form - ihaliga staplar upp, fyllda ned.
Gront mot rott ar praktiskt taget omojligt att skilja at vid deuteranopi
(uppmatt skillnad langt under gransvardet), sa formen far bara meningen.
"""
from __future__ import annotations

import html
import json
import math
from dataclasses import dataclass

from .market.intraday import Bar

# Roller, inte rahex, sa att temat byts pa ett stalle (se app.css).
UP = "var(--chart-up)"
DOWN = "var(--chart-down)"
SERIES = ["var(--chart-s1)", "var(--chart-s2)", "var(--chart-s3)"]
GRID = "var(--chart-grid)"
AXIS = "var(--chart-axis)"
INK_MUTED = "var(--chart-ink-muted)"
SURFACE = "var(--chart-surface)"


@dataclass
class Box:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


def nice_ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    """Jamna axelvarden. Rada tal ur datat ger ticks som 103,47 - oanvandbart."""
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / max(1, count)
    magnitude = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        step = magnitude * mult
        if raw <= step:
            break
    start = math.ceil(lo / step) * step
    ticks, value = [], start
    while value <= hi + step * 0.01:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _fmt(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _path(points: list[tuple[float, float] | None]) -> str:
    """Bygger en path dar None bryter linjen istallet for att dra den genom hal."""
    parts: list[str] = []
    pen_down = False
    for point in points:
        if point is None:
            pen_down = False
            continue
        cmd = "L" if pen_down else "M"
        parts.append(f"{cmd}{point[0]:.1f} {point[1]:.1f}")
        pen_down = True
    return " ".join(parts)


def candlestick(
    bars: list[Bar],
    overlays: dict[str, list[float | None]] | None = None,
    levels: dict[str, float] | None = None,
    band: tuple[str, float, float] | None = None,
    width: int = 940,
    height: int = 380,
    decimals: int = 2,
) -> str:
    """Intradagsgraf med valfria overlager (VWAP, EMA), nivaer och ett band.

    Ett band ritas for en zon som hor ihop - oppningsrangen ar en foreteelse,
    inte tva oberoende linjer, och far darfor en etikett istallet for tva.
    """
    if not bars:
        return '<p class="empty">Inga staplar att visa.</p>'

    overlays = overlays or {}
    levels = levels or {}
    vol_h = 54
    gap = 14
    plot = Box(56, 12, width - 68, height - 34 - vol_h - gap)
    vol = Box(plot.left, plot.bottom + gap, plot.width, vol_h)

    lo = min(b.low for b in bars)
    hi = max(b.high for b in bars)
    for series in overlays.values():
        values = [v for v in series if v is not None]
        if values:
            lo, hi = min(lo, min(values)), max(hi, max(values))
    for value in levels.values():
        lo, hi = min(lo, value), max(hi, value)
    if band:
        lo, hi = min(lo, band[1]), max(hi, band[2])
    pad = (hi - lo) * 0.06 or 1.0
    lo, hi = lo - pad, hi + pad

    def y(value: float) -> float:
        return plot.bottom - (value - lo) / (hi - lo) * plot.height

    step = plot.width / len(bars)
    body = max(1.0, min(11.0, step * 0.62))

    def x(i: int) -> float:
        return plot.left + step * (i + 0.5)

    out: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" class="chart chart-candles" preserveAspectRatio="none">'
    ]

    # Rutnat och vardeaxel - hårfina och tillbakadragna, de ar inte data.
    for tick in nice_ticks(lo, hi):
        ty = y(tick)
        out.append(f'<line x1="{plot.left}" y1="{ty:.1f}" x2="{plot.right}" y2="{ty:.1f}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{plot.left - 8}" y="{ty + 4:.1f}" text-anchor="end" '
                   f'class="chart-tick">{_fmt(tick, decimals)}</text>')

    # Dagsbyten - i en flerdagsgraf ar det den viktigaste orienteringspunkten.
    for i in range(1, len(bars)):
        if bars[i].ts[:10] != bars[i - 1].ts[:10]:
            dx = plot.left + step * i
            out.append(f'<line x1="{dx:.1f}" y1="{plot.top}" x2="{dx:.1f}" y2="{vol.bottom}" '
                       f'stroke="{AXIS}" stroke-width="1"/>')
            out.append(f'<text x="{dx + 4:.1f}" y="{plot.top + 10}" class="chart-tick">'
                       f'{_esc(bars[i].ts[5:10])}</text>')

    # Staplarna. Ihalig = upp, fylld = ned; formen bar riktningen, inte bara fargen.
    for i, bar in enumerate(bars):
        cx = x(i)
        color = UP if bar.is_up else DOWN
        out.append(f'<line x1="{cx:.1f}" y1="{y(bar.high):.1f}" x2="{cx:.1f}" '
                   f'y2="{y(bar.low):.1f}" stroke="{color}" stroke-width="1"/>')
        top, bottom = y(max(bar.open, bar.close)), y(min(bar.open, bar.close))
        h = max(1.0, bottom - top)
        if bar.is_up:
            out.append(f'<rect x="{cx - body / 2:.1f}" y="{top:.1f}" width="{body:.1f}" '
                       f'height="{h:.1f}" fill="{SURFACE}" stroke="{color}" stroke-width="1"/>')
        else:
            out.append(f'<rect x="{cx - body / 2:.1f}" y="{top:.1f}" width="{body:.1f}" '
                       f'height="{h:.1f}" fill="{color}"/>')

    # Overlager: 2 px linjer, i serieordning.
    for idx, (label, series) in enumerate(overlays.items()):
        points = [None if v is None else (x(i), y(v)) for i, v in enumerate(series)]
        out.append(f'<path d="{_path(points)}" fill="none" stroke="{SERIES[idx % len(SERIES)]}" '
                   f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')

    # Zonen ritas som ett band med en enda etikett.
    if band:
        blabel, blow, bhigh = band
        top_y, bottom_y = y(bhigh), y(blow)
        out.append(f'<rect x="{plot.left}" y="{top_y:.1f}" width="{plot.width:.1f}" '
                   f'height="{max(1.0, bottom_y - top_y):.1f}" fill="{INK_MUTED}" opacity="0.10"/>')
        for edge in (top_y, bottom_y):
            out.append(f'<line x1="{plot.left}" y1="{edge:.1f}" x2="{plot.right}" '
                       f'y2="{edge:.1f}" stroke="{INK_MUTED}" stroke-width="1" '
                       f'stroke-dasharray="4 4"/>')
        text = f"{blabel} {_fmt(blow, decimals)}–{_fmt(bhigh, decimals)}"
        tw = len(text) * 6.1 + 10
        out.append(f'<rect x="{plot.left + 6:.1f}" y="{top_y - 17:.1f}" width="{tw:.1f}" '
                   f'height="15" rx="3" fill="{SURFACE}"/>')
        out.append(f'<text x="{plot.left + 11:.1f}" y="{top_y - 6:.1f}" '
                   f'class="chart-tick">{_esc(text)}</text>')

    # Egna nivaer (stopp, ingang) - streckade for att skilja dem
    # fran raknade serier, med etiketten direkt pa linjen.
    #
    # Ligger tva nivaer nara varandra hamnar etiketterna ovanpa varandra, sa de
    # knuffas isar: en etikett som inte gar att lasa ar samre an ingen alls.
    placed: list[float] = []
    for label, value in sorted(levels.items(), key=lambda kv: -kv[1]):
        ly = y(value)
        out.append(f'<line x1="{plot.left}" y1="{ly:.1f}" x2="{plot.right}" y2="{ly:.1f}" '
                   f'stroke="{INK_MUTED}" stroke-width="1" stroke-dasharray="4 4"/>')
        ty = ly - 5
        while any(abs(ty - used) < 15 for used in placed):
            ty += 15
        placed.append(ty)
        text = f"{label} {_fmt(value, decimals)}"
        # Platta i ytans farg under texten - annars laser den streckade linjen
        # rakt genom bokstaverna. Bredden ar uppskattad ur teckenantalet.
        tw = len(text) * 6.1 + 8
        out.append(f'<rect x="{plot.right - 4 - tw:.1f}" y="{ty - 11:.1f}" '
                   f'width="{tw:.1f}" height="15" rx="3" fill="{SURFACE}"/>')
        out.append(f'<text x="{plot.right - 8}" y="{ty:.1f}" text-anchor="end" '
                   f'class="chart-tick">{_esc(text)}</text>')

    # Volympanel: egen baslinje och egen skala, medvetet skild fran kurspanelen.
    max_vol = max((b.volume for b in bars), default=0) or 1
    for i, bar in enumerate(bars):
        vh = bar.volume / max_vol * vol.height
        out.append(f'<rect x="{x(i) - body / 2:.1f}" y="{vol.bottom - vh:.1f}" '
                   f'width="{body:.1f}" height="{max(0.5, vh):.1f}" '
                   f'fill="{UP if bar.is_up else DOWN}" opacity="0.32"/>')
    out.append(f'<line x1="{plot.left}" y1="{vol.bottom:.1f}" x2="{plot.right}" '
               f'y2="{vol.bottom:.1f}" stroke="{AXIS}" stroke-width="1"/>')
    out.append(f'<text x="{plot.left - 8}" y="{vol.top + 10:.1f}" text-anchor="end" '
               f'class="chart-tick">volym</text>')

    # Tidsaxel - glest satta etiketter sa att de inte krockar.
    every = max(1, len(bars) // 8)
    for i in range(0, len(bars), every):
        out.append(f'<text x="{x(i):.1f}" y="{height - 6}" text-anchor="middle" '
                   f'class="chart-tick">{_esc(bars[i].clock)}</text>')

    out.append(f'<g class="chart-hover"><line class="crosshair" y1="{plot.top}" '
               f'y2="{vol.bottom:.1f}" stroke="{INK_MUTED}" stroke-width="1"/></g>')
    out.append("</svg>")

    payload = [{"t": b.clock, "d": b.ts[:10], "o": b.open, "h": b.high,
                "l": b.low, "c": b.close, "v": b.volume} for b in bars]
    geometry = {"left": plot.left, "step": step, "width": width, "count": len(bars)}
    return (f'<div class="chart-wrap" data-chart="candles" '
            f'data-bars="{_esc(json.dumps(payload))}" '
            f'data-geo="{_esc(json.dumps(geometry))}">'
            + "".join(out) +
            '<div class="chart-tip" hidden></div></div>')


def equity_curve(points: list[tuple[str, float]], width: int = 460, height: int = 190) -> str:
    """Ackumulerat resultat. En serie - alltsa ingen teckenforklaring."""
    if len(points) < 2:
        return '<p class="empty">Minst två avslutade affärer krävs för en kurva.</p>'

    plot = Box(62, 12, width - 74, height - 34)
    values = [p[1] for p in points] + [0.0]
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.08 or 1.0
    lo, hi = lo - pad, hi + pad

    def y(v: float) -> float:
        return plot.bottom - (v - lo) / (hi - lo) * plot.height

    def x(i: int) -> float:
        return plot.left + plot.width * (i / (len(points) - 1))

    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
           f'role="img" class="chart">']
    for tick in nice_ticks(lo, hi, 4):
        ty = y(tick)
        out.append(f'<line x1="{plot.left}" y1="{ty:.1f}" x2="{plot.right}" y2="{ty:.1f}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{plot.left - 8}" y="{ty + 4:.1f}" text-anchor="end" '
                   f'class="chart-tick">{_fmt(tick, 0)}</text>')

    zero = y(0)
    out.append(f'<line x1="{plot.left}" y1="{zero:.1f}" x2="{plot.right}" y2="{zero:.1f}" '
               f'stroke="{AXIS}" stroke-width="1"/>')

    coords = [(x(i), y(v)) for i, (_, v) in enumerate(points)]
    area = (f"M{coords[0][0]:.1f} {zero:.1f} "
            + " ".join(f"L{px:.1f} {py:.1f}" for px, py in coords)
            + f" L{coords[-1][0]:.1f} {zero:.1f} Z")
    out.append(f'<path d="{area}" fill="{SERIES[0]}" opacity="0.10"/>')
    out.append(f'<path d="{_path(list(coords))}" fill="none" stroke="{SERIES[0]}" '
               f'stroke-width="2" stroke-linejoin="round"/>')

    ex, ey = coords[-1]
    out.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="{SERIES[0]}" '
               f'stroke="{SURFACE}" stroke-width="2"/>')
    out.append(f'<text x="{ex - 6:.1f}" y="{ey - 10:.1f}" text-anchor="end" '
               f'class="chart-label">{_fmt(points[-1][1], 0)} kr</text>')
    out.append("</svg>")
    return '<div class="chart-wrap">' + "".join(out) + "</div>"


def r_distribution(buckets: list[tuple[str, int]], width: int = 460, height: int = 190) -> str:
    """Fordelning av utfall i R. Polaritet: forlustfacken at ena hallet."""
    if not buckets:
        return '<p class="empty">Ingen avslutad affär att fördela än.</p>'

    plot = Box(16, 12, width - 32, height - 46)
    top = max(count for _, count in buckets) or 1
    slot = plot.width / len(buckets)
    bar_w = min(24.0, slot - 8)

    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
           f'role="img" class="chart">']
    out.append(f'<line x1="{plot.left}" y1="{plot.bottom:.1f}" x2="{plot.right}" '
               f'y2="{plot.bottom:.1f}" stroke="{AXIS}" stroke-width="1"/>')

    for i, (label, count) in enumerate(buckets):
        cx = plot.left + slot * (i + 0.5)
        h = (count / top) * plot.height
        loss = label.startswith("<") or label.startswith("-")
        color = DOWN if loss else UP
        if count:
            # 4 px rundad datande, fyrkantig mot baslinjen.
            r = min(4.0, h)
            bx, by = cx - bar_w / 2, plot.bottom - h
            out.append(f'<path d="M{bx:.1f} {plot.bottom:.1f} V{by + r:.1f} '
                       f'q0 {-r:.1f} {r:.1f} {-r:.1f} H{bx + bar_w - r:.1f} '
                       f'q{r:.1f} 0 {r:.1f} {r:.1f} V{plot.bottom:.1f} Z" fill="{color}"/>')
            out.append(f'<text x="{cx:.1f}" y="{by - 6:.1f}" text-anchor="middle" '
                       f'class="chart-label">{count}</text>')
        out.append(f'<text x="{cx:.1f}" y="{height - 16}" text-anchor="middle" '
                   f'class="chart-tick">{_esc(label)}</text>')

    out.append(f'<text x="{width / 2:.1f}" y="{height - 2}" text-anchor="middle" '
               f'class="chart-tick">utfall i R</text>')
    out.append("</svg>")
    return '<div class="chart-wrap">' + "".join(out) + "</div>"

"""Aktiekoll – personligt beslutsstöd inför aktieköp.

Kör: ./run.sh  (eller uvicorn app.main:app --reload)
"""
from __future__ import annotations

import os
from datetime import date

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import format as fmt
from .db import connect, get_settings, init_db, put_setting, setting_float
from .market import MarketData, build_provider
from .services import repo
from .services.analysis import BUY, HOLD_OFF, WATCH
from .services.overview import build_overview, candidates_from
from .services.planner import build_plan

BASE_DIR = os.path.dirname(__file__)

app = FastAPI(title="Aktiekoll")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

conn = connect()
init_db(conn)
market = MarketData(provider=build_provider(), conn=conn)


# --- formatering -----------------------------------------------------------
# Ligger i app/format.py sa att tjanster och mallar skriver tal likadant.

templates.env.filters.update(num=fmt.num, kr=fmt.kr, pct=fmt.pct,
                             spct=fmt.signed_pct, cap=fmt.cap)
templates.env.globals.update(
    VERDICT_BUY=BUY, VERDICT_WATCH=WATCH, VERDICT_HOLD=HOLD_OFF,
    KIND_LABEL={"BUY": "Köp", "SELL": "Sälj", "DIVIDEND": "Utdelning", "SPLIT": "Split"},
)


def page(request: Request, template: str, **ctx) -> HTMLResponse:
    ctx.setdefault("source", market.source)
    ctx.setdefault("today", date.today().isoformat())
    ctx["path"] = request.url.path
    return templates.TemplateResponse(request, template, ctx)


def as_float(value: str | None, fallback: float | None = None) -> float | None:
    if value is None:
        return fallback
    cleaned = str(value).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    if cleaned == "":
        return fallback
    try:
        return float(cleaned)
    except ValueError:
        return fallback


def back(request: Request, default: str = "/") -> RedirectResponse:
    return RedirectResponse(request.headers.get("referer") or default, status_code=303)


# --- vyer ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    ov = build_overview(conn, market)
    budget = setting_float(ov.settings, "monthly_budget", 5000)
    plan = build_plan(
        budget, candidates_from(ov),
        {r.ticker: (r.value_base or 0.0) for r in ov.rows},
        courtage_min=setting_float(ov.settings, "courtage_min", 1),
        courtage_pct=setting_float(ov.settings, "courtage_pct", 0.0025),
        max_courtage_pct_of_order=setting_float(ov.settings, "max_courtage_pct_of_order", 0.005),
        max_position_pct=setting_float(ov.settings, "max_position_pct", 0.15),
    )
    return page(request, "dashboard.html", ov=ov, plan=plan, budget=budget)


@app.get("/bevakning", response_class=HTMLResponse)
def watchlist(request: Request):
    ov = build_overview(conn, market)
    return page(request, "watchlist.html", ov=ov)


@app.post("/bevakning")
def watchlist_save(
    request: Request,
    ticker: str = Form(...),
    target_weight: str = Form("0"),
    max_buy_price: str = Form(""),
    thesis: str = Form(""),
):
    ticker = ticker.strip().upper()
    if not ticker:
        return back(request, "/bevakning")
    quote = market.quote(ticker)
    repo.upsert_instrument(
        conn, ticker,
        name=quote.name if quote else "",
        currency=quote.currency if quote else "SEK",
        sector=quote.sector if quote else "",
    )
    repo.add_watch(
        conn, ticker,
        target_weight=(as_float(target_weight, 0) or 0) / 100,   # matas in i procent
        max_buy_price=as_float(max_buy_price, None),
        thesis=thesis.strip(),
    )
    return RedirectResponse("/bevakning", status_code=303)


@app.post("/bevakning/{ticker}/ta-bort")
def watchlist_remove(request: Request, ticker: str):
    repo.remove_watch(conn, ticker)
    return RedirectResponse("/bevakning", status_code=303)


@app.get("/aktie/{ticker}", response_class=HTMLResponse)
def stock_detail(request: Request, ticker: str):
    ticker = ticker.upper()
    if not repo.get_instrument(conn, ticker):
        quote = market.quote(ticker)
        if quote:
            repo.upsert_instrument(conn, ticker, quote.name, quote.currency, quote.sector)
    ov = build_overview(conn, market)
    row = ov.by_ticker(ticker)
    txns = repo.list_transactions(conn, ticker)
    return page(request, "stock.html", ov=ov, row=row, ticker=ticker, txns=txns)


@app.get("/portfolj", response_class=HTMLResponse)
def portfolio(request: Request):
    ov = build_overview(conn, market)
    return page(request, "portfolio.html", ov=ov)


@app.get("/transaktioner", response_class=HTMLResponse)
def transactions(request: Request):
    ov = build_overview(conn, market)
    return page(request, "transactions.html", ov=ov, txns=repo.list_transactions(conn))


@app.post("/transaktioner")
def transactions_add(
    request: Request,
    ticker: str = Form(...),
    kind: str = Form(...),
    trade_date: str = Form(...),
    quantity: str = Form("0"),
    price: str = Form("0"),
    fee: str = Form("0"),
    note: str = Form(""),
):
    ticker = ticker.strip().upper()
    if not repo.get_instrument(conn, ticker):
        quote = market.quote(ticker)
        repo.upsert_instrument(conn, ticker, quote.name if quote else "",
                               quote.currency if quote else "SEK",
                               quote.sector if quote else "")
    repo.add_transaction(
        conn, ticker, kind, trade_date,
        quantity=as_float(quantity, 0) or 0,
        price=as_float(price, 0) or 0,
        fee=as_float(fee, 0) or 0,
        note=note.strip(),
    )
    return back(request, "/transaktioner")


@app.post("/transaktioner/{txn_id}/ta-bort")
def transactions_delete(request: Request, txn_id: int):
    repo.delete_transaction(conn, txn_id)
    return back(request, "/transaktioner")


@app.get("/plan", response_class=HTMLResponse)
def plan_view(request: Request, budget: str | None = None):
    ov = build_overview(conn, market)
    amount = as_float(budget, None) or setting_float(ov.settings, "monthly_budget", 5000)
    plan = build_plan(
        amount, candidates_from(ov),
        {r.ticker: (r.value_base or 0.0) for r in ov.rows},
        courtage_min=setting_float(ov.settings, "courtage_min", 1),
        courtage_pct=setting_float(ov.settings, "courtage_pct", 0.0025),
        max_courtage_pct_of_order=setting_float(ov.settings, "max_courtage_pct_of_order", 0.005),
        max_position_pct=setting_float(ov.settings, "max_position_pct", 0.15),
    )
    return page(request, "plan.html", ov=ov, plan=plan, budget=amount)


@app.get("/plan.txt", response_class=PlainTextResponse)
def plan_text(budget: str | None = None):
    """Orderlistan som ren text – att ha bredvid mäklaren när du lägger order."""
    ov = build_overview(conn, market)
    settings = ov.settings
    amount = as_float(budget, None) or setting_float(settings, "monthly_budget", 5000)
    plan = build_plan(
        amount, candidates_from(ov),
        {r.ticker: (r.value_base or 0.0) for r in ov.rows},
        courtage_min=setting_float(settings, "courtage_min", 1),
        courtage_pct=setting_float(settings, "courtage_pct", 0.0025),
        max_courtage_pct_of_order=setting_float(settings, "max_courtage_pct_of_order", 0.005),
        max_position_pct=setting_float(settings, "max_position_pct", 0.15),
    )
    lines = [f"Orderunderlag {date.today().isoformat()}  (budget {fmt.kr(amount)})", ""]
    for o in plan.orders:
        lines.append(f"{o.ticker:<12} {o.shares:>5} st  à {fmt.num(o.price)}  "
                     f"= {fmt.kr(o.amount)}  + courtage {fmt.kr(o.courtage, 2)}")
    if not plan.orders:
        lines.append("Inga köp föreslås med nuvarande regler och budget.")
    lines += ["", f"Summa: {fmt.kr(plan.spent, 2)}   Kvar: {fmt.kr(plan.leftover, 2)}"]
    if plan.skipped:
        lines += ["", "Överhoppade:"]
        lines += [f"  {t}: {why}" for t, why in plan.skipped]
    lines += ["", f"Källa: {market.source}. Kontrollera kurserna hos din mäklare innan du lägger order."]
    return "\n".join(lines)


@app.get("/installningar", response_class=HTMLResponse)
def settings_view(request: Request):
    return page(request, "settings.html", settings=get_settings(conn))


@app.post("/installningar")
def settings_save(
    request: Request,
    min_dividend_yield: str = Form("3"),
    max_pe: str = Form("20"),
    max_position_pct: str = Form("15"),
    courtage_min: str = Form("1"),
    courtage_pct: str = Form("0.25"),
    max_courtage_pct_of_order: str = Form("0.5"),
    monthly_budget: str = Form("5000"),
):
    put_setting(conn, "min_dividend_yield", (as_float(min_dividend_yield, 3) or 0) / 100)
    put_setting(conn, "max_pe", as_float(max_pe, 20) or 20)
    put_setting(conn, "max_position_pct", (as_float(max_position_pct, 15) or 15) / 100)
    put_setting(conn, "courtage_min", as_float(courtage_min, 1) or 0)
    put_setting(conn, "courtage_pct", (as_float(courtage_pct, 0.25) or 0) / 100)
    put_setting(conn, "max_courtage_pct_of_order", (as_float(max_courtage_pct_of_order, 0.5) or 0) / 100)
    put_setting(conn, "monthly_budget", as_float(monthly_budget, 5000) or 0)
    return RedirectResponse("/installningar", status_code=303)


@app.post("/uppdatera-kurser")
def refresh_quotes(request: Request):
    build_overview(conn, market, refresh=True)
    return back(request, "/")

"""Fyller databasen med ett exempel så att appen har något att visa direkt.

Kör: python -m app.seed
"""
from __future__ import annotations

from .db import connect, init_db
from .market import MarketData, build_provider
from .services import repo

WATCH = [
    # ticker,      andel, köpgräns, tes
    ("VOLV-B.ST", 0.15, 280.0, "Stark utdelare, köper under 280"),
    ("INVE-B.ST", 0.20, 290.0, "Bred exponering till substansrabatt"),
    ("SHB-A.ST",  0.10, 115.0, "Låg värdering, stabil utdelning"),
    ("ATCO-A.ST", 0.10, 160.0, "Kvalitetsbolag, vill in billigare"),
    ("TELIA.ST",  0.05,  30.0, "Hög direktavkastning men svag tillväxt"),
    ("AAPL",      0.10, 230.0, "Långsiktigt innehav i USD"),
]

TXNS = [
    ("VOLV-B.ST", "BUY",      "2025-02-14", 20, 232.0, 39),
    ("VOLV-B.ST", "BUY",      "2025-09-05", 15, 254.5, 39),
    ("VOLV-B.ST", "DIVIDEND", "2026-04-08",  0,  18.0,  0),
    ("INVE-B.ST", "BUY",      "2025-03-20", 30, 244.0, 39),
    ("INVE-B.ST", "DIVIDEND", "2026-05-12",  0,   4.6,  0),
    ("SHB-A.ST",  "BUY",      "2025-06-02", 40,  98.5, 39),
    ("SHB-A.ST",  "SELL",     "2026-01-15", 10, 121.0, 39),
    ("AAPL",      "BUY",      "2025-11-11",  8, 195.0, 49),
]


# Affarer for journalen. Medvetet sa att en uppstallning tjanar pengar, en ar
# jamn och en drar ned hela resultatet - det ar just det monstret journalen finns
# for att gora synligt.
#  ticker, riktning, setup, oppnad, stangd, ingang, stopp, utgang, antal, courtage
TRADES = [
    ("VOLV-B.ST", "LONG",  "Öppningsrange",     "2026-09-07T09:35", "2026-09-07T10:20", 264.0, 261.0, 270.0, 120, 78),
    ("ERIC-B.ST", "LONG",  "Öppningsrange",     "2026-09-07T09:40", "2026-09-07T11:05",  78.0,  77.0,  80.5, 400, 78),
    ("SAND.ST",   "SHORT", "Motvals",           "2026-09-07T13:10", "2026-09-07T14:40", 220.0, 223.0, 224.5, 100, 78),
    ("VOLV-B.ST", "LONG",  "VWAP-återtag",      "2026-09-08T10:05", "2026-09-08T12:30", 266.5, 264.0, 271.0, 130, 78),
    ("ATCO-A.ST", "LONG",  "Öppningsrange",     "2026-09-08T09:33", "2026-09-08T09:58", 170.0, 168.5, 168.5, 200, 78),
    ("SHB-A.ST",  "LONG",  "Trendfortsättning", "2026-09-08T14:00", "2026-09-08T16:50", 111.0, 109.8, 113.4, 300, 78),
    ("SAND.ST",   "SHORT", "Motvals",           "2026-09-09T11:20", "2026-09-09T12:05", 219.0, 222.0, 222.0, 110, 78),
    ("TELIA.ST",  "LONG",  "Öppningsrange",     "2026-09-09T09:34", "2026-09-09T10:15",  31.2,  30.8,  32.0, 900, 78),
    ("ERIC-B.ST", "SHORT", "Motvals",           "2026-09-09T15:10", "2026-09-09T16:30",  79.5,  80.8,  80.8, 350, 78),
    ("VOLV-B.ST", "LONG",  "VWAP-återtag",      "2026-09-10T10:40", "2026-09-10T13:15", 267.0, 264.5, 272.5, 120, 78),
    ("ATCO-A.ST", "LONG",  "Trendfortsättning", "2026-09-10T11:00", "2026-09-10T15:40", 171.5, 169.5, 175.0, 180, 78),
    ("SAND.ST",   "SHORT", "Motvals",           "2026-09-10T13:30", "2026-09-10T14:10", 221.0, 224.0, 224.0, 100, 78),
    ("SHB-A.ST",  "LONG",  "Öppningsrange",     "2026-09-11T09:35", "2026-09-11T10:50", 112.0, 110.9, 114.2, 280, 78),
    ("ERIC-B.ST", "LONG",  "VWAP-återtag",      "2026-09-11T11:30", "2026-09-11T14:20",  78.5,  77.6,  77.6, 400, 78),
    ("VOLV-B.ST", "SHORT", "Motvals",           "2026-09-11T15:00", "2026-09-11T16:25", 269.0, 272.0, 272.0, 100, 78),
    ("TELIA.ST",  "LONG",  "Trendfortsättning", "2026-09-14T10:15", "2026-09-14T16:10",  31.0,  30.6,  31.9, 950, 78),
    ("ATCO-A.ST", "LONG",  "Öppningsrange",     "2026-09-15T09:33", "2026-09-15T11:40", 172.0, 170.2, 176.5, 170, 78),
    ("SAND.ST",   "SHORT", "Motvals",           "2026-09-15T14:20", "2026-09-15T15:05", 218.0, 221.0, 221.0, 110, 78),
]


def main() -> None:
    conn = connect()
    init_db(conn)
    market = MarketData(provider=build_provider(), conn=conn)

    for ticker, weight, limit, thesis in WATCH:
        quote = market.quote(ticker)
        repo.upsert_instrument(conn, ticker,
                               name=quote.name if quote else "",
                               currency=quote.currency if quote else "SEK",
                               sector=quote.sector if quote else "")
        repo.add_watch(conn, ticker, target_weight=weight, max_buy_price=limit, thesis=thesis)

    existing = {(t.ticker, t.kind, t.trade_date) for t in repo.list_transactions(conn)}
    added = 0
    for ticker, kind, day, qty, price, fee in TXNS:
        if (ticker, kind, day) in existing:
            continue
        if not repo.get_instrument(conn, ticker):
            repo.upsert_instrument(conn, ticker)
        repo.add_transaction(conn, ticker, kind, day, qty, price, fee, note="exempeldata")
        added += 1

    befintliga_affarer = {(t.ticker, t.opened_at) for t in repo.list_trades(conn)}
    nya_affarer = 0
    for ticker, riktning, setup, oppnad, stangd, ingang, stopp, utgang, antal, courtage in TRADES:
        if (ticker, oppnad) in befintliga_affarer:
            continue
        repo.add_trade(conn, ticker, riktning, oppnad, entry=ingang, stop=stopp,
                       quantity=antal, setup=setup, fees=courtage, note="exempeldata",
                       closed_at=stangd, exit_price=utgang)
        nya_affarer += 1

    print(f"Bevakningslista: {len(WATCH)} poster. Nya transaktioner: {added}.")
    print(f"Nya affärer i journalen: {nya_affarer}.")
    print(f"Källa: {market.source}")
    conn.close()


if __name__ == "__main__":
    main()

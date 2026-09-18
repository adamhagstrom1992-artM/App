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

    print(f"Bevakningslista: {len(WATCH)} poster. Nya transaktioner: {added}.")
    print(f"Källa: {market.source}")
    conn.close()


if __name__ == "__main__":
    main()

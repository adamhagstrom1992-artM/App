from app.services.holdings import Transaction, compute_positions, portfolio_totals


def tx(kind, date, qty=0.0, price=0.0, fee=0.0, ticker="ABC", _id=None):
    return Transaction(ticker=ticker, kind=kind, trade_date=date, quantity=qty,
                       price=price, fee=fee, id=_id)


def test_kop_raknar_in_courtage_i_omkostnadsbeloppet():
    pos = compute_positions([tx("BUY", "2026-01-10", 10, 100, fee=39)])["ABC"]
    assert pos.quantity == 10
    assert pos.cost_basis == 1039
    assert pos.avg_cost == 103.9


def test_genomsnittsmetoden_viktar_flera_kop():
    pos = compute_positions([
        tx("BUY", "2026-01-10", 10, 100, _id=1),
        tx("BUY", "2026-02-10", 30, 200, _id=2),
    ])["ABC"]
    assert pos.quantity == 40
    assert pos.avg_cost == (10 * 100 + 30 * 200) / 40  # 175, inte 150


def test_forsaljning_lamnar_gav_orort_och_bokar_realiserat():
    pos = compute_positions([
        tx("BUY", "2026-01-10", 10, 100, _id=1),
        tx("BUY", "2026-02-10", 10, 200, _id=2),
        tx("SELL", "2026-03-10", 5, 200, fee=10, _id=3),
    ])["ABC"]
    assert pos.avg_cost == 150            # oforandrat av forsaljningen
    assert pos.quantity == 15             # 20 kopta minus 5 salda
    assert pos.cost_basis == 15 * 150
    assert pos.realized_pl == 5 * 200 - 10 - 5 * 150   # 240


def test_full_forsaljning_nollar_innehavet():
    pos = compute_positions([
        tx("BUY", "2026-01-10", 10, 100, _id=1),
        tx("SELL", "2026-06-10", 10, 120, _id=2),
    ])["ABC"]
    assert pos.quantity == 0
    assert pos.cost_basis == 0
    assert pos.realized_pl == 200


def test_split_fordelar_samma_omkostnadsbelopp_pa_fler_aktier():
    pos = compute_positions([
        tx("BUY", "2026-01-10", 10, 150, _id=1),
        tx("SPLIT", "2026-05-02", qty=2, _id=2),
    ])["ABC"]
    assert pos.quantity == 20
    assert pos.cost_basis == 1500
    assert pos.avg_cost == 75


def test_utdelning_utan_antal_anvander_hela_innehavet():
    pos = compute_positions([
        tx("BUY", "2026-01-10", 100, 50, _id=1),
        tx("DIVIDEND", "2026-04-10", qty=0, price=3.5, _id=2),
    ])["ABC"]
    assert pos.dividends == 350
    assert pos.quantity == 100          # utdelning ror inte antalet


def test_forsaljning_over_innehav_varnar_och_klipps():
    pos = compute_positions([
        tx("BUY", "2026-01-10", 5, 100, _id=1),
        tx("SELL", "2026-02-10", 50, 120, _id=2),
    ])["ABC"]
    assert pos.quantity == 0
    assert pos.warnings and "överstiger innehavet" in pos.warnings[0]


def test_transaktioner_sorteras_pa_datum_oavsett_inmatningsordning():
    sen_forst = compute_positions([
        tx("SELL", "2026-03-10", 5, 200, _id=2),
        tx("BUY", "2026-01-10", 10, 100, _id=1),
    ])["ABC"]
    assert sen_forst.quantity == 5
    assert sen_forst.realized_pl == 500


def test_portfoljsummering_hoppar_over_saknade_kurser():
    positions = compute_positions([
        tx("BUY", "2026-01-10", 10, 100, ticker="AAA", _id=1),
        tx("BUY", "2026-01-10", 10, 100, ticker="BBB", _id=2),
        tx("DIVIDEND", "2026-04-10", price=5, ticker="AAA", _id=3),
    ])
    totals = portfolio_totals(positions, {"AAA": 150, "BBB": None})
    assert totals["market_value"] == 1500
    assert totals["cost_basis"] == 2000        # bada posterna
    assert totals["unrealized_pl"] == 500      # men bara den prissatta i resultatet
    assert totals["dividends"] == 50

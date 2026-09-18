from app.market.base import Quote
from app.services import analysis
from app.services.analysis import evaluate


def q(**kw):
    base = dict(ticker="AAA", price=100.0, pe=15.0, eps=6.0, dividend_yield=0.05,
                payout_ratio=0.5, high_52w=120.0, low_52w=80.0)
    base.update(kw)
    return Quote(**base)


def test_uppfyllda_krav_ger_kopvard():
    a = evaluate(q(), max_buy_price=110, min_yield=0.03, max_pe=20)
    assert a.verdict == analysis.BUY


def test_kurs_over_kopgransen_blockerar():
    a = evaluate(q(price=150.0), max_buy_price=110, min_yield=0.03, max_pe=20)
    assert a.verdict == analysis.HOLD_OFF


def test_for_hogt_pe_ger_bevaka_inte_kopvard():
    a = evaluate(q(pe=45.0), max_buy_price=110, min_yield=0.03, max_pe=20)
    assert a.verdict == analysis.WATCH


def test_overvikt_blockerar_pafyllning():
    a = evaluate(q(), max_buy_price=110, max_position_pct=0.15, current_weight=0.30)
    assert a.verdict == analysis.HOLD_OFF
    assert any(c.label == "Utrymme i portföljen" and c.ok is False for c in a.checks)


def test_saknad_kurs_ger_okant_omdome():
    a = evaluate(None)
    assert a.verdict == analysis.UNKNOWN


def test_saknade_nyckeltal_raknas_inte_som_underkant():
    a = evaluate(q(pe=None, dividend_yield=None, payout_ratio=None), max_buy_price=110)
    assert a.verdict == analysis.UNKNOWN
    assert a.relevant == 1              # bara köpgränsen gick att pröva


def test_riktkurs_speglar_ditt_eget_pe_tak():
    a = evaluate(q(eps=6.0), max_pe=20)
    assert a.fair_value == 120.0

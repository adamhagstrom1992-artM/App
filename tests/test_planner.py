from app.services.planner import Candidate, build_plan, courtage_for


def cand(ticker, price, weight, limit=None, native=None):
    return Candidate(ticker=ticker, name=ticker, price=price, target_weight=weight,
                     max_buy_price=limit, price_native=native)


def test_pengarna_gar_till_den_som_ligger_langst_under_malvikt():
    plan = build_plan(
        10_000,
        [cand("AAA", 100, 0.5), cand("BBB", 100, 0.5)],
        {"AAA": 9_000, "BBB": 1_000},
        courtage_min=0, courtage_pct=0, max_position_pct=1.0,
    )
    by_ticker = {o.ticker: o for o in plan.orders}
    assert "BBB" in by_ticker
    assert by_ticker["BBB"].amount > by_ticker.get("AAA", by_ticker["BBB"]).amount or "AAA" not in by_ticker


def test_kurs_over_kopgransen_hoppas_over_med_skal():
    plan = build_plan(
        10_000,
        [cand("AAA", 250, 1.0, limit=200)],
        {},
        courtage_min=0, courtage_pct=0, max_position_pct=1.0,
    )
    assert plan.orders == []
    assert plan.skipped[0][0] == "AAA"
    assert "gräns" in plan.skipped[0][1]


def test_kopgransen_jamfors_i_aktiens_egen_valuta():
    # Kurs 220 USD (2299 SEK) mot en grans satt i USD.
    plan = build_plan(
        100_000,
        [cand("AAPL", 2299.0, 1.0, limit=230, native=220.0)],
        {},
        courtage_min=0, courtage_pct=0, max_position_pct=1.0,
    )
    assert len(plan.orders) == 1        # under gransen i USD, alltsa kopvard


def test_innehav_pa_malvikt_far_inga_pengar():
    plan = build_plan(
        1_000,
        [cand("AAA", 100, 0.10)],
        {"AAA": 50_000},
        courtage_min=0, courtage_pct=0,
    )
    assert plan.orders == []
    assert "målvikt" in plan.skipped[0][1]


def test_bara_hela_aktier_och_budgeten_haller():
    plan = build_plan(
        1_000,
        [cand("AAA", 300, 1.0)],
        {},
        courtage_min=39, courtage_pct=0, max_courtage_pct_of_order=1.0, max_position_pct=1.0,
    )
    order = plan.orders[0]
    assert order.shares == 3            # 3 x 300 + 39 = 939 ryms, 4 st gor det inte
    assert order.total <= 1_000
    assert plan.leftover >= 0


def test_courtagesparr_stoppar_smulorder():
    plan = build_plan(
        200,
        [cand("AAA", 150, 1.0)],
        {},
        courtage_min=39, courtage_pct=0, max_courtage_pct_of_order=0.005, max_position_pct=1.0,
    )
    assert plan.orders == []
    assert "Courtaget" in plan.skipped[0][1]


def test_planen_overskrider_aldrig_budgeten():
    plan = build_plan(
        10_000,
        [cand(t, 97, 0.25) for t in ("AAA", "BBB", "CCC", "DDD")],
        {},
        courtage_min=39, courtage_pct=0.0025, max_courtage_pct_of_order=1.0, max_position_pct=1.0,
    )
    assert plan.spent <= 10_000
    assert sum(o.total for o in plan.orders) == plan.spent
    assert plan.leftover >= 0


def test_maxvikt_kapar_en_for_stor_malvikt():
    plan = build_plan(
        100_000,
        [cand("AAA", 100, 0.80)],
        {},
        courtage_min=0, courtage_pct=0, max_position_pct=0.10,
    )
    # Taket pa 10 % av 100 000 ger 10 000 kr, inte 80 000.
    assert plan.orders[0].amount == 10_000


def test_courtage_ar_hogsta_av_minimum_och_procent():
    assert courtage_for(1_000, 39, 0.0025) == 39
    assert courtage_for(100_000, 39, 0.0025) == 250

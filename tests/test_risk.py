import pytest

from app.services.risk import LONG, SHORT, plan_trade, r_multiple


def plan(**kw):
    base = dict(account_size=100_000, risk_pct=0.01, entry=100.0, stop=98.0,
                courtage_min=0, courtage_pct=0, max_position_pct=1.0)
    base.update(kw)
    return plan_trade(**base)


def test_antalet_aktier_foljer_av_risken_inte_av_kapitalet():
    # 1 % av 100 000 = 1 000 kr risk, 2 kr per aktie till stoppen -> 500 aktier.
    p = plan()
    assert p.shares == 500
    assert p.risk_budget == 1_000
    assert p.risk_actual == 1_000
    assert p.position_value == 50_000


def test_tatare_stopp_ger_fler_aktier_men_samma_risk():
    tat, vid = plan(stop=99.0), plan(stop=95.0)
    assert tat.shares == 1_000 and vid.shares == 200
    assert tat.risk_actual == vid.risk_actual == 1_000


def test_courtage_rors_in_i_den_verkliga_risken():
    p = plan(courtage_min=39, courtage_pct=0)
    assert p.fees == 78                       # in och ut
    assert p.risk_actual == 1_000 + 78


def test_positionstaket_kapar_en_orimligt_stor_position():
    p = plan(stop=99.9, max_position_pct=0.25)   # tat stopp -> annars 10 000 aktier
    assert p.position_value <= 25_000
    assert p.capped_by_position_limit
    assert any("nedkapat" in w for w in p.warnings)


def test_kort_affar_kraver_stopp_over_ingangen():
    assert plan(direction=SHORT, entry=100, stop=102).shares == 500
    fel = plan(direction=SHORT, entry=100, stop=98)
    assert not fel.ok and "kort affär" in fel.blockers[0]


def test_lang_affar_kraver_stopp_under_ingangen():
    fel = plan(entry=100, stop=105)
    assert not fel.ok and "lång affär" in fel.blockers[0]


def test_for_liten_risk_for_en_hel_aktie_blockerar():
    p = plan(account_size=1_000, risk_pct=0.001, entry=500, stop=400)
    assert not p.ok
    assert "hel aktie" in p.blockers[0]


def test_malkurser_raknas_i_r():
    p = plan()                                  # risk 2 kr per aktie
    assert p.target(1) == 102 and p.target(3) == 106
    kort = plan(direction=SHORT, entry=100, stop=102)
    assert kort.target(2) == 96


def test_breakeven_ligger_courtaget_bort_fran_ingangen():
    p = plan(courtage_min=50, courtage_pct=0)
    assert p.breakeven == 100 + 100 / p.shares   # 100 kr avgifter fordelat pa antalet


def test_for_tat_stopp_mot_atr_varnar():
    p = plan(stop=99.8, atr=3.0)                 # 0,2 kr risk mot 3 kr normal rorelse
    assert any("brus" in w for w in p.warnings)


def test_for_vid_stopp_mot_atr_varnar():
    p = plan(stop=80.0, atr=2.0)
    assert any("fyra ATR" in w for w in p.warnings)


def test_r_multipel_ar_resultat_delat_med_tagen_risk():
    assert r_multiple(100, 98, 106, LONG) == 3.0
    assert r_multiple(100, 98, 98, LONG) == -1.0
    assert r_multiple(100, 102, 94, SHORT) == 3.0
    assert r_multiple(100, 100, 110, LONG) is None      # ingen risk, odefinierat


@pytest.mark.parametrize("field,value", [("account_size", 0), ("risk_pct", 0), ("entry", 0)])
def test_orimliga_indata_blockerar_istallet_for_att_krascha(field, value):
    assert not plan(**{field: value}).ok

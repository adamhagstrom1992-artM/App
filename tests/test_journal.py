from app.services.journal import Trade, group_stats, r_histogram, summarize
from app.services.risk import LONG, SHORT


def trade(entry=100.0, stop=98.0, exit=None, qty=100, direction=LONG, fees=0.0,
          opened="2026-09-14T09:30:00", closed="2026-09-14T11:00:00", setup="ORB", _id=1):
    return Trade(ticker="AAA", direction=direction, entry=entry, stop=stop, quantity=qty,
                 opened_at=opened, closed_at=closed if exit is not None else None,
                 exit=exit, setup=setup, fees=fees, id=_id)


def test_oppen_affar_har_inget_resultat_och_raknas_inte():
    t = trade(exit=None)
    assert t.is_open and t.pl is None and t.r is None
    assert summarize([t]).trades == 0


def test_resultat_och_r_for_en_vinnande_lang_affar():
    t = trade(entry=100, stop=98, exit=106, qty=100, fees=80)
    assert t.gross_pl == 600
    assert t.pl == 520                      # courtaget dras av
    assert t.r == 3.0                       # R raknas pa kurserna
    assert t.risk_amount == 200


def test_kort_affar_tjanar_pa_nedgang():
    t = trade(direction=SHORT, entry=100, stop=102, exit=94, qty=50)
    assert t.gross_pl == 300
    assert t.r == 3.0


def test_traffsakerhet_och_expectancy():
    s = summarize([
        trade(exit=104, _id=1),             # +2R
        trade(exit=104, _id=2),             # +2R
        trade(exit=98, _id=3),              # -1R
        trade(exit=98, _id=4),              # -1R
    ])
    assert s.trades == 4 and s.wins == 2 and s.losses == 2
    assert s.win_rate == 0.5
    assert s.expectancy_r == 0.5            # (2+2-1-1)/4
    assert s.best_r == 2.0 and s.worst_r == -1.0


def test_profit_factor_och_payoff():
    s = summarize([trade(exit=106, _id=1), trade(exit=98, _id=2)])
    assert s.gross_win == 600 and s.gross_loss == 200
    assert s.profit_factor == 3.0
    assert s.payoff_ratio == 3.0


def test_profit_factor_utan_forluster_ar_odefinierad_men_kraschar_inte():
    assert summarize([trade(exit=106)]).profit_factor == float("inf")
    assert summarize([]).profit_factor is None


def test_jamn_affar_raknas_varken_som_vinst_eller_forlust():
    s = summarize([trade(exit=100)])
    assert s.scratches == 1 and s.wins == 0 and s.losses == 0
    assert s.win_rate is None


def test_max_drawdown_mats_fran_toppen():
    s = summarize([
        trade(exit=110, _id=1),   # +1000, topp 1000
        trade(exit=94, _id=2),    # -600,  equity 400
        trade(exit=96, _id=3),    # -400,  equity 0
        trade(exit=102, _id=4),   # +200,  equity 200
    ])
    assert s.total_pl == 200
    assert s.max_drawdown == 1000           # fran 1000 ned till 0
    assert [round(e[1]) for e in s.equity] == [1000, 400, 0, 200]


def test_langsta_forlustsvit():
    s = summarize([trade(exit=98, _id=i) for i in range(1, 4)] + [trade(exit=104, _id=4)])
    assert s.longest_loss_streak == 3
    assert s.longest_win_streak == 1


def test_uppdelning_per_setup_satter_det_samsta_sist():
    trades = [
        trade(exit=106, setup="ORB", _id=1),
        trade(exit=106, setup="ORB", _id=2),
        trade(exit=98, setup="Motvals", _id=3),
        trade(exit=98, setup="Motvals", _id=4),
    ]
    grupper = group_stats(trades, key=lambda t: t.setup)
    assert [g[0] for g in grupper] == ["ORB", "Motvals"]
    assert grupper[0][1].sum_r == 6.0
    assert grupper[1][1].sum_r == -2.0


def test_uppdelning_per_veckodag_anvander_svenska_namn():
    grupper = group_stats([trade(opened="2026-09-14T09:30:00", exit=104)],
                          key=lambda t: t.weekday)
    assert grupper[0][0] == "Måndag"        # 2026-09-14 ar en mandag


def test_r_histogram_lagger_utfall_i_ratt_fack():
    fack = dict(r_histogram([-3.0, -0.5, 0.5, 1.5, 2.5, 9.0]))
    assert fack["< -2"] == 1
    assert fack["-1…0"] == 1
    assert fack["0…1"] == 1
    assert fack["> 3"] == 1
    assert r_histogram([]) == []


def test_innehavstid_raknas_i_minuter():
    t = trade(opened="2026-09-14T09:30:00", closed="2026-09-14T11:00:00", exit=104)
    assert t.held_minutes == 90


def test_expectancy_avrundar_bort_flyttalsbrus():
    # +2R, -1R, -1R gar jamnt ut, men summan blir 4e-15 i flyttal.
    s = summarize([trade(exit=104, _id=1), trade(exit=98, _id=2), trade(exit=98, _id=3)])
    assert s.expectancy_r == 0.0

import math

from app.market.intraday import Bar
from app.services import indicators as ind


def bar(o, h, l, c, v=1000.0, ts="2026-09-18T09:00:00+00:00"):
    return Bar(ts=ts, open=o, high=h, low=l, close=c, volume=v)


def test_sma_ar_none_under_uppvarmning_och_ratt_darefter():
    out = ind.sma([1, 2, 3, 4, 5], 3)
    assert out[:2] == [None, None]
    assert out[2] == 2.0 and out[3] == 3.0 and out[4] == 4.0


def test_ema_seedas_med_sma_och_foljer_formeln():
    values = [10, 11, 12, 13]
    out = ind.ema(values, 3)
    assert out[2] == 11.0                       # (10+11+12)/3
    k = 2 / 4
    assert math.isclose(out[3], 13 * k + 11 * (1 - k))


def test_ema_pa_for_kort_serie_ger_bara_none():
    assert ind.ema([1, 2], 5) == [None, None]


def test_vwap_viktar_med_volym_och_nollstalls_per_dag():
    dag1 = [bar(10, 10, 10, 10, v=100, ts="2026-09-17T09:00:00+00:00"),
            bar(20, 20, 20, 20, v=300, ts="2026-09-17T09:05:00+00:00")]
    dag2 = [bar(50, 50, 50, 50, v=100, ts="2026-09-18T09:00:00+00:00")]
    out = ind.vwap(dag1 + dag2)
    assert out[0] == 10
    assert out[1] == (10 * 100 + 20 * 300) / 400      # 17.5, volymviktat
    assert out[2] == 50                                # ny dag, nollstalld


def test_rsi_haller_sig_inom_skalan():
    stigande = list(range(1, 40))
    out = ind.rsi([float(v) for v in stigande], 14)
    assert out[13] is None or 0 <= out[13] <= 100
    assert out[-1] == 100.0                            # bara uppgangar


def test_rsi_pa_bara_nedgangar_narmar_sig_noll():
    out = ind.rsi([float(v) for v in range(40, 1, -1)], 14)
    assert out[-1] == 0.0


def test_true_range_tar_hansyn_till_gap():
    bars = [bar(10, 11, 9, 10), bar(20, 21, 19, 20)]
    tr = ind.true_range(bars)
    assert tr[0] == 2                                  # forsta stapeln: bara hog-lag
    assert tr[1] == 11                                 # gapet upp fran close 10 till hog 21


def test_atr_ar_medel_av_true_range_under_forsta_perioden():
    bars = [bar(10, 12, 8, 10) for _ in range(5)]      # TR = 4 varje stapel
    out = ind.atr(bars, 3)
    assert out[:2] == [None, None]
    assert out[2] == 4.0 and out[-1] == 4.0


def test_oppningsrange_tar_bara_dagens_forsta_staplar():
    igar = [bar(1, 99, 1, 1, ts="2026-09-17T09:00:00+00:00")]
    idag = [bar(10, 12, 9, 11, ts="2026-09-18T09:00:00+00:00"),
            bar(11, 14, 10, 13, ts="2026-09-18T09:05:00+00:00"),
            bar(13, 30, 5, 20, ts="2026-09-18T09:10:00+00:00")]
    hog, lag = ind.opening_range(igar + idag, minutes=10, interval_minutes=5)
    assert (hog, lag) == (14, 9)                       # tredje stapeln ligger utanfor fonstret
    assert ind.opening_range([]) is None


def test_latest_hoppar_over_efterslapande_none():
    assert ind.latest([None, 1.0, 2.0, None]) == 2.0
    assert ind.latest([None, None]) is None

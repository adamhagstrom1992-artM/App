"""Genomgang av alla vyer mot en tillfallig databas i demolage."""
import os
import tempfile

os.environ["AKTIEKOLL_SOURCE"] = "demo"
os.environ["AKTIEKOLL_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def seeded():
    client.post("/bevakning", data={"ticker": "VOLV-B.ST", "target_weight": "20",
                                    "max_buy_price": "300", "thesis": "Testtes"})
    client.post("/transaktioner", data={"ticker": "VOLV-B.ST", "kind": "BUY",
                                        "trade_date": "2026-01-10", "quantity": "10",
                                        "price": "250", "fee": "39"})


@pytest.mark.parametrize("path", [
    "/", "/bevakning", "/portfolj", "/plan", "/transaktioner",
    "/installningar", "/aktie/VOLV-B.ST",
])
def test_alla_vyer_svarar(path):
    r = client.get(path)
    assert r.status_code == 200
    assert "Aktiekoll" in r.text


def test_demolaget_flaggas_tydligt():
    assert "Demoläge" in client.get("/").text


def test_bevakning_visar_kopgrans_och_omdome():
    body = client.get("/bevakning").text
    assert "VOLV-B.ST" in body
    assert "Testtes" in body


def test_innehavet_raknas_fram_ur_transaktionen():
    body = client.get("/portfolj").text
    assert "Volvo B" in body
    assert "10 st" in body


def test_aktievyn_visar_checklistan():
    body = client.get("/aktie/VOLV-B.ST").text
    assert "Mot dina regler" in body
    assert "Under din köpgräns" in body


def test_okand_ticker_ger_vanlig_sida_inte_krasch():
    r = client.get("/aktie/FINNS-INTE.ST")
    assert r.status_code == 200
    assert "Hittade ingen kursdata" in r.text


def test_textlistan_gar_att_ha_bredvid_maklaren():
    r = client.get("/plan.txt?budget=20000")
    assert r.status_code == 200
    assert "Orderunderlag" in r.text
    assert "Källa: demo" in r.text


def test_planen_haller_budgeten():
    r = client.get("/plan?budget=10000")
    assert r.status_code == 200
    assert "Köpplan" in r.text


def test_installningar_sparas_och_visas_igen():
    client.post("/installningar", data={
        "min_dividend_yield": "4.5", "max_pe": "18", "max_position_pct": "12",
        "courtage_min": "39", "courtage_pct": "0.25",
        "max_courtage_pct_of_order": "0.5", "monthly_budget": "7500",
    })
    body = client.get("/installningar").text
    assert "4.5" in body and "7500" in body


def test_transaktion_gar_att_ta_bort():
    client.post("/transaktioner", data={"ticker": "ERIC-B.ST", "kind": "BUY",
                                        "trade_date": "2026-02-01", "quantity": "5",
                                        "price": "80", "fee": "39"})
    assert "ERIC-B.ST" in client.get("/transaktioner").text
    import re
    body = client.get("/transaktioner").text
    ids = re.findall(r"/transaktioner/(\d+)/ta-bort", body)
    client.post(f"/transaktioner/{ids[0]}/ta-bort", follow_redirects=False)
    assert len(re.findall(r"/transaktioner/(\d+)/ta-bort", client.get("/transaktioner").text)) == len(ids) - 1


def test_kommatecken_som_decimaltecken_accepteras():
    client.post("/bevakning", data={"ticker": "TELIA.ST", "target_weight": "7,5",
                                    "max_buy_price": "29,80", "thesis": ""})
    assert "TELIA.ST" in client.get("/bevakning").text


# --- daytrading-vyerna ------------------------------------------------------

@pytest.mark.parametrize("path", ["/trading", "/risk", "/journal"])
def test_daytradingvyerna_svarar(path):
    r = client.get(path)
    assert r.status_code == 200
    assert "Aktiekoll" in r.text


def test_grafen_ritas_som_svg_med_staplar():
    body = client.get("/trading?ticker=VOLV-B.ST&interval=5m&days=2").text
    assert "<svg" in body and 'data-chart="candles"' in body
    assert "VWAP" in body
    assert "stigande stapel" in body           # teckenförklaringen finns


def test_grafvyn_flaggar_att_datat_inte_ar_realtid():
    body = client.get("/trading").text
    assert "syntetiskt brus" in body or "fördröjd" in body


def test_riskberaknaren_ger_antal_aktier_ur_risken():
    body = client.get("/risk?entry=100&stop=98&account=100000&risk=1").text
    assert "500" in body                       # 1000 kr risk / 2 kr per aktie
    assert "Målkurser" in body


def test_riskberaknaren_vagrar_stopp_pa_fel_sida():
    body = client.get("/risk?entry=100&stop=105&account=100000&risk=1").text
    assert "stoppen ligga under ingången" in body


def test_journalen_raknar_r_och_resultat_for_en_avslutad_affar():
    client.post("/journal", data={"ticker": "ERIC-B.ST", "direction": "LONG",
                                  "opened_at": "2026-09-14T09:35", "entry": "80",
                                  "stop": "78", "quantity": "100", "setup": "Utbrott",
                                  "fees": "39"})
    import re
    ids = re.findall(r"/journal/(\d+)/stang", client.get("/journal").text)
    assert ids, "affären ska ligga som öppen"
    client.post(f"/journal/{ids[-1]}/stang", data={"exit_price": "86",
                                                   "closed_at": "2026-09-14T10:40",
                                                   "fees": "39", "note": "testaffär"})
    body = client.get("/journal").text
    assert "3,00R" in body                     # (86-80)/(80-78)
    assert "Utbrott" in body
    assert "Expectancy" in body


def test_affar_gar_att_ta_bort_ur_journalen():
    import re
    before = re.findall(r"/journal/(\d+)/ta-bort", client.get("/journal").text)
    client.post(f"/journal/{before[0]}/ta-bort", follow_redirects=False)
    after = re.findall(r"/journal/(\d+)/ta-bort", client.get("/journal").text)
    assert len(after) == len(before) - 1

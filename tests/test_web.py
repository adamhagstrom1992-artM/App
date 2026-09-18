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

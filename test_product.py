# ─────────────────────────────────────────────────────────────────
# FICHIER : test_stock.py
# LANCER  : pytest test_stock.py -v -s
# PRÉREQUIS : uvicorn main:app --reload  (dans un autre terminal)
# ─────────────────────────────────────────────────────────────────

import httpx

BASE_URL = "http://localhost:8000"

# Variables partagées entre les tests
product_id  = None
all_sns     = []
fail_sn     = None
pass_sn     = None

# ─────────────────────────────────────────────────────────────────
# TEST 1 — Créer un stock de 10 comprimés
# CE QU'ON VÉRIFIE : 10 SN générés au bon format
# SWAGGER          : POST /stock → quantity: 10 → observer 10 SN
# ─────────────────────────────────────────────────────────────────
def test_create_stock():
    global product_id, all_sns

    r = httpx.post(f"{BASE_URL}/stock", json={
        "product_name": "Paracetamol 500mg",
        "form": "comprimes",
        "batch_number": "BAT-001",
        "quantity": 10,
    })

    assert r.status_code == 200
    data = r.json()

    product_id = data["product_id"]
    all_sns = data["serial_numbers"]

    assert data["quantity"] == 10
    assert len(all_sns) == 10
    assert all_sns[0].startswith("SN-")

    print(f"\n✅ Stock créé : {product_id}")
    print(f"   {len(all_sns)} SN générés : {all_sns[0]} → {all_sns[-1]}")


# ─────────────────────────────────────────────────────────────────
# TEST 2 — Voir le stock créé
# CE QU'ON VÉRIFIE : produit visible + total_pending = 10
# SWAGGER          : GET /stock → observer le produit et ses compteurs
# ─────────────────────────────────────────────────────────────────
def test_get_stock():
    r = httpx.get(f"{BASE_URL}/stock")

    assert r.status_code == 200
    assert r.json()["total_products"] >= 1

    produit = next(p for p in r.json()["products"] if p["product_id"] == product_id)
    assert produit["total_pending"] == 10
    assert produit["total_passed"] == 0
    assert produit["total_rejected"] == 0

    print(f"\n✅ Stock visible — pending: 10 | passed: 0 | rejected: 0")


# ─────────────────────────────────────────────────────────────────
# TEST 3 — Machine envoie PASS pour le 1er SN
# CE QU'ON VÉRIFIE : statut → passed, compteur passed +1
# SWAGGER          : POST /machine/test → result: "pass" + SN
# ─────────────────────────────────────────────────────────────────
def test_machine_pass():
    global pass_sn
    pass_sn = all_sns[0]

    r = httpx.post(f"{BASE_URL}/machine/test", json={
        "serial_number": pass_sn,
        "station_id": "STATION-01",
        "result": "pass"
    })

    assert r.status_code == 200
    assert r.json()["result"] == "✅ PASS"
    assert r.json()["status"] == "passed"

    print(f"\n✅ PASS → {pass_sn} | STATION-01")


# ─────────────────────────────────────────────────────────────────
# TEST 4 — Machine envoie FAIL pour le 2ème SN
# CE QU'ON VÉRIFIE :
#   - statut → rejected
#   - incident_id généré automatiquement
#   - compteur rejected +1
# SWAGGER          : POST /machine/test → result: "fail" + SN
#                    → observer le rejet + incident_id dans la réponse
# ─────────────────────────────────────────────────────────────────
def test_machine_fail():
    global fail_sn
    fail_sn = all_sns[1]

    r = httpx.post(f"{BASE_URL}/machine/test", json={
        "serial_number": fail_sn,
        "station_id": "STATION-01",
        "result": "fail"
    })

    assert r.status_code == 200
    data = r.json()

    assert data["result"] == "❌ FAIL"
    assert data["status"] == "rejected"
    assert data["incident_id"].startswith("INC-")

    print(f"\n✅ FAIL → {fail_sn} | STATION-01")
    print(f"   Incident créé : {data['incident_id']}")


# ─────────────────────────────────────────────────────────────────
# TEST 5 — Vérifier les compteurs après pass + fail
# CE QU'ON VÉRIFIE : pending=8, passed=1, rejected=1
# SWAGGER          : GET /stock/{product_id} → observer les compteurs
# ─────────────────────────────────────────────────────────────────
def test_stock_counters_updated():
    r = httpx.get(f"{BASE_URL}/stock/{product_id}")

    assert r.status_code == 200
    data = r.json()

    assert data["total_pending"] == 8
    assert data["total_passed"] == 1
    assert data["total_rejected"] == 1

    print(f"\n✅ Compteurs corrects — pending: 8 | passed: 1 | rejected: 1")


# ─────────────────────────────────────────────────────────────────
# TEST 6 — Vérifier le rapport du SN rejeté
# CE QU'ON VÉRIFIE : incident présent avec station + date + produit
# SWAGGER          : GET /rapports/{fail_sn} → voir rapport complet
# ─────────────────────────────────────────────────────────────────
def test_rapport_sn_rejete():
    r = httpx.get(f"{BASE_URL}/rapports/{fail_sn}")

    assert r.status_code == 200
    data = r.json()

    assert data["status"] == "rejected"
    assert data["incident"] is not None
    assert data["incident"]["station_id"] == "STATION-01"
    assert data["incident"]["product_name"] == "Paracetamol 500mg"

    print(f"\n✅ Rapport SN rejeté :")
    print(f"   SN       : {fail_sn}")
    print(f"   Produit  : {data['product_name']}")
    print(f"   Station  : {data['incident']['station_id']}")
    print(f"   Date     : {data['incident']['detected_at']}")
    print(f"   Incident : {data['incident']['incident_id']}")


# ─────────────────────────────────────────────────────────────────
# TEST 7 — Vérifier le rapport du SN passé (pas d'incident)
# CE QU'ON VÉRIFIE : status = passed, incident = null
# SWAGGER          : GET /rapports/{pass_sn} → pas d'incident
# ─────────────────────────────────────────────────────────────────
def test_rapport_sn_passe():
    r = httpx.get(f"{BASE_URL}/rapports/{pass_sn}")

    assert r.status_code == 200
    data = r.json()

    assert data["status"] == "passed"
    assert data["incident"] is None

    print(f"\n✅ Rapport SN passé : {pass_sn} — aucun incident")


# ─────────────────────────────────────────────────────────────────
# TEST 8 — Voir tous les rapports d'incidents
# CE QU'ON VÉRIFIE : 1 incident enregistré au total
# SWAGGER          : GET /rapports → voir tous les rejets
# ─────────────────────────────────────────────────────────────────
def test_all_rapports():
    r = httpx.get(f"{BASE_URL}/rapports")

    assert r.status_code == 200
    assert r.json()["total_incidents"] >= 1

    inc = r.json()["incidents"][0]
    print(f"\n✅ Rapport global — {r.json()['total_incidents']} incident(s)")
    print(f"   {inc['incident_id']} | {inc['serial_number']} | {inc['station_id']} | {inc['detected_at']}")


# ─────────────────────────────────────────────────────────────────
# TEST 9 — SN invalide retourne 404
# CE QU'ON VÉRIFIE : SN inconnu = 404
# SWAGGER          : POST /machine/test → SN-00000000-9999 → erreur rouge
# ─────────────────────────────────────────────────────────────────
def test_invalid_sn():
    r = httpx.post(f"{BASE_URL}/machine/test", json={
        "serial_number": "SN-00000000-9999",
        "station_id": "STATION-01",
        "result": "fail"
    })
    assert r.status_code == 404

    print(f"\n✅ SN inconnu retourne bien 404")


# ─────────────────────────────────────────────────────────────────
# TEST 10 — Quantité invalide (> 100) retourne 422
# CE QU'ON VÉRIFIE : quantité hors limite = 422
# SWAGGER          : POST /stock → quantity: 200 → voir erreur 422
# ─────────────────────────────────────────────────────────────────
def test_invalid_quantity():
    r = httpx.post(f"{BASE_URL}/stock", json={
        "product_name": "Test",
        "form": "comprimes",
        "batch_number": "BAT-999",
        "quantity": 200,
    })
    assert r.status_code == 422

    print(f"\n✅ Quantité > 100 retourne bien 422")

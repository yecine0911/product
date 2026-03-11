# ─────────────────────────────────────────────────────────────────
# FICHIER : test_rapports.py
# LANCER  : pytest test_rapports.py -v -s
# PRÉREQUIS : uvicorn main:app --reload  (dans un autre terminal)
# ─────────────────────────────────────────────────────────────────

import httpx
import json

BASE_URL = "http://localhost:8000"

# Variables partagées
product_id  = None
all_sns     = []
rapport_id  = None
hash_avant  = None

BATCH = "BAT-TEST-01"
OPERATEUR = "Ali Ben Salah"

# ─────────────────────────────────────────────────────────────────
# TEST 1 — Créer un stock de 5 comprimés
# ─────────────────────────────────────────────────────────────────
def test_create_stock():
    global product_id, all_sns

    r = httpx.post(f"{BASE_URL}/stock", json={
        "product_name": "Paracetamol 500mg",
        "form": "comprimes",
        "batch_number": BATCH,
        "quantity": 5
    })

    assert r.status_code == 200
    product_id = r.json()["product_id"]
    all_sns = r.json()["serial_numbers"]
    assert len(all_sns) == 5

    print(f"\n✅ Stock créé : {product_id} | 5 SN générés")


# ─────────────────────────────────────────────────────────────────
# TEST 2 — Machine : 3 PASS + 2 FAIL
# ─────────────────────────────────────────────────────────────────
def test_machine_tests():
    for sn in all_sns[:3]:
        r = httpx.post(f"{BASE_URL}/machine/test", json={
            "serial_number": sn, "station_id": "STATION-01", "result": "pass"
        })
        assert r.json()["result"] == "✅ PASS"

    for sn in all_sns[3:]:
        r = httpx.post(f"{BASE_URL}/machine/test", json={
            "serial_number": sn, "station_id": "STATION-02", "result": "fail"
        })
        assert r.json()["result"] == "❌ FAIL"

    print(f"\n✅ 3 PASS + 2 FAIL enregistrés avec logs horodatés")


# ─────────────────────────────────────────────────────────────────
# TEST 3 — Vérifier les logs horodatés
# CE QU'ON VÉRIFIE : chaque test a généré un log avec timestamp
# SWAGGER          : GET /logs → observer chaque action horodatée
# ─────────────────────────────────────────────────────────────────
def test_logs_horodates():
    r = httpx.get(f"{BASE_URL}/logs")
    assert r.status_code == 200

    logs = r.json()["logs"]
    assert len(logs) >= 5   # 1 création + 3 pass + 2 fail + 2 rejets auto

    # Vérifier que chaque log a un timestamp
    for log in logs:
        assert "timestamp" in log
        assert "action" in log
        assert "detail" in log
        assert log["timestamp"] != ""

    print(f"\n✅ {len(logs)} logs horodatés trouvés")
    for log in logs:
        print(f"   [{log['timestamp']}] {log['action']} — {log['detail'][:60]}...")


# ─────────────────────────────────────────────────────────────────
# TEST 4 — Générer le rapport du lot
# CE QU'ON VÉRIFIE :
#   - Rapport contient date, opérateur, résultats
#   - Statut = NON CONFORME (car 2 rejets)
#   - Rapport de non-conformité généré automatiquement
#   - Hash d'intégrité présent
# SWAGGER          : POST /rapports/generer → batch_number + operateur
# ─────────────────────────────────────────────────────────────────
def test_generer_rapport():
    global rapport_id, hash_avant

    r = httpx.post(f"{BASE_URL}/rapports/generer", json={
        "batch_number": BATCH,
        "operateur": OPERATEUR
    })

    assert r.status_code == 200
    data = r.json()

    rapport_id = data["rapport_id"]
    hash_avant = data["hash_integrite"]

    # Vérifier contenu du rapport
    assert data["batch_number"] == BATCH
    assert data["total_unites"] == 5
    assert data["total_passes"] == 3
    assert data["total_rejetes"] == 2
    assert data["statut_conformite"] == "NON CONFORME"

    # Vérifier rapport de non-conformité généré auto
    assert data["non_conformite"] is not None
    assert data["non_conformite"]["total_rejetes"] == 2

    # Vérifier hash présent
    assert data["hash_integrite"] != ""
    assert len(data["hash_integrite"]) == 64  # SHA256

    print(f"\n✅ Rapport généré : {rapport_id}")
    print(f"   Opérateur    : {OPERATEUR}")
    print(f"   Conformité   : NON CONFORME")
    print(f"   Passés       : 3 | Rejetés : 2")
    print(f"   Hash SHA256  : {hash_avant[:20]}...")


# ─────────────────────────────────────────────────────────────────
# TEST 5 — Vérifier le contenu complet du rapport
# CE QU'ON VÉRIFIE : date, opérateur, logs, incidents présents
# SWAGGER          : GET /rapports/{rapport_id}
# ─────────────────────────────────────────────────────────────────
def test_rapport_contenu():
    r = httpx.get(f"{BASE_URL}/rapports/{rapport_id}")
    assert r.status_code == 200

    data = r.json()
    assert data["operateur"] == OPERATEUR
    assert "generated_at" in data
    assert len(data["logs"]) > 0
    assert len(data["incidents"]) == 2

    print(f"\n✅ Contenu rapport vérifié")
    print(f"   Opérateur  : {data['operateur']}")
    print(f"   Généré le  : {data['generated_at']}")
    print(f"   Logs       : {len(data['logs'])} entrées")
    print(f"   Incidents  : {len(data['incidents'])} enregistrés")


# ─────────────────────────────────────────────────────────────────
# TEST 6 — Vérifier l'intégrité (rapport non modifiable)
# CE QU'ON VÉRIFIE : hash identique à chaque consultation
# SWAGGER          : GET /rapports/{rapport_id} → vérifier hash inchangé
# ─────────────────────────────────────────────────────────────────
def test_integrite_rapport():
    r1 = httpx.get(f"{BASE_URL}/rapports/{rapport_id}")
    r2 = httpx.get(f"{BASE_URL}/rapports/{rapport_id}")

    hash1 = r1.json()["hash_integrite"]
    hash2 = r2.json()["hash_integrite"]

    assert hash1 == hash2
    assert hash1 == hash_avant

    print(f"\n✅ Intégrité vérifiée — hash identique à chaque consultation")
    print(f"   Hash : {hash1[:32]}...")


# ─────────────────────────────────────────────────────────────────
# TEST 7 — Rapport HTML accessible
# CE QU'ON VÉRIFIE : HTML généré et accessible via URL
# NAVIGATEUR       : http://localhost:8000/rapports/{rapport_id}/html
# ─────────────────────────────────────────────────────────────────
def test_rapport_html():
    r = httpx.get(f"{BASE_URL}/rapports/{rapport_id}/html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Rapport de Production GxP" in r.text
    assert "NON CONFORME" in r.text

    print(f"\n✅ Rapport HTML accessible")
    print(f"   URL : http://localhost:8000/rapports/{rapport_id}/html")
    print(f"   → Ouvrir cette URL dans le navigateur pour voir le rapport visuel")


# ─────────────────────────────────────────────────────────────────
# TEST 8 — Rapports archivés et consultables par lot
# CE QU'ON VÉRIFIE : rapport retrouvable via le numéro de lot
# SWAGGER          : GET /rapports/lot/BAT-TEST-01
# ─────────────────────────────────────────────────────────────────
def test_rapports_par_lot():
    r = httpx.get(f"{BASE_URL}/rapports/lot/{BATCH}")
    assert r.status_code == 200
    assert r.json()["total_rapports"] >= 1
    assert r.json()["batch_number"] == BATCH

    print(f"\n✅ Rapports archivés pour lot {BATCH} : {r.json()['total_rapports']} rapport(s)")


# ─────────────────────────────────────────────────────────────────
# TEST 9 — Rapport lot inconnu → 404
# CE QU'ON VÉRIFIE : lot inexistant retourne 404
# SWAGGER          : GET /rapports/lot/BAT-999 → erreur rouge
# ─────────────────────────────────────────────────────────────────
def test_rapport_lot_inconnu():
    r = httpx.get(f"{BASE_URL}/rapports/lot/BAT-999")
    assert r.status_code == 404

    print(f"\n✅ Lot inconnu retourne bien 404")
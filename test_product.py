# ─────────────────────────────────────────────────────────────────
# FICHIER : test_products.py
# LANCER  : pytest test_products.py -v -s
# PRÉREQUIS : uvicorn main:app --reload  (dans un autre terminal)
# ─────────────────────────────────────────────────────────────────

import httpx
import pytest

BASE_URL = "http://localhost:8000"

# Numéros de série partagés entre les tests
sn_1 = None
sn_2 = None
sn_3 = None
incident_id = None

# ─────────────────────────────────────────────────────────────────
# TEST 1 — Créer 3 produits
# CE QU'ON VÉRIFIE : 3 SN générés automatiquement au bon format
# SWAGGER          : POST /products × 3 → noter les 3 SN retournés
# ─────────────────────────────────────────────────────────────────
def test_create_products():
    global sn_1, sn_2, sn_3

    produits = [
        {"name": "Paracetamol 500mg", "category": "Analgésique",   "batch_number": "BAT-001", "quantity": 5000.0, "operator": "Ali"},
        {"name": "Ibuprofene 200mg",  "category": "Anti-inflammatoire", "batch_number": "BAT-002", "quantity": 3000.0, "operator": "Sara"},
        {"name": "Amoxicilline 1g",   "category": "Antibiotique",  "batch_number": "BAT-003", "quantity": 2000.0, "operator": "Ali"},
    ]

    r1 = httpx.post(f"{BASE_URL}/products", json=produits[0])
    r2 = httpx.post(f"{BASE_URL}/products", json=produits[1])
    r3 = httpx.post(f"{BASE_URL}/products", json=produits[2])

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 200

    sn_1 = r1.json()["serial_number"]
    sn_2 = r2.json()["serial_number"]
    sn_3 = r3.json()["serial_number"]

    # Vérifier format SN
    for sn in [sn_1, sn_2, sn_3]:
        assert sn.startswith("SN-")
        assert len(sn) == 16

    print(f"\n✅ 3 produits créés :")
    print(f"   {sn_1} → Paracetamol 500mg")
    print(f"   {sn_2} → Ibuprofene 200mg")
    print(f"   {sn_3} → Amoxicilline 1g")


# ─────────────────────────────────────────────────────────────────
# TEST 2 — Vérifier que les 3 produits sont en statut "pending"
# CE QU'ON VÉRIFIE : statut initial = pending pour tous
# SWAGGER          : GET /products → observer quality_status = pending
# ─────────────────────────────────────────────────────────────────
def test_all_products_pending():
    for sn in [sn_1, sn_2, sn_3]:
        r = httpx.get(f"{BASE_URL}/products/{sn}")
        assert r.status_code == 200
        assert r.json()["quality_status"] == "pending"

    print(f"\n✅ Les 3 produits sont bien en statut 'pending'")


# ─────────────────────────────────────────────────────────────────
# TEST 3 — Signaler un incident sur sn_1 (contamination, STATION-03)
# CE QU'ON VÉRIFIE :
#   - Incident créé avec ID au format INC-YYYYMMDD-XXXX
#   - Produit sn_1 automatiquement rejeté
#   - Station et type de problème bien enregistrés
# SWAGGER          : POST /incidents → entrer sn_1 + STATION-03
#                    → observer le rejet automatique dans la réponse
# ─────────────────────────────────────────────────────────────────
def test_create_incident_and_auto_reject():
    global incident_id

    incident_data = {
        "serial_number": sn_1,
        "station_id": "STATION-03",
        "problem_type": "contamination",
        "severity": "critique",
        "detected_by": "Ali Ben Salah",
        "description": "Contamination bactérienne détectée lors du contrôle qualité",
        "corrective_action": "Arrêt ligne STATION-03, nettoyage complet"
    }

    r = httpx.post(f"{BASE_URL}/incidents", json=incident_data)
    assert r.status_code == 200

    data = r.json()
    incident_id = data["incident_id"]

    # Vérifier format INC
    assert incident_id.startswith("INC-")
    # Vérifier infos enregistrées
    assert data["incident"]["station_id"] == "STATION-03"
    assert data["incident"]["problem_type"] == "contamination"
    assert data["incident"]["severity"] == "critique"
    assert data["incident"]["product_status_after"] == "rejected"

    print(f"\n✅ Incident créé : {incident_id}")
    print(f"   Station     : STATION-03")
    print(f"   Problème    : contamination critique")
    print(f"   Produit     : {sn_1} → automatiquement REJETÉ")


# ─────────────────────────────────────────────────────────────────
# TEST 4 — Vérifier que le produit est bien rejeté après incident
# CE QU'ON VÉRIFIE : quality_status = rejected sur sn_1
# SWAGGER          : GET /products/{sn_1} → voir rejected
# ─────────────────────────────────────────────────────────────────
def test_product_rejected_after_incident():
    r = httpx.get(f"{BASE_URL}/products/{sn_1}")
    assert r.status_code == 200
    assert r.json()["quality_status"] == "rejected"
    assert incident_id in r.json()["incidents"]

    print(f"\n✅ Produit {sn_1} confirmé REJETÉ")
    print(f"   Incident lié : {incident_id}")


# ─────────────────────────────────────────────────────────────────
# TEST 5 — Créer un 2ème incident (même station, type différent)
# CE QU'ON VÉRIFIE : plusieurs incidents possibles sur même station
# SWAGGER          : POST /incidents → sn_2 + STATION-03 + temperature
# ─────────────────────────────────────────────────────────────────
def test_second_incident_same_station():
    r = httpx.post(f"{BASE_URL}/incidents", json={
        "serial_number": sn_2,
        "station_id": "STATION-03",
        "problem_type": "temperature",
        "severity": "majeur",
        "detected_by": "Sara Mansour",
        "description": "Température hors limite détectée : 32°C au lieu de 25°C max",
        "corrective_action": "Recalibrage du système de refroidissement"
    })
    assert r.status_code == 200
    assert r.json()["incident"]["station_id"] == "STATION-03"

    print(f"\n✅ 2ème incident sur STATION-03 enregistré → {sn_2} rejeté")


# ─────────────────────────────────────────────────────────────────
# TEST 6 — Analyser les incidents par station (STATION-03)
# CE QU'ON VÉRIFIE : 2 incidents trouvés pour STATION-03
# SWAGGER          : GET /incidents/station/STATION-03
#                    → identifier que cette station pose problème
# ─────────────────────────────────────────────────────────────────
def test_incidents_by_station():
    r = httpx.get(f"{BASE_URL}/incidents/station/STATION-03")
    assert r.status_code == 200
    assert r.json()["total_incidents"] == 2

    print(f"\n✅ STATION-03 : {r.json()['total_incidents']} incidents détectés")
    for inc in r.json()["incidents"]:
        print(f"   → {inc['incident_id']} | {inc['problem_type']} | {inc['severity']} | {inc['detected_at']}")


# ─────────────────────────────────────────────────────────────────
# TEST 7 — Analyser les incidents par type (contamination)
# CE QU'ON VÉRIFIE : tous les produits touchés par contamination
# SWAGGER          : GET /incidents/type/contamination
#                    → voir tous les SN affectés par ce problème
# ─────────────────────────────────────────────────────────────────
def test_incidents_by_type():
    r = httpx.get(f"{BASE_URL}/incidents/type/contamination")
    assert r.status_code == 200
    assert r.json()["total_incidents"] >= 1

    print(f"\n✅ Incidents 'contamination' : {r.json()['total_incidents']} produit(s) affecté(s)")
    for p in r.json()["affected_products"]:
        print(f"   → {p['serial_number']} | {p['product_name']} | Station: {p['station_id']} | {p['detected_at']}")


# ─────────────────────────────────────────────────────────────────
# TEST 8 — Station inconnue retourne 404
# CE QU'ON VÉRIFIE : station sans incident = 404
# SWAGGER          : GET /incidents/station/STATION-99 → erreur rouge
# ─────────────────────────────────────────────────────────────────
def test_unknown_station():
    r = httpx.get(f"{BASE_URL}/incidents/station/STATION-99")
    assert r.status_code == 404

    print(f"\n✅ Station inconnue retourne bien 404")
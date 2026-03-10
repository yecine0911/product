# ─────────────────────────────────────────────────────────────────
# FICHIER : test_products.py
# RÔLE    : Tests automatiques Pytest sur les IDs produits
# LANCER  : pytest test_products.py -v
# RÉSULTAT: s'affiche dans le terminal (PASSED / FAILED)
#
# ⚠️  IMPORTANT : le serveur FastAPI doit tourner AVANT de lancer
#     les tests → uvicorn main:app --reload (dans un autre terminal)
# ─────────────────────────────────────────────────────────────────

import httpx

# URL de base du serveur FastAPI local
BASE_URL = "http://localhost:8000"


# ─────────────────────────────────────────────────────────────────
# TEST 1 : Lister tous les produits
# CE QU'ON VÉRIFIE : le serveur répond 200 + la liste n'est pas vide
# RÉSULTAT ATTENDU : ✅ PASSED
# SWAGGER          : GET /products → même réponse visible manuellement
# ─────────────────────────────────────────────────────────────────
def test_get_all_products():
    response = httpx.get(f"{BASE_URL}/products")
    assert response.status_code == 200
    assert response.json()["total"] > 0


# ─────────────────────────────────────────────────────────────────
# TEST 2 : Chercher un produit qui EXISTE (PRD-001)
# CE QU'ON VÉRIFIE : retourne bien le bon nom de produit
# RÉSULTAT ATTENDU : ✅ PASSED
# SWAGGER          : GET /products/PRD-001 → même réponse
# ─────────────────────────────────────────────────────────────────
def test_get_existing_product():
    response = httpx.get(f"{BASE_URL}/products/PRD-001")
    assert response.status_code == 200
    assert response.json()["name"] == "Paracetamol 500mg"


# ─────────────────────────────────────────────────────────────────
# TEST 3 : Chercher un produit qui N'EXISTE PAS (PRD-999)
# CE QU'ON VÉRIFIE : retourne bien une erreur 404
# RÉSULTAT ATTENDU : ✅ PASSED
# SWAGGER          : GET /products/PRD-999 → voir l'erreur 404 en rouge
# ─────────────────────────────────────────────────────────────────
def test_get_nonexistent_product():
    response = httpx.get(f"{BASE_URL}/products/PRD-999")
    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────
# TEST 4 : Ajouter un nouveau produit (PRD-100)
# CE QU'ON VÉRIFIE : produit ajouté → récupérable ensuite
# RÉSULTAT ATTENDU : ✅ PASSED
# SWAGGER          : POST /products/PRD-100?name=Aspirine → puis GET
# ─────────────────────────────────────────────────────────────────
def test_add_new_product():
    response = httpx.post(f"{BASE_URL}/products/PRD-100?name=Aspirine 100mg")
    assert response.status_code == 200
    assert response.json()["product_id"] == "PRD-100"

    # Vérifier que le produit est bien récupérable maintenant
    check = httpx.get(f"{BASE_URL}/products/PRD-100")
    assert check.status_code == 200
    assert check.json()["name"] == "Aspirine 100mg"


# ─────────────────────────────────────────────────────────────────
# TEST 5 : Ajouter un produit avec un ID qui EXISTE DÉJÀ
# CE QU'ON VÉRIFIE : retourne erreur 400 (doublon interdit)
# RÉSULTAT ATTENDU : ✅ PASSED
# SWAGGER          : POST /products/PRD-001 → voir erreur 400 en rouge
# ─────────────────────────────────────────────────────────────────
def test_add_duplicate_product():
    response = httpx.post(f"{BASE_URL}/products/PRD-001?name=Doublon Test")
    assert response.status_code == 400


# ─────────────────────────────────────────────────────────────────
# TEST 6 : Supprimer un produit existant (PRD-003)
# CE QU'ON VÉRIFIE : supprimé → n'existe plus → 404 après suppression
# RÉSULTAT ATTENDU : ✅ PASSED
# SWAGGER          : DELETE /products/PRD-003 → puis GET pour confirmer
# ─────────────────────────────────────────────────────────────────
def test_delete_existing_product():
    response = httpx.delete(f"{BASE_URL}/products/PRD-003")
    assert response.status_code == 200

    # Vérifier que le produit est bien supprimé
    check = httpx.get(f"{BASE_URL}/products/PRD-003")
    assert check.status_code == 404


# ─────────────────────────────────────────────────────────────────
# TEST 7 : Supprimer un produit qui N'EXISTE PAS
# CE QU'ON VÉRIFIE : retourne erreur 404
# RÉSULTAT ATTENDU : ✅ PASSED
# SWAGGER          : DELETE /products/PRD-999 → voir erreur 404
# ─────────────────────────────────────────────────────────────────
def test_delete_nonexistent_product():
    response = httpx.delete(f"{BASE_URL}/products/PRD-999")
    assert response.status_code == 404
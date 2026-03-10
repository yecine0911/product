# ─────────────────────────────────────────────────────────────────
# FICHIER : main.py
# RÔLE    : Serveur FastAPI avec gestion simple des produits
# LANCER  : uvicorn main:app --reload
# SWAGGER : http://localhost:8000/docs  ← tester manuellement ici
# ─────────────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Test Produits Pharmaceutiques",
    description="Tester les IDs produits manuellement ici dans Swagger",
    version="1.0.0"
)

# ─── Base de données fictive en mémoire ───────────────────────────
# Pas de vraie BDD — juste un dictionnaire Python
# Clé = ID produit | Valeur = nom du produit
products = {
    "PRD-001": "Paracetamol 500mg",
    "PRD-002": "Ibuprofene 200mg",
    "PRD-003": "Amoxicilline 1g",
}

# ─────────────────────────────────────────────────────────────────
# ENDPOINT 1 : Récupérer tous les produits
# CE QU'ON ATTEND : retourner la liste complète des 3 produits
# TEST PYTEST     : vérifie status 200 + que la liste n'est pas vide
# SWAGGER         : cliquer "Try it out" → "Execute" → voir la liste
# ─────────────────────────────────────────────────────────────────
@app.get("/products", summary="Lister tous les produits", tags=["Produits"])
def get_all_products():
    return {"total": len(products), "products": products}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 2 : Récupérer un produit par son ID
# CE QU'ON ATTEND : retourner le produit si l'ID existe
# TEST PYTEST     : vérifie PRD-001 existe + PRD-999 retourne 404
# SWAGGER         : entrer "PRD-001" dans le champ → observer réponse
# ─────────────────────────────────────────────────────────────────
@app.get("/products/{product_id}", summary="Chercher un produit par ID", tags=["Produits"])
def get_product(product_id: str):
    if product_id not in products:
        raise HTTPException(
            status_code=404,
            detail=f"Produit '{product_id}' introuvable."
        )
    return {"product_id": product_id, "name": products[product_id]}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 3 : Ajouter un nouveau produit
# CE QU'ON ATTEND : ajouter le produit et retourner confirmation
# TEST PYTEST     : vérifie que le produit ajouté est bien récupérable
# SWAGGER         : entrer un ID + nom → vérifier ajout avec GET
# ─────────────────────────────────────────────────────────────────
@app.post("/products/{product_id}", summary="Ajouter un produit", tags=["Produits"])
def add_product(product_id: str, name: str):
    if product_id in products:
        raise HTTPException(
            status_code=400,
            detail=f"Produit '{product_id}' existe déjà."
        )
    products[product_id] = name
    return {"message": "Produit ajouté", "product_id": product_id, "name": name}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 4 : Supprimer un produit
# CE QU'ON ATTEND : supprimer et confirmer, sinon 404
# TEST PYTEST     : supprime PRD-003 → vérifie qu'il n'existe plus
# SWAGGER         : entrer "PRD-003" → Execute → puis GET pour confirmer
# ─────────────────────────────────────────────────────────────────
@app.delete("/products/{product_id}", summary="Supprimer un produit", tags=["Produits"])
def delete_product(product_id: str):
    if product_id not in products:
        raise HTTPException(
            status_code=404,
            detail=f"Produit '{product_id}' introuvable."
        )
    del products[product_id]
    return {"message": f"Produit '{product_id}' supprimé avec succès."}
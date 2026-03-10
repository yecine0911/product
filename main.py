# ─────────────────────────────────────────────────────────────────
# FICHIER : main.py
# LIGNE   : Formes Sèches (comprimés, gélules)
# LANCER  : uvicorn main:app --reload
# SWAGGER : http://localhost:8000/docs
#
# FLUX COMPLET :
#   1. POST /stock          → créer un produit + quantité → SN générés auto
#   2. GET  /stock          → voir tous les produits + total SN
#   3. GET  /stock/{id}     → voir un produit + tous ses SN
#   4. POST /machine/test   → machine envoie pass/fail + SN + station
#                             → si FAIL : rejet auto + incident enregistré
#   5. GET  /rapports       → voir tous les incidents (SN, station, date...)
#   6. GET  /rapports/{SN}  → rapport complet d'un SN spécifique
# ─────────────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

app = FastAPI(
    title="MES — Ligne Formes Sèches (Comprimés / Gélules)",
    description="""
## 🏭 Ligne de Production — Formes Sèches

### Flux de test recommandé dans Swagger :

**Étape 1 — Créer le stock**
- `POST /stock` → entrer le produit + quantité → SN générés automatiquement

**Étape 2 — Voir le stock**
- `GET /stock` → voir tous les produits et leur total SN
- `GET /stock/{product_id}` → voir tous les SN d'un produit

**Étape 3 — Simuler la machine**
- `POST /machine/test` → envoyer pass/fail + SN + station
- Si **fail** → produit rejeté automatiquement + incident créé

**Étape 4 — Consulter les rapports**
- `GET /rapports` → tous les incidents enregistrés
- `GET /rapports/{serial_number}` → rapport complet d'un SN
    """,
    version="1.0.0"
)

# ─── Stockage en mémoire ──────────────────────────────────────────
# stock_items   : tous les SN générés    (clé = SN)
# stock_batches : les produits créés     (clé = product_id)
# incidents     : les incidents          (clé = incident_id)

stock_items   = {}
stock_batches = {}
incidents     = {}

# ─── Modèles ──────────────────────────────────────────────────────

class StockCreate(BaseModel):
    product_name: str
    form: str          # comprimes ou gelules
    batch_number: str
    quantity: int      # nombre d'unités (max 100 pour les tests)

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_name": "Paracetamol 500mg",
                "form": "comprimes",
                "batch_number": "BAT-001",
                "quantity": 20,
            }
        }
    }

class MachineTest(BaseModel):
    serial_number: str
    station_id: str
    result: str        # "pass" ou "fail"

    model_config = {
        "json_schema_extra": {
            "example": {
                "serial_number": "SN-20260310-0005",
                "station_id": "STATION-01",
                "result": "fail"
            }
        }
    }

# ─── Utilitaires ──────────────────────────────────────────────────
def generate_product_id():
    return f"PRD-{str(uuid.uuid4())[:6].upper()}"

def generate_incident_id():
    return f"INC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

# ─────────────────────────────────────────────────────────────────
# ENDPOINT 1 — Créer un stock
# CE QU'ON ATTEND :
#   - Un product_id généré automatiquement
#   - Un SN unique par unité (ex: 20 unités = 20 SN)
#   - Format SN : SN-YYYYMMDD-0001 ... SN-YYYYMMDD-0020
# TEST PYTEST    : vérifier que le nombre de SN = quantité saisie
# SWAGGER        : entrer produit + quantity: 20 → observer 20 SN générés
# ─────────────────────────────────────────────────────────────────
@app.post("/stock", summary="Créer un stock → génère un SN par unité", tags=["Stock"])
def create_stock(data: StockCreate):

    if data.quantity < 1 or data.quantity > 100:
        raise HTTPException(status_code=422, detail="Quantité doit être entre 1 et 100 unités.")

    if data.form not in ["comprimes", "gelules"]:
        raise HTTPException(status_code=422, detail="Forme invalide. Valeurs acceptées : comprimes, gelules")

    # Générer le product_id
    product_id = generate_product_id()
    date_str = datetime.now().strftime("%Y%m%d")

    # Générer un SN par unité
    serial_numbers = []
    for i in range(1, data.quantity + 1):
        sn = f"SN-{date_str}-{str(i).zfill(4)}"
        serial_numbers.append(sn)
        stock_items[sn] = {
            "serial_number": sn,
            "product_id": product_id,
            "product_name": data.product_name,
            "form": data.form,
            "batch_number": data.batch_number,
                "status": "pending",
            "created_at": datetime.now().isoformat(),
            "incident_id": None
        }

    # Enregistrer le batch produit
    stock_batches[product_id] = {
        "product_id": product_id,
        "product_name": data.product_name,
        "form": data.form,
        "batch_number": data.batch_number,
        "quantity": data.quantity,
        "created_at": datetime.now().isoformat(),
        "serial_numbers": serial_numbers,
        "total_pending": data.quantity,
        "total_passed": 0,
        "total_rejected": 0
    }

    return {
        "message": f"Stock créé — {data.quantity} SN générés automatiquement",
        "product_id": product_id,
        "product_name": data.product_name,
        "form": data.form,
        "batch_number": data.batch_number,
        "quantity": data.quantity,
        "serial_numbers": serial_numbers
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 2 — Voir tous les produits en stock
# CE QU'ON ATTEND : liste des produits + total SN par statut
# TEST PYTEST    : vérifier total_pending = quantity après création
# SWAGGER        : Execute → voir résumé de chaque produit
# ─────────────────────────────────────────────────────────────────
@app.get("/stock", summary="Voir tous les produits en stock", tags=["Stock"])
def get_all_stock():
    if not stock_batches:
        return {"message": "Stock vide. Créez un stock via POST /stock.", "total_products": 0, "products": []}
    return {
        "total_products": len(stock_batches),
        "products": list(stock_batches.values())
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 3 — Voir un produit et tous ses SN
# CE QU'ON ATTEND : détail du produit + liste de tous ses SN + statuts
# TEST PYTEST    : vérifier que les SN du produit sont bien listés
# SWAGGER        : copier product_id depuis GET /stock → coller ici
# ─────────────────────────────────────────────────────────────────
@app.get("/stock/{product_id}", summary="Voir un produit et tous ses SN", tags=["Stock"])
def get_product_stock(product_id: str):
    if product_id not in stock_batches:
        raise HTTPException(status_code=404, detail=f"Produit '{product_id}' introuvable.")

    batch = stock_batches[product_id]
    # Récupérer le statut actuel de chaque SN
    units = [stock_items[sn] for sn in batch["serial_numbers"] if sn in stock_items]

    return {
        "product_id": product_id,
        "product_name": batch["product_name"],
        "batch_number": batch["batch_number"],
        "total_units": batch["quantity"],
        "total_pending": batch["total_pending"],
        "total_passed": batch["total_passed"],
        "total_rejected": batch["total_rejected"],
        "units": units
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 4 — Résultat de test machine (pass / fail)
# CE QU'ON ATTEND :
#   - PASS → statut SN passe à "passed"
#   - FAIL → statut SN passe à "rejected" + incident créé automatiquement
# TEST PYTEST    : envoyer fail → vérifier rejected + incident généré
# SWAGGER        : copier un SN → result: "fail" → observer rejet auto
# ─────────────────────────────────────────────────────────────────
@app.post("/machine/test", summary="Résultat machine → pass/fail par SN", tags=["Machine"])
def machine_test(data: MachineTest):

    if data.serial_number not in stock_items:
        raise HTTPException(status_code=404, detail=f"SN '{data.serial_number}' introuvable.")

    if data.result not in ["pass", "fail"]:
        raise HTTPException(status_code=422, detail="Résultat invalide. Valeurs acceptées : pass, fail")

    item = stock_items[data.serial_number]
    product_id = item["product_id"]

    # ── CAS PASS ──────────────────────────────────────────────────
    if data.result == "pass":
        item["status"] = "passed"
        stock_batches[product_id]["total_pending"] -= 1
        stock_batches[product_id]["total_passed"] += 1
        return {
            "result": "✅ PASS",
            "serial_number": data.serial_number,
            "station_id": data.station_id,
            "product_name": item["product_name"],
            "status": "passed",
            "tested_at": datetime.now().isoformat()
        }

    # ── CAS FAIL → rejet automatique + incident ───────────────────
    incident_id = generate_incident_id()
    incident = {
        "incident_id": incident_id,
        "serial_number": data.serial_number,
        "product_id": product_id,
        "product_name": item["product_name"],
        "form": item["form"],
        "batch_number": item["batch_number"],
        "station_id": data.station_id,
        "status_before": item["status"],
        "status_after": "rejected",
        "detected_at": datetime.now().isoformat()
    }

    # Enregistrer l'incident
    incidents[incident_id] = incident

    # Rejeter le SN
    item["status"] = "rejected"
    item["incident_id"] = incident_id

    # Mettre à jour les compteurs du produit
    stock_batches[product_id]["total_pending"] -= 1
    stock_batches[product_id]["total_rejected"] += 1

    return {
        "result": "❌ FAIL",
        "serial_number": data.serial_number,
        "station_id": data.station_id,
        "product_name": item["product_name"],
        "status": "rejected",
        "incident_id": incident_id,
        "tested_at": datetime.now().isoformat()
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 5 — Voir tous les rapports d'incidents
# CE QU'ON ATTEND : tous les SN rejetés avec station + date + produit
# TEST PYTEST    : vérifier total augmente après chaque fail
# SWAGGER        : Execute → analyser tous les rejets par station/date
# ─────────────────────────────────────────────────────────────────
@app.get("/rapports", summary="Tous les incidents enregistrés", tags=["Rapports"])
def get_all_rapports():
    if not incidents:
        return {"message": "Aucun incident. Envoyez un résultat 'fail' via POST /machine/test.", "total": 0, "incidents": []}
    return {
        "total_incidents": len(incidents),
        "incidents": list(incidents.values())
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 6 — Rapport complet d'un SN spécifique
# CE QU'ON ATTEND : toutes les infos du SN + son incident si rejeté
# TEST PYTEST    : vérifier incident_id présent si rejected
# SWAGGER        : copier un SN rejeté → voir rapport complet
# ─────────────────────────────────────────────────────────────────
@app.get("/rapports/{serial_number}", summary="Rapport complet d'un SN", tags=["Rapports"])
def get_rapport_by_sn(serial_number: str):
    if serial_number not in stock_items:
        raise HTTPException(status_code=404, detail=f"SN '{serial_number}' introuvable.")

    item = stock_items[serial_number]
    incident = None
    if item["incident_id"] and item["incident_id"] in incidents:
        incident = incidents[item["incident_id"]]

    return {
        "serial_number": serial_number,
        "product_name": item["product_name"],
        "batch_number": item["batch_number"],
        "form": item["form"],
        "status": item["status"],
        "created_at": item["created_at"],
        "incident": incident
    }

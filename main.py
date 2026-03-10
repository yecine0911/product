# ─────────────────────────────────────────────────────────────────
# FICHIER : main.py
# RÔLE    : Gestion produits pharmaceutiques + Incidents de fabrication
# LANCER  : uvicorn main:app --reload
# SWAGGER : http://localhost:8000/docs
# ─────────────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

app = FastAPI(
    title="MES/MOM — Produits & Incidents de Fabrication",
    description="""
## 🏭 Gestion des Produits Pharmaceutiques

### Ordre de test recommandé dans Swagger :
1. `POST /products` — Créer un produit
2. `GET /products` — Voir tous les produits
3. `POST /incidents` — Signaler un incident sur un produit → **rejet automatique**
4. `GET /incidents` — Voir tous les incidents enregistrés
5. `GET /incidents/station/{station_id}` — Voir tous les incidents d'une station
6. `GET /incidents/type/{problem_type}` — Analyser les incidents par type de problème
7. `GET /products/{serial_number}` — Vérifier que le produit est bien **rejected**
    """,
    version="1.0.0"
)

# ─── Stockage en mémoire ──────────────────────────────────────────
products = {}
incidents = {}

# ─── Modèles ──────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    category: str
    batch_number: str
    quantity: float
    operator: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Paracetamol 500mg",
                "category": "Analgésique",
                "batch_number": "BAT-001",
                "quantity": 5000.0,
                "operator": "Ali Ben Salah"
            }
        }
    }

class IncidentCreate(BaseModel):
    serial_number: str
    station_id: str
    problem_type: str
    severity: str
    detected_by: str
    description: str
    corrective_action: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "serial_number": "SN-20260310-A3F2",
                "station_id": "STATION-03",
                "problem_type": "contamination",
                "severity": "critique",
                "detected_by": "Ali Ben Salah",
                "description": "Contamination bactérienne détectée lors du contrôle qualité",
                "corrective_action": "Arrêt de la ligne STATION-03, nettoyage complet"
            }
        }
    }

# ─── Utilitaires ──────────────────────────────────────────────────
def generate_serial():
    date_part = datetime.now().strftime("%Y%m%d")
    unique_part = str(uuid.uuid4())[:4].upper()
    return f"SN-{date_part}-{unique_part}"

def generate_incident_id():
    date_part = datetime.now().strftime("%Y%m%d")
    unique_part = str(uuid.uuid4())[:4].upper()
    return f"INC-{date_part}-{unique_part}"

VALID_SEVERITIES = ["mineur", "majeur", "critique"]
VALID_PROBLEM_TYPES = ["contamination", "temperature", "poids", "ph", "emballage", "autre"]

# ─────────────────────────────────────────────────────────────────
# ENDPOINT 1 — Créer un produit
# CE QU'ON ATTEND : produit créé, SN généré auto, statut = pending
# TEST PYTEST     : vérifier format SN + statut initial = pending
# SWAGGER         : remplir le formulaire → noter le SN retourné
# ─────────────────────────────────────────────────────────────────
@app.post("/products", summary="Créer un produit", tags=["Produits"])
def create_product(data: ProductCreate):
    serial_number = generate_serial()
    product = {
        "serial_number": serial_number,
        "name": data.name,
        "category": data.category,
        "batch_number": data.batch_number,
        "quantity": data.quantity,
        "operator": data.operator,
        "manufacture_date": datetime.now().strftime("%Y-%m-%d"),
        "expiration_date": f"{datetime.now().year + 2}-{datetime.now().strftime('%m-%d')}",
        "quality_status": "pending",
        "created_at": datetime.now().isoformat(),
        "incidents": []
    }
    products[serial_number] = product
    return {"message": "Produit créé avec succès", "serial_number": serial_number, "product": product}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 2 — Lister tous les produits
# CE QU'ON ATTEND : liste complète avec statuts actuels
# TEST PYTEST     : vérifier total augmente après création
# SWAGGER         : Execute → observer les statuts (pending/rejected)
# ─────────────────────────────────────────────────────────────────
@app.get("/products", summary="Lister tous les produits", tags=["Produits"])
def get_all_products():
    if not products:
        return {"message": "Aucun produit. Créez d'abord un produit via POST /products.", "total": 0, "products": []}
    return {"total": len(products), "products": list(products.values())}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 3 — Chercher un produit par SN
# CE QU'ON ATTEND : retourner le produit + ses incidents liés
# TEST PYTEST     : après incident → vérifier statut = rejected
# SWAGGER         : coller le SN → observer si rejected après incident
# ─────────────────────────────────────────────────────────────────
@app.get("/products/{serial_number}", summary="Chercher un produit par numéro de série", tags=["Produits"])
def get_product(serial_number: str):
    if serial_number not in products:
        raise HTTPException(status_code=404, detail=f"Produit '{serial_number}' introuvable.")
    return products[serial_number]


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 4 — Signaler un incident de fabrication
# CE QU'ON ATTEND :
#   - Incident enregistré avec ID unique, date, station, type, gravité
#   - Produit automatiquement passé en "rejected"
#   - Incident lié au produit via son SN
# TEST PYTEST     : vérifier INC généré + produit rejected + lien SN
# SWAGGER         : entrer SN + station + type → observer rejet auto
# ─────────────────────────────────────────────────────────────────
@app.post("/incidents", summary="Signaler un incident → rejet automatique du produit", tags=["Incidents"])
def create_incident(data: IncidentCreate):

    # Vérifier que le produit existe
    if data.serial_number not in products:
        raise HTTPException(status_code=404, detail=f"Produit '{data.serial_number}' introuvable.")

    # Vérifier gravité valide
    if data.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=422, detail=f"Gravité invalide. Valeurs acceptées : {VALID_SEVERITIES}")

    # Vérifier type de problème valide
    if data.problem_type not in VALID_PROBLEM_TYPES:
        raise HTTPException(status_code=422, detail=f"Type invalide. Valeurs acceptées : {VALID_PROBLEM_TYPES}")

    # Générer l'incident
    incident_id = generate_incident_id()
    incident = {
        "incident_id": incident_id,
        "serial_number": data.serial_number,
        "product_name": products[data.serial_number]["name"],
        "batch_number": products[data.serial_number]["batch_number"],
        "station_id": data.station_id,
        "problem_type": data.problem_type,
        "severity": data.severity,
        "detected_by": data.detected_by,
        "description": data.description,
        "corrective_action": data.corrective_action,
        "detected_at": datetime.now().isoformat(),
        "product_status_before": products[data.serial_number]["quality_status"],
        "product_status_after": "rejected"
    }

    # Enregistrer l'incident
    incidents[incident_id] = incident

    # Rejeter automatiquement le produit
    products[data.serial_number]["quality_status"] = "rejected"
    products[data.serial_number]["incidents"].append(incident_id)

    return {
        "message": f"⚠️ Incident enregistré — Produit '{data.serial_number}' automatiquement rejeté",
        "incident_id": incident_id,
        "incident": incident
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 5 — Voir tous les incidents
# CE QU'ON ATTEND : liste complète de tous les incidents enregistrés
# TEST PYTEST     : vérifier total augmente après signalement
# SWAGGER         : Execute → analyser tous les incidents par date
# ─────────────────────────────────────────────────────────────────
@app.get("/incidents", summary="Voir tous les incidents enregistrés", tags=["Incidents"])
def get_all_incidents():
    if not incidents:
        return {"message": "Aucun incident enregistré.", "total": 0, "incidents": []}
    return {"total": len(incidents), "incidents": list(incidents.values())}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 6 — Incidents par station
# CE QU'ON ATTEND : tous les incidents d'une station spécifique
# TEST PYTEST     : créer 2 incidents STATION-01 → vérifier total = 2
# SWAGGER         : entrer "STATION-03" → voir tous ses problèmes
# UTILITÉ         : identifier si une station est source de problèmes
# ─────────────────────────────────────────────────────────────────
@app.get("/incidents/station/{station_id}", summary="Incidents par station", tags=["Analyse"])
def get_incidents_by_station(station_id: str):
    result = [i for i in incidents.values() if i["station_id"] == station_id]
    if not result:
        raise HTTPException(status_code=404, detail=f"Aucun incident trouvé pour la station '{station_id}'.")
    return {
        "station_id": station_id,
        "total_incidents": len(result),
        "incidents": result
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 7 — Incidents par type de problème
# CE QU'ON ATTEND : tous les incidents d'un type donné
# TEST PYTEST     : créer 3 incidents contamination → vérifier total = 3
# SWAGGER         : entrer "contamination" → voir tous les produits touchés
# UTILITÉ         : détecter les problèmes récurrents (analyse tendance)
# ─────────────────────────────────────────────────────────────────
@app.get("/incidents/type/{problem_type}", summary="Incidents par type de problème", tags=["Analyse"])
def get_incidents_by_type(problem_type: str):
    result = [i for i in incidents.values() if i["problem_type"] == problem_type]
    if not result:
        raise HTTPException(status_code=404, detail=f"Aucun incident de type '{problem_type}' trouvé.")

    # Résumé des produits touchés
    affected_products = [{"serial_number": i["serial_number"], "product_name": i["product_name"],
                          "station_id": i["station_id"], "detected_at": i["detected_at"]} for i in result]
    return {
        "problem_type": problem_type,
        "total_incidents": len(result),
        "affected_products": affected_products,
        "incidents": result
    }
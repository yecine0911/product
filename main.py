# ─────────────────────────────────────────────────────────────────
# FICHIER : main.py
# LIGNE   : Formes Sèches (comprimés, gélules)
# LANCER  : uvicorn main:app --reload
# SWAGGER : http://localhost:8000/docs
#
# FLUX COMPLET :
#   1. POST /stock              → créer produit + quantité → SN auto
#   2. GET  /stock              → voir tous les produits + total SN
#   3. GET  /stock/{product_id} → voir un produit + tous ses SN
#   4. POST /machine/test       → machine envoie pass/fail + SN + station
#                                 → FAIL : rejet auto + log horodaté
#   5. POST /rapports/generer   → générer rapport final (JSON + HTML)
#   6. GET  /rapports           → voir tous les rapports archivés
#   7. GET  /rapports/{id}      → consulter un rapport spécifique
#   8. GET  /rapports/lot/{batch_number} → rapports par numéro de lot
# ─────────────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid
import hashlib
import json

app = FastAPI(
    title="MES — Ligne Formes Sèches + Rapports GxP",
    description="""
## 🏭 Ligne de Production — Formes Sèches + Rapports

### Flux recommandé dans Swagger :

**Étape 1 — Stock**
- `POST /stock` → créer produit + quantité → SN générés auto

**Étape 2 — Machine**
- `POST /machine/test` → pass/fail + SN + station → log horodaté auto

**Étape 3 — Rapport**
- `POST /rapports/generer` → générer rapport JSON + HTML par lot
- `GET /rapports/{rapport_id}` → consulter le rapport
- `GET /rapports/{rapport_id}/html` → voir le rapport en HTML
- `GET /rapports/lot/{batch_number}` → tous les rapports d'un lot
    """,
    version="1.0.0"
)

# ─── Stockage en mémoire ──────────────────────────────────────────
stock_items   = {}   # clé = SN
stock_batches = {}   # clé = product_id
incidents     = {}   # clé = incident_id
logs          = []   # liste de tous les logs horodatés
rapports      = {}   # clé = rapport_id

# ─── Modèles ──────────────────────────────────────────────────────

class StockCreate(BaseModel):
    product_name: str
    form: str
    batch_number: str
    quantity: int

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_name": "Paracetamol 500mg",
                "form": "comprimes",
                "batch_number": "BAT-001",
                "quantity": 10
            }
        }
    }

class MachineTest(BaseModel):
    serial_number: str
    station_id: str
    result: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "serial_number": "SN-20260310-A1B2C3",
                "station_id": "STATION-01",
                "result": "fail"
            }
        }
    }

class RapportGenerer(BaseModel):
    batch_number: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "batch_number": "BAT-001",
            }
        }
    }

# ─── Utilitaires ──────────────────────────────────────────────────
def generate_product_id():
    return f"PRD-{str(uuid.uuid4())[:6].upper()}"

def generate_incident_id():
    return f"INC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

def generate_rapport_id():
    return f"RPT-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

def ajouter_log(action: str, detail: str):
    # Chaque action est enregistrée avec horodatage précis
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "detail": detail
    })

def generer_hash(contenu: dict) -> str:
    # Hash SHA256 pour garantir l'intégrité du rapport (non modifiable)
    contenu_str = json.dumps(contenu, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(contenu_str.encode()).hexdigest()

def generer_html(rapport: dict) -> str:
    # Générer le rapport HTML
    incidents_rows = ""
    for inc in rapport["incidents"]:
        incidents_rows += f"""
        <tr>
            <td>{inc['incident_id']}</td>
            <td>{inc['serial_number']}</td>
            <td>{inc['station_id']}</td>
            <td>{inc['detected_at']}</td>
            <td><span class="rejected">REJETÉ</span></td>
        </tr>"""

    passed_rows = ""
    for sn in rapport["unites_passees"]:
        passed_rows += f"""
        <tr>
            <td>{sn}</td>
            <td><span class="passed">PASSÉ</span></td>
        </tr>"""

    conformite = "CONFORME" if rapport["total_rejetes"] == 0 else "NON CONFORME"
    conformite_class = "passed" if rapport["total_rejetes"] == 0 else "rejected"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Rapport {rapport['rapport_id']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
        h2 {{ color: #283593; margin-top: 30px; }}
        .header-box {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ background: white; padding: 15px 25px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-number {{ font-size: 2em; font-weight: bold; }}
        .passed {{ color: #2e7d32; font-weight: bold; }}
        .rejected {{ color: #c62828; font-weight: bold; }}
        .pending {{ color: #f57f17; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th {{ background: #1a237e; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f5f5f5; }}
        .conformite {{ font-size: 1.5em; font-weight: bold; padding: 15px; border-radius: 8px; text-align: center; margin: 20px 0; }}
        .hash-box {{ background: #263238; color: #80cbc4; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 0.85em; word-break: break-all; margin-top: 20px; }}
        .integrity-note {{ color: #666; font-size: 0.85em; margin-top: 5px; }}
    </style>
</head>
<body>
    <h1>📋 Rapport de Production GxP</h1>

    <div class="header-box">
        <table style="box-shadow:none;">
            <tr><th>Champ</th><th>Valeur</th></tr>
            <tr><td>Rapport ID</td><td><strong>{rapport['rapport_id']}</strong></td></tr>
            <tr><td>Numéro de lot</td><td>{rapport['batch_number']}</td></tr>
            <tr><td>Produit</td><td>{rapport['product_name']}</td></tr>
                <tr><td>Date génération</td><td>{rapport['generated_at']}</td></tr>
        </table>
    </div>

    <div class="stats">
        <div class="stat"><div class="stat-number">{rapport['total_unites']}</div>Unités totales</div>
        <div class="stat"><div class="stat-number passed">{rapport['total_passes']}</div>Passées ✅</div>
        <div class="stat"><div class="stat-number rejected">{rapport['total_rejetes']}</div>Rejetées ❌</div>
        <div class="stat"><div class="stat-number pending">{rapport['total_pending']}</div>Non testées</div>
    </div>

    <div class="conformite {conformite_class}">
        Statut de conformité : {conformite}
    </div>

    <h2>❌ Incidents enregistrés</h2>
    <table>
        <tr><th>Incident ID</th><th>Numéro de série</th><th>Station</th><th>Date détection</th><th>Statut</th></tr>
        {incidents_rows if incidents_rows else '<tr><td colspan="5" style="text-align:center">Aucun incident</td></tr>'}
    </table>

    <h2>✅ Unités passées</h2>
    <table>
        <tr><th>Numéro de série</th><th>Statut</th></tr>
        {passed_rows if passed_rows else '<tr><td colspan="2" style="text-align:center">Aucune unité passée</td></tr>'}
    </table>

    <h2>📝 Logs horodatés</h2>
    <table>
        <tr><th>Timestamp</th><th>Action</th><th>Détail</th></tr>
        {''.join(f"<tr><td>{l['timestamp']}</td><td>{l['action']}</td><td>{l['detail']}</td></tr>" for l in rapport['logs'])}
    </table>

    <h2>🔒 Intégrité du rapport</h2>
    <div class="hash-box">
        SHA256 : {rapport['hash_integrite']}
    </div>
    <p class="integrity-note">Ce hash garantit que le rapport n'a pas été modifié après génération.</p>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 1 — Créer un stock
# CE QU'ON ATTEND : SN unique par unité générés automatiquement
# LOG             : action "STOCK_CREE" enregistrée avec horodatage
# SWAGGER         : remplir formulaire → observer SN générés
# ─────────────────────────────────────────────────────────────────
@app.post("/stock", summary="Créer un stock → SN générés automatiquement", tags=["Stock"])
def create_stock(data: StockCreate):
    if data.quantity < 1 or data.quantity > 100:
        raise HTTPException(status_code=422, detail="Quantité doit être entre 1 et 100.")
    if data.form not in ["comprimes", "gelules"]:
        raise HTTPException(status_code=422, detail="Forme invalide. Valeurs : comprimes, gelules")

    product_id = generate_product_id()
    date_str = datetime.now().strftime("%Y%m%d")

    serial_numbers = []
    for _ in range(data.quantity):
        sn = f"SN-{date_str}-{str(uuid.uuid4())[:6].upper()}"
        while sn in stock_items:
            sn = f"SN-{date_str}-{str(uuid.uuid4())[:6].upper()}"
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

    ajouter_log("STOCK_CREE", f"Produit: {data.product_name} | Lot: {data.batch_number} | Quantité: {data.quantity} unités | product_id: {product_id}")

    return {
        "message": f"Stock créé — {data.quantity} SN générés",
        "product_id": product_id,
        "product_name": data.product_name,
        "batch_number": data.batch_number,
        "quantity": data.quantity,
        "serial_numbers": serial_numbers
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 2 — Voir tous les produits en stock
# ─────────────────────────────────────────────────────────────────
@app.get("/stock", summary="Voir tous les produits en stock", tags=["Stock"])
def get_all_stock():
    if not stock_batches:
        return {"message": "Stock vide.", "total_products": 0, "products": []}
    return {"total_products": len(stock_batches), "products": list(stock_batches.values())}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 3 — Voir un produit par product_id
# ─────────────────────────────────────────────────────────────────
@app.get("/stock/{product_id}", summary="Voir un produit et tous ses SN", tags=["Stock"])
def get_product_stock(product_id: str):
    if product_id not in stock_batches:
        raise HTTPException(status_code=404, detail=f"Produit '{product_id}' introuvable.")
    batch = stock_batches[product_id]
    units = [stock_items[sn] for sn in batch["serial_numbers"] if sn in stock_items]
    return {**batch, "units": units}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 4 — Résultat machine (pass / fail)
# CE QU'ON ATTEND :
#   PASS → statut passed + log horodaté
#   FAIL → statut rejected + incident + log horodaté
# SWAGGER         : copier SN → result: fail → observer rejet + log
# ─────────────────────────────────────────────────────────────────
@app.post("/machine/test", summary="Résultat machine pass/fail → log horodaté auto", tags=["Machine"])
def machine_test(data: MachineTest):
    if data.serial_number not in stock_items:
        raise HTTPException(status_code=404, detail=f"SN '{data.serial_number}' introuvable.")
    if data.result not in ["pass", "fail"]:
        raise HTTPException(status_code=422, detail="Résultat invalide. Valeurs : pass, fail")

    item = stock_items[data.serial_number]
    product_id = item["product_id"]

    if data.result == "pass":
        item["status"] = "passed"
        stock_batches[product_id]["total_pending"] -= 1
        stock_batches[product_id]["total_passed"] += 1
        ajouter_log("TEST_PASS", f"SN: {data.serial_number} | Station: {data.station_id} | Produit: {item['product_name']} | Lot: {item['batch_number']}")
        return {
            "result": "✅ PASS",
            "serial_number": data.serial_number,
            "station_id": data.station_id,
            "product_name": item["product_name"],
            "status": "passed",
            "tested_at": datetime.now().isoformat()
        }

    # FAIL → rejet + incident + log
    incident_id = generate_incident_id()
    incident = {
        "incident_id": incident_id,
        "serial_number": data.serial_number,
        "product_id": product_id,
        "product_name": item["product_name"],
        "batch_number": item["batch_number"],
        "station_id": data.station_id,
        "detected_at": datetime.now().isoformat()
    }
    incidents[incident_id] = incident
    item["status"] = "rejected"
    item["incident_id"] = incident_id
    stock_batches[product_id]["total_pending"] -= 1
    stock_batches[product_id]["total_rejected"] += 1

    ajouter_log("TEST_FAIL", f"SN: {data.serial_number} | Station: {data.station_id} | Produit: {item['product_name']} | Lot: {item['batch_number']} | Incident: {incident_id}")
    ajouter_log("REJET_AUTO", f"SN: {data.serial_number} automatiquement rejeté suite à l'échec du test en {data.station_id}")

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
# ENDPOINT 5 — Générer un rapport par lot
# CE QU'ON ATTEND :
#   - Rapport JSON avec date, opérateur, résultats, logs, incidents
#   - Rapport HTML généré automatiquement
#   - Hash SHA256 pour garantir l'intégrité (non modifiable)
#   - Rapport de non-conformité si rejets > 0
# SWAGGER         : entrer batch_number → rapport généré
# ─────────────────────────────────────────────────────────────────
@app.post("/rapports/generer", summary="Générer un rapport GxP par numéro de lot", tags=["Rapports"])
def generer_rapport(data: RapportGenerer):

    # Trouver le produit correspondant au lot
    batch = next((b for b in stock_batches.values() if b["batch_number"] == data.batch_number), None)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Lot '{data.batch_number}' introuvable.")

    # Récupérer les unités du lot
    units = [stock_items[sn] for sn in batch["serial_numbers"] if sn in stock_items]
    unites_passees = [u["serial_number"] for u in units if u["status"] == "passed"]
    unites_rejetees = [u["serial_number"] for u in units if u["status"] == "rejected"]
    unites_pending = [u["serial_number"] for u in units if u["status"] == "pending"]

    # Incidents liés au lot
    incidents_lot = [i for i in incidents.values() if i["batch_number"] == data.batch_number]

    # Logs liés au lot
    logs_lot = [l for l in logs if data.batch_number in l["detail"]]

    # Statut de conformité
    conforme = len(unites_rejetees) == 0
    statut_conformite = "CONFORME" if conforme else "NON CONFORME"

    rapport_id = generate_rapport_id()
    generated_at = datetime.now().isoformat()

    # Construire le rapport
    contenu_rapport = {
        "rapport_id": rapport_id,
        "batch_number": data.batch_number,
        "product_name": batch["product_name"],
        "product_id": batch["product_id"],
        "form": batch["form"],
        "generated_at": generated_at,
        "statut_conformite": statut_conformite,
        "total_unites": batch["quantity"],
        "total_passes": len(unites_passees),
        "total_rejetes": len(unites_rejetees),
        "total_pending": len(unites_pending),
        "unites_passees": unites_passees,
        "unites_rejetees": unites_rejetees,
        "incidents": incidents_lot,
        "logs": logs_lot,
        "non_conformite": None if conforme else {
            "type": "RAPPORT_NON_CONFORMITE",
            "batch_number": data.batch_number,
            "total_rejetes": len(unites_rejetees),
            "incidents": incidents_lot,
            "generated_at": generated_at
        }
    }

    # Hash SHA256 pour intégrité (rapport non modifiable après génération)
    contenu_rapport["hash_integrite"] = generer_hash(contenu_rapport)

    # Générer HTML
    html_contenu = generer_html(contenu_rapport)
    contenu_rapport["html"] = html_contenu

    # Archiver le rapport
    rapports[rapport_id] = contenu_rapport

    ajouter_log("RAPPORT_GENERE", f"Rapport: {rapport_id} | Lot: {data.batch_number} | Conformité: {statut_conformite}")

    return {
        "message": "Rapport généré avec succès",
        "rapport_id": rapport_id,
        "batch_number": data.batch_number,
        "statut_conformite": statut_conformite,
        "total_unites": batch["quantity"],
        "total_passes": len(unites_passees),
        "total_rejetes": len(unites_rejetees),
        "total_pending": len(unites_pending),
        "non_conformite": contenu_rapport["non_conformite"],
        "hash_integrite": contenu_rapport["hash_integrite"],
        "html_url": f"/rapports/{rapport_id}/html",
        "rapport_complet_url": f"/rapports/{rapport_id}"
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 6 — Voir tous les rapports archivés
# CE QU'ON ATTEND : liste de tous les rapports générés
# SWAGGER         : Execute → voir tous les rapports archivés
# ─────────────────────────────────────────────────────────────────
@app.get("/rapports", summary="Tous les rapports archivés", tags=["Rapports"])
def get_all_rapports():
    if not rapports:
        return {"message": "Aucun rapport. Générez via POST /rapports/generer.", "total": 0, "rapports": []}
    # Résumé sans le HTML pour ne pas surcharger la réponse
    resume = [{k: v for k, v in r.items() if k != "html"} for r in rapports.values()]
    return {"total": len(rapports), "rapports": resume}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 7 — Consulter un rapport JSON
# CE QU'ON ATTEND : rapport complet avec logs, incidents, hash
# SWAGGER         : copier rapport_id → voir rapport complet
# ─────────────────────────────────────────────────────────────────
@app.get("/rapports/{rapport_id}", summary="Consulter un rapport complet (JSON)", tags=["Rapports"])
def get_rapport(rapport_id: str):
    if rapport_id not in rapports:
        raise HTTPException(status_code=404, detail=f"Rapport '{rapport_id}' introuvable.")
    return {k: v for k, v in rapports[rapport_id].items() if k != "html"}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 8 — Voir le rapport en HTML
# CE QU'ON ATTEND : page HTML avec tableau des résultats
# SWAGGER         : copier rapport_id → ouvrir l'URL dans le navigateur
# ─────────────────────────────────────────────────────────────────
@app.get("/rapports/{rapport_id}/html", summary="Voir le rapport en HTML", tags=["Rapports"], response_class=HTMLResponse)
def get_rapport_html(rapport_id: str):
    if rapport_id not in rapports:
        raise HTTPException(status_code=404, detail=f"Rapport '{rapport_id}' introuvable.")
    return HTMLResponse(content=rapports[rapport_id]["html"])


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 9 — Rapports par numéro de lot
# CE QU'ON ATTEND : tous les rapports générés pour un lot donné
# SWAGGER         : entrer batch_number → voir historique des rapports
# ─────────────────────────────────────────────────────────────────
@app.get("/rapports/lot/{batch_number}", summary="Rapports archivés par numéro de lot", tags=["Rapports"])
def get_rapports_par_lot(batch_number: str):
    result = [{k: v for k, v in r.items() if k != "html"} for r in rapports.values() if r["batch_number"] == batch_number]
    if not result:
        raise HTTPException(status_code=404, detail=f"Aucun rapport pour le lot '{batch_number}'.")
    return {"batch_number": batch_number, "total_rapports": len(result), "rapports": result}


# ─────────────────────────────────────────────────────────────────
# ENDPOINT 10 — Voir tous les logs horodatés
# CE QU'ON ATTEND : historique complet de toutes les actions
# SWAGGER         : Execute → voir chaque action avec timestamp
# ─────────────────────────────────────────────────────────────────
@app.get("/logs", summary="Tous les logs horodatés", tags=["Logs"])
def get_all_logs():
    if not logs:
        return {"message": "Aucun log.", "total": 0, "logs": []}
    return {"total": len(logs), "logs": logs}

# ─────────────────────────────────────────────────────────────────
# ENDPOINT DEBUG — Voir tout ce qui est en mémoire
# CE QU'ON ATTEND : snapshot complet de l'état du serveur
# UTILITÉ         : vérifier immédiatement si la création a réussi
#                   voir combien de produits, SN, incidents en mémoire
# SWAGGER         : GET /debug → Execute → voir tout l'état actuel
# ─────────────────────────────────────────────────────────────────
@app.get("/debug", summary="🔍 Voir tout ce qui est en mémoire", tags=["Debug"])
def debug_memory():
    return {
        "etat_memoire": {
            "total_produits_stock": len(stock_batches),
            "total_unites_sn": len(stock_items),
            "total_incidents": len(incidents),
            "total_rapports": len(rapports),
            "total_logs": len(logs)
        },
        "produits": [
            {
                "product_id": b["product_id"],
                "product_name": b["product_name"],
                "batch_number": b["batch_number"],
                "quantity": b["quantity"],
                "created_at": b["created_at"],
                "pending": b["total_pending"],
                "passed": b["total_passed"],
                "rejected": b["total_rejected"],
                "premiers_sns": b["serial_numbers"][:3],
                "derniers_sns": b["serial_numbers"][-3:]
            }
            for b in stock_batches.values()
        ],
        "derniers_logs": logs[-5:] if logs else [],
        "derniers_incidents": list(incidents.values())[-3:] if incidents else []
    }


# ─────────────────────────────────────────────────────────────────
# ENDPOINT DEBUG SN — Vérifier un SN spécifique
# CE QU'ON ATTEND : confirmer que le SN existe et voir son état
# UTILITÉ         : après création, coller un SN et vérifier
# SWAGGER         : GET /debug/sn/{serial_number} → état du SN
# ─────────────────────────────────────────────────────────────────
@app.get("/debug/sn/{serial_number}", summary="🔍 Vérifier un SN spécifique", tags=["Debug"])
def debug_sn(serial_number: str):
    if serial_number not in stock_items:
        return {
            "existe": False,
            "serial_number": serial_number,
            "message": "❌ Ce SN n'existe pas en mémoire — vérifiez que vous avez bien créé le stock"
        }
    item = stock_items[serial_number]
    return {
        "existe": True,
        "serial_number": serial_number,
        "product_name": item["product_name"],
        "batch_number": item["batch_number"],
        "status": item["status"],
        "created_at": item["created_at"],
        "incident_id": item["incident_id"],
        "message": "✅ SN trouvé en mémoire"
    }
"""Application de gestion d'activité freelance.

Outil mono-utilisateur pour une enseignante vacataire indépendante :
écoles, contacts, modules, contrats, séances, documents financiers
(devis / factures), paiements et relances.

Pile : Flask + SQLite (sans ORM). Pages rendues côté serveur (Jinja2).
Voir fiche_projet_gestion_freelance_v2.md pour le cahier des charges.
"""

from datetime import date, timedelta

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

import db
from db import execute, query

app = Flask(__name__)
app.secret_key = "dev-secret-key-a-changer-en-production"

# Initialise la base (schéma + seed) au chargement du module : fonctionne
# aussi bien en local que sous le WSGI de PythonAnywhere.
with app.app_context():
    db.init_db()

# Ferme la connexion SQLite à la fin de chaque requête.
app.teardown_appcontext(db.close_db)


# Libellés lisibles réutilisés dans les templates --------------------------------
TYPES_DOC = {"D": "Devis", "FP": "Facture provisoire", "F": "Facture définitive"}
NIVEAUX_RELANCE = {
    1: "Rappel courtois",
    2: "Relance ferme",
    3: "Relance urgente",
    4: "Mise en demeure",
}


@app.context_processor
def inject_globals():
    """Variables disponibles dans tous les templates."""
    return {
        "TYPES_DOC": TYPES_DOC,
        "NIVEAUX_RELANCE": NIVEAUX_RELANCE,
        "annee_courante": date.today().year,
    }


# =============================================================================
#  TABLEAU DE BORD
# =============================================================================

@app.get("/")
def dashboard():
    annee = date.today().year
    today = date.today().isoformat()

    # Encours = total facturé (FP/F émises) - paiements reçus
    encours = query(
        """
        SELECT COALESCE(SUM(lf.montant), 0)
                 - COALESCE((SELECT SUM(p.montant) FROM paiements p
                             JOIN factures f2 ON f2.id = p.facture_id
                             WHERE f2.type_doc IN ('FP','F') AND f2.statut != 'annulee'), 0)
               AS encours
        FROM lignes_facture lf
        JOIN factures f ON f.id = lf.facture_id
        WHERE f.type_doc IN ('FP','F') AND f.statut != 'annulee'
        """,
        one=True,
    )["encours"]

    # Factures en retard : échéance dépassée et reste dû > 0
    factures = query(
        """
        SELECT f.*, e.code_court,
               (SELECT COALESCE(SUM(montant),0) FROM lignes_facture WHERE facture_id = f.id) AS total,
               (SELECT COALESCE(SUM(montant),0) FROM paiements      WHERE facture_id = f.id) AS paye
        FROM factures f
        JOIN ecoles e ON e.id = f.ecole_id
        WHERE f.type_doc IN ('FP','F') AND f.statut != 'annulee'
        """
    )
    en_retard = [
        f for f in factures
        if f["date_echeance"] and f["date_echeance"] < today
        and (f["total"] - f["paye"]) > 0.001
    ]

    # Heures restantes sur l'année (contractualisées - réalisées)
    heures = query(
        """
        SELECT
          COALESCE((SELECT SUM(lc.volume_horaire)
                    FROM lignes_contrat lc
                    JOIN contrats c ON c.id = lc.contrat_id
                    WHERE c.annee = ? AND c.statut != 'annule'), 0) AS contract,
          COALESCE((SELECT SUM(s.nb_heures)
                    FROM seances s
                    JOIN lignes_contrat lc ON lc.id = s.ligne_contrat_id
                    JOIN contrats c ON c.id = lc.contrat_id
                    WHERE c.annee = ? AND s.statut = 'realisee'), 0) AS faites
        """,
        (annee, annee),
        one=True,
    )
    heures_restantes = (heures["contract"] or 0) - (heures["faites"] or 0)

    # Devis en attente de réponse (non annulés)
    devis_attente = query(
        "SELECT COUNT(*) AS n FROM factures WHERE type_doc = 'D' AND statut NOT IN ('annulee')",
        one=True,
    )["n"]

    # Chiffre d'affaires encaissé sur l'année
    ca_encaisse = query(
        """
        SELECT COALESCE(SUM(p.montant), 0) AS ca
        FROM paiements p
        JOIN factures f ON f.id = p.facture_id
        WHERE f.annee = ? AND f.type_doc IN ('FP','F')
        """,
        (annee,),
        one=True,
    )["ca"]

    return render_template(
        "dashboard.html",
        encours=encours,
        en_retard=en_retard,
        heures_restantes=heures_restantes,
        heures_contract=heures["contract"] or 0,
        heures_faites=heures["faites"] or 0,
        devis_attente=devis_attente,
        ca_encaisse=ca_encaisse,
    )


# =============================================================================
#  ÉCOLES
# =============================================================================

@app.get("/ecoles")
def ecoles_list():
    ecoles = query("SELECT * FROM ecoles ORDER BY code_court")
    return render_template("ecoles_list.html", ecoles=ecoles)


@app.route("/ecoles/nouveau", methods=["GET", "POST"])
def ecole_new():
    if request.method == "POST":
        execute(
            """INSERT INTO ecoles
               (code_court, code_numerique, adresse, code_postal, ville, telephone, email, site_web, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                request.form["code_court"].strip(),
                request.form["code_numerique"],
                request.form.get("adresse"),
                request.form.get("code_postal"),
                request.form.get("ville"),
                request.form.get("telephone"),
                request.form.get("email"),
                request.form.get("site_web"),
                request.form.get("notes"),
            ),
        )
        flash("École créée.", "success")
        return redirect(url_for("ecoles_list"))
    return render_template("ecole_form.html", ecole=None)


@app.route("/ecoles/<int:eid>/modifier", methods=["GET", "POST"])
def ecole_edit(eid):
    ecole = query("SELECT * FROM ecoles WHERE id = ?", (eid,), one=True)
    if ecole is None:
        flash("École introuvable.", "error")
        return redirect(url_for("ecoles_list"))
    if request.method == "POST":
        execute(
            """UPDATE ecoles SET
               code_court=?, code_numerique=?, adresse=?, code_postal=?, ville=?,
               telephone=?, email=?, site_web=?, notes=? WHERE id=?""",
            (
                request.form["code_court"].strip(),
                request.form["code_numerique"],
                request.form.get("adresse"),
                request.form.get("code_postal"),
                request.form.get("ville"),
                request.form.get("telephone"),
                request.form.get("email"),
                request.form.get("site_web"),
                request.form.get("notes"),
                eid,
            ),
        )
        flash("École mise à jour.", "success")
        return redirect(url_for("ecoles_list"))
    return render_template("ecole_form.html", ecole=ecole)


@app.get("/ecoles/<int:eid>")
def ecole_detail(eid):
    ecole = query("SELECT * FROM ecoles WHERE id = ?", (eid,), one=True)
    if ecole is None:
        flash("École introuvable.", "error")
        return redirect(url_for("ecoles_list"))
    contacts = query("SELECT * FROM contacts WHERE ecole_id = ? ORDER BY nom", (eid,))
    contrats = query(
        "SELECT * FROM contrats WHERE ecole_id = ? ORDER BY annee DESC", (eid,)
    )
    return render_template(
        "ecole_detail.html", ecole=ecole, contacts=contacts, contrats=contrats
    )


@app.post("/ecoles/<int:eid>/supprimer")
def ecole_delete(eid):
    execute("DELETE FROM ecoles WHERE id = ?", (eid,))
    flash("École supprimée.", "success")
    return redirect(url_for("ecoles_list"))


# =============================================================================
#  CONTACTS
# =============================================================================

@app.get("/contacts")
def contacts_list():
    contacts = query(
        """SELECT c.*, e.code_court FROM contacts c
           JOIN ecoles e ON e.id = c.ecole_id ORDER BY e.code_court, c.nom"""
    )
    return render_template("contacts_list.html", contacts=contacts)


@app.route("/contacts/nouveau", methods=["GET", "POST"])
def contact_new():
    if request.method == "POST":
        execute(
            """INSERT INTO contacts (ecole_id, nom, prenom, fonction, telephone, email, decisionnaire)
               VALUES (?,?,?,?,?,?,?)""",
            (
                request.form["ecole_id"],
                request.form["nom"].strip(),
                request.form.get("prenom"),
                request.form.get("fonction"),
                request.form.get("telephone"),
                request.form.get("email"),
                1 if request.form.get("decisionnaire") else 0,
            ),
        )
        flash("Contact créé.", "success")
        return redirect(url_for("contacts_list"))
    ecoles = query("SELECT id, code_court FROM ecoles ORDER BY code_court")
    return render_template(
        "contact_form.html", contact=None, ecoles=ecoles,
        ecole_id=request.args.get("ecole_id", type=int),
    )


@app.route("/contacts/<int:cid>/modifier", methods=["GET", "POST"])
def contact_edit(cid):
    contact = query("SELECT * FROM contacts WHERE id = ?", (cid,), one=True)
    if contact is None:
        flash("Contact introuvable.", "error")
        return redirect(url_for("contacts_list"))
    if request.method == "POST":
        execute(
            """UPDATE contacts SET ecole_id=?, nom=?, prenom=?, fonction=?,
               telephone=?, email=?, decisionnaire=? WHERE id=?""",
            (
                request.form["ecole_id"],
                request.form["nom"].strip(),
                request.form.get("prenom"),
                request.form.get("fonction"),
                request.form.get("telephone"),
                request.form.get("email"),
                1 if request.form.get("decisionnaire") else 0,
                cid,
            ),
        )
        flash("Contact mis à jour.", "success")
        return redirect(url_for("contacts_list"))
    ecoles = query("SELECT id, code_court FROM ecoles ORDER BY code_court")
    return render_template("contact_form.html", contact=contact, ecoles=ecoles, ecole_id=None)


@app.post("/contacts/<int:cid>/supprimer")
def contact_delete(cid):
    execute("DELETE FROM contacts WHERE id = ?", (cid,))
    flash("Contact supprimé.", "success")
    return redirect(url_for("contacts_list"))


# =============================================================================
#  MODULES
# =============================================================================

@app.get("/modules")
def modules_list():
    modules = query(
        """SELECT m.*, n.libelle AS niveau, s.code AS specialite
           FROM modules m
           LEFT JOIN niveaux n     ON n.id = m.niveau_id
           LEFT JOIN specialites s ON s.id = m.specialite_id
           ORDER BY m.code_module"""
    )
    return render_template("modules_list.html", modules=modules)


def _module_refs():
    return (
        query("SELECT id, libelle FROM niveaux ORDER BY libelle"),
        query("SELECT id, code, libelle FROM specialites ORDER BY code"),
    )


@app.route("/modules/nouveau", methods=["GET", "POST"])
def module_new():
    if request.method == "POST":
        execute(
            """INSERT INTO modules
               (code_module, intitule, niveau_id, specialite_id, volume_horaire_ref, tarif_horaire_ref)
               VALUES (?,?,?,?,?,?)""",
            (
                request.form["code_module"].strip(),
                request.form["intitule"].strip(),
                request.form.get("niveau_id") or None,
                request.form.get("specialite_id") or None,
                request.form.get("volume_horaire_ref") or 0,
                request.form.get("tarif_horaire_ref") or 0,
            ),
        )
        flash("Module créé.", "success")
        return redirect(url_for("modules_list"))
    niveaux, specialites = _module_refs()
    return render_template("module_form.html", module=None, niveaux=niveaux, specialites=specialites)


@app.route("/modules/<int:mid>/modifier", methods=["GET", "POST"])
def module_edit(mid):
    module = query("SELECT * FROM modules WHERE id = ?", (mid,), one=True)
    if module is None:
        flash("Module introuvable.", "error")
        return redirect(url_for("modules_list"))
    if request.method == "POST":
        execute(
            """UPDATE modules SET code_module=?, intitule=?, niveau_id=?,
               specialite_id=?, volume_horaire_ref=?, tarif_horaire_ref=? WHERE id=?""",
            (
                request.form["code_module"].strip(),
                request.form["intitule"].strip(),
                request.form.get("niveau_id") or None,
                request.form.get("specialite_id") or None,
                request.form.get("volume_horaire_ref") or 0,
                request.form.get("tarif_horaire_ref") or 0,
                mid,
            ),
        )
        flash("Module mis à jour.", "success")
        return redirect(url_for("modules_list"))
    niveaux, specialites = _module_refs()
    return render_template("module_form.html", module=module, niveaux=niveaux, specialites=specialites)


@app.post("/modules/<int:mid>/supprimer")
def module_delete(mid):
    try:
        execute("DELETE FROM modules WHERE id = ?", (mid,))
        flash("Module supprimé.", "success")
    except Exception:
        flash("Impossible de supprimer : ce module est utilisé dans un contrat.", "error")
    return redirect(url_for("modules_list"))


# =============================================================================
#  RÉFÉRENTIELS (niveaux & spécialités)
# =============================================================================

@app.get("/referentiels")
def referentiels():
    niveaux = query("SELECT * FROM niveaux ORDER BY libelle")
    specialites = query("SELECT * FROM specialites ORDER BY code")
    return render_template("referentiels.html", niveaux=niveaux, specialites=specialites)


@app.post("/referentiels/niveaux")
def niveau_add():
    libelle = request.form.get("libelle", "").strip()
    if libelle:
        try:
            execute("INSERT INTO niveaux (libelle) VALUES (?)", (libelle,))
            flash("Niveau ajouté.", "success")
        except Exception:
            flash("Ce niveau existe déjà.", "error")
    return redirect(url_for("referentiels"))


@app.post("/referentiels/niveaux/<int:nid>/supprimer")
def niveau_delete(nid):
    execute("DELETE FROM niveaux WHERE id = ?", (nid,))
    flash("Niveau supprimé.", "success")
    return redirect(url_for("referentiels"))


@app.post("/referentiels/specialites")
def specialite_add():
    code = request.form.get("code", "").strip()
    libelle = request.form.get("libelle", "").strip() or code
    if code:
        try:
            execute(
                "INSERT INTO specialites (code, libelle, mutualise) VALUES (?,?,?)",
                (code, libelle, 1 if "+" in code else 0),
            )
            flash("Spécialité ajoutée.", "success")
        except Exception:
            flash("Cette spécialité existe déjà.", "error")
    return redirect(url_for("referentiels"))


@app.post("/referentiels/specialites/<int:sid>/supprimer")
def specialite_delete(sid):
    execute("DELETE FROM specialites WHERE id = ?", (sid,))
    flash("Spécialité supprimée.", "success")
    return redirect(url_for("referentiels"))


# =============================================================================
#  CONTRATS & LIGNES DE CONTRAT
# =============================================================================

@app.get("/contrats")
def contrats_list():
    contrats = query(
        """SELECT c.*, e.code_court,
                  (SELECT COALESCE(SUM(volume_horaire),0) FROM lignes_contrat WHERE contrat_id = c.id) AS heures
           FROM contrats c JOIN ecoles e ON e.id = c.ecole_id
           ORDER BY c.annee DESC, e.code_court"""
    )
    return render_template("contrats_list.html", contrats=contrats)


@app.route("/contrats/nouveau", methods=["GET", "POST"])
def contrat_new():
    if request.method == "POST":
        cid = execute(
            """INSERT INTO contrats (ecole_id, annee, type_contractualisation, reference, statut, date_creation, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (
                request.form["ecole_id"],
                request.form["annee"],
                request.form["type_contractualisation"],
                request.form.get("reference"),
                request.form["statut"],
                request.form.get("date_creation") or date.today().isoformat(),
                request.form.get("notes"),
            ),
        )
        flash("Contrat créé. Ajoutez maintenant ses lignes.", "success")
        return redirect(url_for("contrat_detail", cid=cid))
    ecoles = query("SELECT id, code_court FROM ecoles ORDER BY code_court")
    return render_template("contrat_form.html", contrat=None, ecoles=ecoles)


@app.route("/contrats/<int:cid>/modifier", methods=["GET", "POST"])
def contrat_edit(cid):
    contrat = query("SELECT * FROM contrats WHERE id = ?", (cid,), one=True)
    if contrat is None:
        flash("Contrat introuvable.", "error")
        return redirect(url_for("contrats_list"))
    if request.method == "POST":
        execute(
            """UPDATE contrats SET ecole_id=?, annee=?, type_contractualisation=?,
               reference=?, statut=?, date_creation=?, notes=? WHERE id=?""",
            (
                request.form["ecole_id"],
                request.form["annee"],
                request.form["type_contractualisation"],
                request.form.get("reference"),
                request.form["statut"],
                request.form.get("date_creation"),
                request.form.get("notes"),
                cid,
            ),
        )
        flash("Contrat mis à jour.", "success")
        return redirect(url_for("contrat_detail", cid=cid))
    ecoles = query("SELECT id, code_court FROM ecoles ORDER BY code_court")
    return render_template("contrat_form.html", contrat=contrat, ecoles=ecoles)


@app.get("/contrats/<int:cid>")
def contrat_detail(cid):
    contrat = query(
        "SELECT c.*, e.code_court FROM contrats c JOIN ecoles e ON e.id = c.ecole_id WHERE c.id = ?",
        (cid,), one=True,
    )
    if contrat is None:
        flash("Contrat introuvable.", "error")
        return redirect(url_for("contrats_list"))
    lignes = query(
        """SELECT lc.*, m.code_module, m.intitule,
                  (SELECT COALESCE(SUM(nb_heures),0) FROM seances
                   WHERE ligne_contrat_id = lc.id AND statut='realisee') AS heures_faites
           FROM lignes_contrat lc
           JOIN modules m ON m.id = lc.module_id
           WHERE lc.contrat_id = ? ORDER BY m.code_module""",
        (cid,),
    )
    modules = query("SELECT id, code_module, intitule, tarif_horaire_ref, volume_horaire_ref FROM modules ORDER BY code_module")
    return render_template("contrat_detail.html", contrat=contrat, lignes=lignes, modules=modules)


@app.post("/contrats/<int:cid>/lignes")
def ligne_contrat_add(cid):
    execute(
        """INSERT INTO lignes_contrat (contrat_id, module_id, type_cours, volume_horaire, tarif_horaire)
           VALUES (?,?,?,?,?)""",
        (
            cid,
            request.form["module_id"],
            request.form["type_cours"],
            request.form.get("volume_horaire") or 0,
            request.form.get("tarif_horaire") or 0,
        ),
    )
    flash("Ligne ajoutée au contrat.", "success")
    return redirect(url_for("contrat_detail", cid=cid))


@app.post("/lignes-contrat/<int:lid>/supprimer")
def ligne_contrat_delete(lid):
    ligne = query("SELECT contrat_id FROM lignes_contrat WHERE id = ?", (lid,), one=True)
    execute("DELETE FROM lignes_contrat WHERE id = ?", (lid,))
    flash("Ligne supprimée.", "success")
    return redirect(url_for("contrat_detail", cid=ligne["contrat_id"]) if ligne else url_for("contrats_list"))


@app.post("/contrats/<int:cid>/supprimer")
def contrat_delete(cid):
    execute("DELETE FROM contrats WHERE id = ?", (cid,))
    flash("Contrat supprimé.", "success")
    return redirect(url_for("contrats_list"))


# =============================================================================
#  SÉANCES
# =============================================================================

@app.get("/seances")
def seances_list():
    seances = query(
        """SELECT s.*, m.code_module, e.code_court, c.annee
           FROM seances s
           JOIN lignes_contrat lc ON lc.id = s.ligne_contrat_id
           JOIN modules m  ON m.id = lc.module_id
           JOIN contrats c ON c.id = lc.contrat_id
           JOIN ecoles e   ON e.id = c.ecole_id
           ORDER BY s.date_seance DESC"""
    )
    return render_template("seances_list.html", seances=seances)


def _lignes_contrat_options():
    return query(
        """SELECT lc.id, m.code_module, m.intitule, e.code_court, c.annee
           FROM lignes_contrat lc
           JOIN modules m  ON m.id = lc.module_id
           JOIN contrats c ON c.id = lc.contrat_id
           JOIN ecoles e   ON e.id = c.ecole_id
           ORDER BY c.annee DESC, e.code_court, m.code_module"""
    )


@app.route("/seances/nouveau", methods=["GET", "POST"])
def seance_new():
    if request.method == "POST":
        execute(
            """INSERT INTO seances (ligne_contrat_id, date_seance, nb_heures, statut, notes)
               VALUES (?,?,?,?,?)""",
            (
                request.form["ligne_contrat_id"],
                request.form["date_seance"],
                request.form.get("nb_heures") or 0,
                request.form["statut"],
                request.form.get("notes"),
            ),
        )
        flash("Séance enregistrée.", "success")
        return redirect(url_for("seances_list"))
    return render_template(
        "seance_form.html", seance=None, lignes=_lignes_contrat_options(),
        ligne_id=request.args.get("ligne_id", type=int),
    )


@app.route("/seances/<int:sid>/modifier", methods=["GET", "POST"])
def seance_edit(sid):
    seance = query("SELECT * FROM seances WHERE id = ?", (sid,), one=True)
    if seance is None:
        flash("Séance introuvable.", "error")
        return redirect(url_for("seances_list"))
    if request.method == "POST":
        execute(
            """UPDATE seances SET ligne_contrat_id=?, date_seance=?, nb_heures=?, statut=?, notes=? WHERE id=?""",
            (
                request.form["ligne_contrat_id"],
                request.form["date_seance"],
                request.form.get("nb_heures") or 0,
                request.form["statut"],
                request.form.get("notes"),
                sid,
            ),
        )
        flash("Séance mise à jour.", "success")
        return redirect(url_for("seances_list"))
    return render_template(
        "seance_form.html", seance=seance, lignes=_lignes_contrat_options(), ligne_id=None
    )


@app.post("/seances/<int:sid>/supprimer")
def seance_delete(sid):
    execute("DELETE FROM seances WHERE id = ?", (sid,))
    flash("Séance supprimée.", "success")
    return redirect(url_for("seances_list"))


# =============================================================================
#  DOCUMENTS FINANCIERS (devis & factures)
# =============================================================================

@app.get("/factures")
def factures_list():
    rows = query(
        """SELECT f.*, e.code_court,
                  (SELECT COALESCE(SUM(montant),0) FROM lignes_facture WHERE facture_id = f.id) AS total,
                  (SELECT COALESCE(SUM(montant),0) FROM paiements      WHERE facture_id = f.id) AS paye
           FROM factures f JOIN ecoles e ON e.id = f.ecole_id
           ORDER BY f.annee DESC, f.compteur DESC"""
    )
    return render_template("factures_list.html", factures=rows)


@app.route("/factures/nouveau", methods=["GET", "POST"])
def facture_new():
    """Crée un devis (D) ou une facture provisoire (FP) avec numérotation auto."""
    if request.method == "POST":
        type_doc = request.form["type_doc"]  # 'D' ou 'FP' uniquement à la création
        annee = int(request.form["annee"])
        ecole = query("SELECT * FROM ecoles WHERE id = ?", (request.form["ecole_id"],), one=True)

        serie = db.serie_for(type_doc)
        compteur = db.prochain_compteur(annee, serie)
        numero = db.construire_numero(type_doc, annee, ecole["code_numerique"], compteur)

        delai = query("SELECT delai_paiement FROM parametres WHERE id = 1", one=True)
        delai_jours = (delai["delai_paiement"] if delai and delai["delai_paiement"] else 30)
        emission = request.form.get("date_emission") or date.today().isoformat()
        echeance = (date.fromisoformat(emission) + timedelta(days=delai_jours)).isoformat()

        fid = execute(
            """INSERT INTO factures
               (type_doc, annee, ecole_id, contact_id, contrat_id, compteur, numero,
                date_emission, date_echeance, statut, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                type_doc, annee, ecole["id"],
                request.form.get("contact_id") or None,
                request.form.get("contrat_id") or None,
                compteur, numero, emission, echeance, "emise",
                request.form.get("notes"),
            ),
        )
        flash(f"Document {numero} créé.", "success")
        return redirect(url_for("facture_detail", fid=fid))

    ecoles = query("SELECT id, code_court, code_numerique FROM ecoles ORDER BY code_court")
    contacts = query(
        "SELECT c.id, c.nom, c.prenom, c.ecole_id FROM contacts c ORDER BY c.nom"
    )
    contrats = query(
        "SELECT c.id, c.annee, c.ecole_id, e.code_court FROM contrats c JOIN ecoles e ON e.id=c.ecole_id ORDER BY c.annee DESC"
    )
    return render_template(
        "facture_form.html", ecoles=ecoles, contacts=contacts, contrats=contrats
    )


@app.get("/factures/<int:fid>")
def facture_detail(fid):
    facture = query(
        """SELECT f.*, e.code_court, e.code_numerique
           FROM factures f JOIN ecoles e ON e.id = f.ecole_id WHERE f.id = ?""",
        (fid,), one=True,
    )
    if facture is None:
        flash("Document introuvable.", "error")
        return redirect(url_for("factures_list"))
    lignes = query("SELECT * FROM lignes_facture WHERE facture_id = ? ORDER BY id", (fid,))
    paiements = query("SELECT * FROM paiements WHERE facture_id = ? ORDER BY date_paiement", (fid,))
    relances = query("SELECT * FROM relances WHERE facture_id = ? ORDER BY niveau", (fid,))
    parametres = query("SELECT * FROM parametres WHERE id = 1", one=True)
    contact = (
        query("SELECT * FROM contacts WHERE id = ?", (facture["contact_id"],), one=True)
        if facture["contact_id"] else None
    )
    # Lignes de contrat proposables pour pré-remplir une ligne de facture
    lignes_contrat = []
    if facture["contrat_id"]:
        lignes_contrat = query(
            """SELECT lc.id, m.code_module, m.intitule, lc.volume_horaire, lc.tarif_horaire
               FROM lignes_contrat lc JOIN modules m ON m.id = lc.module_id
               WHERE lc.contrat_id = ?""",
            (facture["contrat_id"],),
        )
    return render_template(
        "facture_detail.html",
        facture=facture, lignes=lignes, paiements=paiements, relances=relances,
        parametres=parametres, contact=contact, lignes_contrat=lignes_contrat,
        total=db.total_facture(fid), paye=db.total_paye(fid), reste=db.reste_du(fid),
    )


@app.post("/factures/<int:fid>/lignes")
def ligne_facture_add(fid):
    qte = float(request.form.get("quantite_heures") or 0)
    pu = float(request.form.get("prix_unitaire") or 0)
    execute(
        """INSERT INTO lignes_facture
           (facture_id, ligne_contrat_id, description, quantite_heures, prix_unitaire, montant)
           VALUES (?,?,?,?,?,?)""",
        (
            fid,
            request.form.get("ligne_contrat_id") or None,
            request.form["description"].strip(),
            qte, pu, round(qte * pu, 2),
        ),
    )
    flash("Ligne ajoutée.", "success")
    return redirect(url_for("facture_detail", fid=fid))


@app.post("/lignes-facture/<int:lid>/supprimer")
def ligne_facture_delete(lid):
    ligne = query("SELECT facture_id FROM lignes_facture WHERE id = ?", (lid,), one=True)
    execute("DELETE FROM lignes_facture WHERE id = ?", (lid,))
    flash("Ligne supprimée.", "success")
    return redirect(url_for("facture_detail", fid=ligne["facture_id"]) if ligne else url_for("factures_list"))


@app.post("/factures/<int:fid>/valider")
def facture_valider(fid):
    """Transforme une facture provisoire (FP) en facture définitive (F).

    Le compteur est conservé ; seul le préfixe perd son « P ». Opération tracée
    et irréversible (fiche § 2.6).
    """
    facture = query("SELECT * FROM factures WHERE id = ?", (fid,), one=True)
    if facture is None:
        flash("Document introuvable.", "error")
        return redirect(url_for("factures_list"))
    if facture["type_doc"] != "FP":
        flash("Seule une facture provisoire peut être validée.", "error")
        return redirect(url_for("facture_detail", fid=fid))
    nouveau_numero = facture["numero"].replace("FP-", "F-", 1)
    execute(
        "UPDATE factures SET type_doc='F', numero=?, date_validation=? WHERE id=?",
        (nouveau_numero, date.today().isoformat(), fid),
    )
    flash(f"Facture validée : {nouveau_numero} (définitive).", "success")
    return redirect(url_for("facture_detail", fid=fid))


@app.post("/factures/<int:fid>/annuler")
def facture_annuler(fid):
    execute("UPDATE factures SET statut='annulee' WHERE id=?", (fid,))
    flash("Document annulé.", "success")
    return redirect(url_for("facture_detail", fid=fid))


@app.post("/factures/<int:fid>/supprimer")
def facture_delete(fid):
    execute("DELETE FROM factures WHERE id = ?", (fid,))
    flash("Document supprimé.", "success")
    return redirect(url_for("factures_list"))


# =============================================================================
#  PAIEMENTS
# =============================================================================

@app.post("/factures/<int:fid>/paiements")
def paiement_add(fid):
    execute(
        """INSERT INTO paiements (facture_id, date_paiement, montant, mode, reference)
           VALUES (?,?,?,?,?)""",
        (
            fid,
            request.form["date_paiement"],
            request.form.get("montant") or 0,
            request.form["mode"],
            request.form.get("reference"),
        ),
    )
    # Passe la facture à 'payee' si entièrement réglée
    if db.reste_du(fid) <= 0.001:
        execute("UPDATE factures SET statut='payee' WHERE id=? AND statut!='annulee'", (fid,))
    flash("Paiement enregistré.", "success")
    return redirect(url_for("facture_detail", fid=fid))


@app.post("/paiements/<int:pid>/supprimer")
def paiement_delete(pid):
    p = query("SELECT facture_id FROM paiements WHERE id = ?", (pid,), one=True)
    execute("DELETE FROM paiements WHERE id = ?", (pid,))
    if p and db.reste_du(p["facture_id"]) > 0.001:
        execute("UPDATE factures SET statut='emise' WHERE id=? AND statut='payee'", (p["facture_id"],))
    flash("Paiement supprimé.", "success")
    return redirect(url_for("facture_detail", fid=p["facture_id"]) if p else url_for("factures_list"))


# =============================================================================
#  RELANCES
# =============================================================================

@app.get("/relances")
def relances_list():
    relances = query(
        """SELECT r.*, f.numero, e.code_court,
                  (SELECT COALESCE(SUM(montant),0) FROM lignes_facture WHERE facture_id = f.id) AS total,
                  (SELECT COALESCE(SUM(montant),0) FROM paiements      WHERE facture_id = f.id) AS paye
           FROM relances r
           JOIN factures f ON f.id = r.facture_id
           JOIN ecoles e   ON e.id = f.ecole_id
           ORDER BY r.statut, r.date_prevue"""
    )
    return render_template("relances_list.html", relances=relances)


@app.post("/factures/<int:fid>/relances")
def relance_add(fid):
    execute(
        """INSERT INTO relances (facture_id, niveau, date_prevue, date_envoi, statut, notes)
           VALUES (?,?,?,?,?,?)""",
        (
            fid,
            int(request.form["niveau"]),
            request.form.get("date_prevue") or None,
            request.form.get("date_envoi") or None,
            "envoyee" if request.form.get("date_envoi") else "planifiee",
            request.form.get("notes"),
        ),
    )
    flash("Relance enregistrée.", "success")
    return redirect(url_for("facture_detail", fid=fid))


@app.post("/relances/<int:rid>/envoyee")
def relance_envoyee(rid):
    r = query("SELECT facture_id FROM relances WHERE id = ?", (rid,), one=True)
    execute(
        "UPDATE relances SET statut='envoyee', date_envoi=? WHERE id=?",
        (date.today().isoformat(), rid),
    )
    flash("Relance marquée comme envoyée.", "success")
    return redirect(request.referrer or url_for("relances_list"))


@app.post("/relances/<int:rid>/supprimer")
def relance_delete(rid):
    r = query("SELECT facture_id FROM relances WHERE id = ?", (rid,), one=True)
    execute("DELETE FROM relances WHERE id = ?", (rid,))
    flash("Relance supprimée.", "success")
    return redirect(request.referrer or url_for("relances_list"))


# =============================================================================
#  PARAMÈTRES (mentions légales auto-entrepreneur)
# =============================================================================

@app.route("/parametres", methods=["GET", "POST"])
def parametres():
    if request.method == "POST":
        execute(
            """UPDATE parametres SET
               raison_sociale=?, siret=?, adresse=?, code_postal=?, ville=?,
               telephone=?, email=?, iban=?, bic=?, mention_tva=?, delai_paiement=?, penalites=?
               WHERE id=1""",
            (
                request.form.get("raison_sociale"),
                request.form.get("siret"),
                request.form.get("adresse"),
                request.form.get("code_postal"),
                request.form.get("ville"),
                request.form.get("telephone"),
                request.form.get("email"),
                request.form.get("iban"),
                request.form.get("bic"),
                request.form.get("mention_tva"),
                request.form.get("delai_paiement") or 30,
                request.form.get("penalites"),
            ),
        )
        flash("Paramètres enregistrés.", "success")
        return redirect(url_for("parametres"))
    params = query("SELECT * FROM parametres WHERE id = 1", one=True)
    return render_template("parametres.html", params=params)


if __name__ == "__main__":
    # utile en local uniquement
    app.run(host="0.0.0.0", port=5000, debug=True)

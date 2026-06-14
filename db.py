"""Couche d'accès à la base SQLite.

Centralise la connexion, l'initialisation (schéma + seed exécutés une seule
fois), quelques helpers de requête et les fonctions d'automatisation métier
(numérotation des documents, calculs de restes dus / heures restantes).
"""

import os
import sqlite3

from flask import g

# Le fichier de base vit à côté de l'application (compatible PythonAnywhere).
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "gestion_freelance.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
SEED_PATH = os.path.join(BASE_DIR, "seed.sql")

# Bases de numérotation (fiche § 3) : 'dernier' attribué, le prochain = +1.
COMPTEUR_BASE = {"devis": 1011, "facture": 8031}


# -----------------------------------------------------------------------------
#  Connexion
# -----------------------------------------------------------------------------

def get_db():
    """Renvoie la connexion liée à la requête courante (créée à la demande)."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    """Ferme la connexion en fin de requête (branché sur teardown_appcontext)."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# -----------------------------------------------------------------------------
#  Helpers de requête
# -----------------------------------------------------------------------------

def query(sql, params=(), one=False):
    """SELECT — renvoie une liste de Row, ou une seule Row si one=True."""
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    """INSERT/UPDATE/DELETE — commit et renvoie le lastrowid."""
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


# -----------------------------------------------------------------------------
#  Initialisation
# -----------------------------------------------------------------------------

def init_db():
    """Crée le schéma puis injecte le seed si la base est vierge.

    Idempotent : peut être appelé à chaque démarrage sans risque.
    """
    db = sqlite3.connect(DB_PATH)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            db.executescript(f.read())
        # Le seed n'est appliqué que si aucune école n'existe encore.
        already = db.execute("SELECT COUNT(*) FROM ecoles").fetchone()[0]
        if not already and os.path.exists(SEED_PATH):
            with open(SEED_PATH, encoding="utf-8") as f:
                db.executescript(f.read())
        db.commit()
    finally:
        db.close()


# -----------------------------------------------------------------------------
#  Automatisations métier
# -----------------------------------------------------------------------------

def serie_for(type_doc):
    """Série de compteur associée à un type de document."""
    return "devis" if type_doc == "D" else "facture"


def prochain_compteur(annee, serie):
    """Calcule, réserve et renvoie le prochain numéro de compteur.

    Le compteur est global par année et par série, sans trou ni doublon.
    """
    db = get_db()
    row = db.execute(
        "SELECT dernier FROM compteurs WHERE annee = ? AND serie = ?",
        (annee, serie),
    ).fetchone()
    if row is None:
        nouveau = COMPTEUR_BASE[serie] + 1
        db.execute(
            "INSERT INTO compteurs (annee, serie, dernier) VALUES (?, ?, ?)",
            (annee, serie, nouveau),
        )
    else:
        nouveau = row["dernier"] + 1
        db.execute(
            "UPDATE compteurs SET dernier = ? WHERE annee = ? AND serie = ?",
            (nouveau, annee, serie),
        )
    db.commit()
    return nouveau


def construire_numero(type_doc, annee, code_ecole, compteur):
    """Format : TYPE-ANNÉE-CODE_ÉCOLE-COMPTEUR (ex: FP-2026-5070-8032)."""
    return f"{type_doc}-{annee}-{code_ecole}-{compteur}"


def total_facture(facture_id):
    """Montant total d'une facture (somme des lignes)."""
    row = query(
        "SELECT COALESCE(SUM(montant), 0) AS total FROM lignes_facture WHERE facture_id = ?",
        (facture_id,),
        one=True,
    )
    return row["total"] if row else 0


def total_paye(facture_id):
    """Montant déjà encaissé pour une facture."""
    row = query(
        "SELECT COALESCE(SUM(montant), 0) AS paye FROM paiements WHERE facture_id = ?",
        (facture_id,),
        one=True,
    )
    return row["paye"] if row else 0


def reste_du(facture_id):
    """Reste dû = montant facturé - paiements reçus."""
    return total_facture(facture_id) - total_paye(facture_id)

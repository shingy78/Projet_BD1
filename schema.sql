-- =============================================================================
--  Schéma de la base — Application de gestion d'activité freelance
--  SGBD : SQLite 3
--  Conçu d'après la fiche projet (fiche_projet_gestion_freelance_v2.md)
--  12 entités métier + 2 tables techniques (compteurs, parametres)
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
--  RÉFÉRENTIELS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS niveaux (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    libelle TEXT NOT NULL UNIQUE          -- L1, L2, L3, M1, M2...
);

CREATE TABLE IF NOT EXISTS specialites (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    code    TEXT NOT NULL UNIQUE,         -- CYBER, INFRA, DEV, DATA, CYBER+INFRA (groupe mutualisé)
    libelle TEXT NOT NULL,
    mutualise INTEGER NOT NULL DEFAULT 0  -- 1 si groupe-classe mutualisé (présence d'un '+')
);

-- -----------------------------------------------------------------------------
--  TIERS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ecoles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    code_court     TEXT NOT NULL UNIQUE,           -- ISEP, EPITA...
    code_numerique INTEGER NOT NULL UNIQUE,        -- 5020, 5070 — figure dans la numérotation
    adresse        TEXT,
    code_postal    TEXT,
    ville          TEXT,
    telephone      TEXT,
    email          TEXT,
    site_web       TEXT,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ecole_id      INTEGER NOT NULL,
    nom           TEXT NOT NULL,
    prenom        TEXT,
    fonction      TEXT,
    telephone     TEXT,
    email         TEXT,
    decisionnaire INTEGER NOT NULL DEFAULT 0,      -- 1 = donneur d'ordre principal
    FOREIGN KEY (ecole_id) REFERENCES ecoles(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
--  OFFRE
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS modules (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    code_module        TEXT NOT NULL UNIQUE,
    intitule           TEXT NOT NULL,
    niveau_id          INTEGER,                    -- facultatif
    specialite_id      INTEGER,                    -- facultatif
    volume_horaire_ref REAL,                       -- volume horaire de référence
    tarif_horaire_ref  REAL,                       -- tarif horaire indicatif
    FOREIGN KEY (niveau_id)     REFERENCES niveaux(id)     ON DELETE SET NULL,
    FOREIGN KEY (specialite_id) REFERENCES specialites(id) ON DELETE SET NULL
);

-- -----------------------------------------------------------------------------
--  ENGAGEMENTS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS contrats (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    ecole_id              INTEGER NOT NULL,
    annee                 INTEGER NOT NULL,
    type_contractualisation TEXT NOT NULL DEFAULT 'contrat'
                          CHECK (type_contractualisation IN ('contrat','bon_de_commande','devis','autre')),
    reference             TEXT,
    statut                TEXT NOT NULL DEFAULT 'en_cours'
                          CHECK (statut IN ('en_cours','en_attente','termine','annule')),
    date_creation         TEXT,
    notes                 TEXT,
    FOREIGN KEY (ecole_id) REFERENCES ecoles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lignes_contrat (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contrat_id      INTEGER NOT NULL,
    module_id       INTEGER NOT NULL,
    type_cours      TEXT NOT NULL DEFAULT 'Specialite'
                    CHECK (type_cours IN ('Specialite','Commun')),  -- saisi manuellement
    volume_horaire  REAL NOT NULL DEFAULT 0,       -- heures contractualisées
    tarif_horaire   REAL NOT NULL DEFAULT 0,       -- tarif négocié (fige les conditions de l'année)
    FOREIGN KEY (contrat_id) REFERENCES contrats(id) ON DELETE CASCADE,
    FOREIGN KEY (module_id)  REFERENCES modules(id)  ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS seances (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ligne_contrat_id INTEGER NOT NULL,
    date_seance      TEXT NOT NULL,
    nb_heures        REAL NOT NULL DEFAULT 0,
    statut           TEXT NOT NULL DEFAULT 'planifiee'
                     CHECK (statut IN ('planifiee','realisee','annulee')),
    notes            TEXT,
    FOREIGN KEY (ligne_contrat_id) REFERENCES lignes_contrat(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
--  FINANCES
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS factures (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    type_doc       TEXT NOT NULL CHECK (type_doc IN ('D','FP','F')),  -- Devis / Facture provisoire / Facture définitive
    annee          INTEGER NOT NULL,
    ecole_id       INTEGER NOT NULL,
    contact_id     INTEGER,
    contrat_id     INTEGER,
    compteur       INTEGER NOT NULL,               -- compteur global par année et par série
    numero         TEXT NOT NULL UNIQUE,           -- TYPE-ANNEE-CODE_ECOLE-COMPTEUR
    date_emission  TEXT,
    date_echeance  TEXT,
    statut         TEXT NOT NULL DEFAULT 'emise'
                   CHECK (statut IN ('brouillon','emise','payee','annulee')),
    date_validation TEXT,                          -- date du passage FP -> F (irréversible)
    notes          TEXT,
    FOREIGN KEY (ecole_id)   REFERENCES ecoles(id)   ON DELETE RESTRICT,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL,
    FOREIGN KEY (contrat_id) REFERENCES contrats(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS lignes_facture (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    facture_id       INTEGER NOT NULL,
    ligne_contrat_id INTEGER,                       -- traçabilité vers la ligne de contrat
    description      TEXT NOT NULL,
    quantite_heures  REAL NOT NULL DEFAULT 0,
    prix_unitaire    REAL NOT NULL DEFAULT 0,
    montant          REAL NOT NULL DEFAULT 0,       -- = quantite_heures * prix_unitaire
    FOREIGN KEY (facture_id)       REFERENCES factures(id)       ON DELETE CASCADE,
    FOREIGN KEY (ligne_contrat_id) REFERENCES lignes_contrat(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS paiements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    facture_id    INTEGER NOT NULL,
    date_paiement TEXT NOT NULL,
    montant       REAL NOT NULL DEFAULT 0,
    mode          TEXT NOT NULL DEFAULT 'virement'
                  CHECK (mode IN ('virement','cheque','prelevement','autre')),
    reference     TEXT,
    FOREIGN KEY (facture_id) REFERENCES factures(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relances (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    facture_id  INTEGER NOT NULL,
    niveau      INTEGER NOT NULL CHECK (niveau IN (1,2,3,4)),  -- 1=rappel courtois ... 4=mise en demeure
    date_prevue TEXT,
    date_envoi  TEXT,
    statut      TEXT NOT NULL DEFAULT 'planifiee'
                CHECK (statut IN ('planifiee','envoyee')),
    notes       TEXT,
    FOREIGN KEY (facture_id) REFERENCES factures(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
--  TABLES TECHNIQUES
-- -----------------------------------------------------------------------------

-- Compteur global par année et par série de documents.
-- 'dernier' contient le dernier numéro attribué ; le prochain = dernier + 1.
-- Initialisation (fiche § 3) : devis à 1011, factures à 8031.
CREATE TABLE IF NOT EXISTS compteurs (
    annee   INTEGER NOT NULL,
    serie   TEXT NOT NULL CHECK (serie IN ('devis','facture')),
    dernier INTEGER NOT NULL,
    PRIMARY KEY (annee, serie)
);

-- Paramètres de l'auto-entrepreneur (table à ligne unique, id = 1).
-- Alimente les mentions légales des documents.
CREATE TABLE IF NOT EXISTS parametres (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    raison_sociale  TEXT,
    siret           TEXT,
    adresse         TEXT,
    code_postal     TEXT,
    ville           TEXT,
    telephone       TEXT,
    email           TEXT,
    iban            TEXT,
    bic             TEXT,
    mention_tva     TEXT,                  -- "TVA non applicable, art. 293 B du CGI"
    delai_paiement  INTEGER DEFAULT 30,    -- jours
    penalites       TEXT
);

-- -----------------------------------------------------------------------------
--  INDEX utiles
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_contacts_ecole       ON contacts(ecole_id);
CREATE INDEX IF NOT EXISTS idx_contrats_ecole        ON contrats(ecole_id);
CREATE INDEX IF NOT EXISTS idx_lignes_contrat_contrat ON lignes_contrat(contrat_id);
CREATE INDEX IF NOT EXISTS idx_seances_ligne          ON seances(ligne_contrat_id);
CREATE INDEX IF NOT EXISTS idx_factures_ecole         ON factures(ecole_id);
CREATE INDEX IF NOT EXISTS idx_lignes_facture_facture ON lignes_facture(facture_id);
CREATE INDEX IF NOT EXISTS idx_paiements_facture      ON paiements(facture_id);
CREATE INDEX IF NOT EXISTS idx_relances_facture       ON relances(facture_id);

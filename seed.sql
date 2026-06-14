-- =============================================================================
--  Données de référence (seed) — exécutées une seule fois à l'initialisation.
--  Toutes les insertions sont idempotentes (INSERT OR IGNORE).
-- =============================================================================

-- Écoles partenaires (codes numériques en service — fiche § 2.1)
INSERT OR IGNORE INTO ecoles (code_court, code_numerique, ville) VALUES
    ('ESGI',  5010, 'Paris'),
    ('ISEP',  5020, 'Paris'),
    ('EPSI',  5030, 'Paris'),
    ('IPSSI', 5040, 'Paris'),
    ('CNAM',  5050, 'Paris'),
    ('ESIEE', 5060, 'Noisy-le-Grand'),
    ('EPITA', 5070, 'Le Kremlin-Bicêtre'),
    ('EFREI', 5080, 'Villejuif');

-- Niveaux d'études
INSERT OR IGNORE INTO niveaux (libelle) VALUES
    ('L1'), ('L2'), ('L3'), ('M1'), ('M2');

-- Spécialités (avec un groupe mutualisé d'exemple)
INSERT OR IGNORE INTO specialites (code, libelle, mutualise) VALUES
    ('DEV',        'Développement logiciel',       0),
    ('CYBER',      'Cybersécurité',                 0),
    ('INFRA',      'Infrastructure & Réseaux',      0),
    ('DATA',       'Data & Intelligence artificielle', 0),
    ('CYBER+INFRA','Cybersécurité + Infrastructure (mutualisé)', 1);

-- Paramètres de l'auto-entrepreneur (ligne unique, à compléter par l'utilisatrice)
INSERT OR IGNORE INTO parametres
    (id, raison_sociale, mention_tva, delai_paiement, penalites)
VALUES
    (1,
     'Professeure d''informatique indépendante',
     'TVA non applicable, art. 293 B du CGI',
     30,
     'Pénalités de retard : 3 fois le taux d''intérêt légal. Indemnité forfaitaire de recouvrement : 40 €.');

# Fiche descriptive — Application de gestion d'activité freelance

**Projet :** Outil de gestion pour professeure d'informatique indépendante
**Statut juridique de l'utilisatrice :** auto-entrepreneur, franchise en base de TVA (art. 293 B du CGI)
**Date :** juin 2026 — *version recentrée (hors Outlook et messagerie)*

---

## 1. Contexte et objectifs

L'utilisatrice intervient comme enseignante vacataire pour le compte de plusieurs écoles d'informatique. Son activité génère un volume croissant de contrats, de modules enseignés, de séances à suivre et de documents financiers (devis, factures provisoires, factures définitives, paiements, relances). La gestion par tableur ou documents épars atteint ses limites : risque d'erreur de numérotation, perte de visibilité sur les impayés, ressaisie d'informations, suivi imprécis des heures réalisées.

L'objectif est de centraliser l'ensemble de cette activité dans une base de données structurée, dotée d'une interface de saisie agréable, qui automatise les tâches répétitives et fournit une vision claire et fiable de la situation à tout moment.

> **Périmètre de cette version.** Cette fiche décrit le cœur du projet, hors intégration Outlook et messagerie. Le rapprochement automatique des séances avec l'agenda et l'envoi automatisé des relances par e-mail sont écartés pour l'instant et feront l'objet d'une phase ultérieure (voir § 6).

### Objectifs principaux

- Centraliser les écoles partenaires, leurs contacts et les modules enseignés.
- Formaliser les engagements annuels (contrats, bons de commande, devis) et le détail des modules contractualisés.
- Produire et numéroter automatiquement les documents financiers selon une convention stricte.
- Suivre le cycle de vie des factures, depuis la facture provisoire jusqu'au paiement, en passant par les relances.
- Suivre les heures réalisées au regard des heures contractualisées.
- Disposer d'indicateurs de pilotage : heures restant à effectuer, encours, retards de paiement, chiffre d'affaires.

---

## 2. Périmètre fonctionnel

### 2.1 Gestion des écoles

Référencement des établissements partenaires avec leurs coordonnées complètes. Chaque école porte deux identifiants : un code court et un code numérique stable, ce dernier étant intégré dans la numérotation des documents financiers.

| Donnée | Précision |
|--------|-----------|
| Code court | Ex. `ISEP`, `EPITA` |
| Code numérique | Ex. 5020, 5070 — figure dans les numéros de documents |
| Coordonnées | Adresse, ville, code postal, téléphone, e-mail, site web |
| Notes | Champ libre |

Codes numériques en service : ESGI 5010, ISEP 5020, EPSI 5030, IPSSI 5040, CNAM 5050, ESIEE 5060, EPITA 5070, EFREI 5080.

### 2.2 Gestion des contacts

Interlocuteurs rattachés à chaque école : nom, prénom, fonction, coordonnées. Un indicateur « décisionnaire » permet d'identifier le donneur d'ordre principal, utile au moment d'émettre un document financier.

### 2.3 Catalogue des modules

Description des modules enseignés : code module, intitulé, niveau d'études et spécialité concernés, volume horaire de référence et tarif horaire indicatif. Le niveau et la spécialité sont facultatifs (un module peut être générique).

Les spécialités gèrent aussi les **groupes-classes mutualisés** : la notation `CYBER+INFRA` désigne un cours commun à deux spécialités, distinct d'un cours de spécialité simple.

### 2.4 Contrats et lignes de contrat

Un contrat formalise l'engagement annuel d'une école. Il accepte plusieurs formes de contractualisation (contrat, bon de commande, devis, autre) avec leurs références respectives, et porte un statut (en cours, en attente, terminé, annulé).

Chaque contrat se décompose en **lignes de contrat**, une par module contractualisé, précisant :

- le module concerné ;
- le **type de cours** (Spécialité ou Commun), sélectionné manuellement à la saisie ;
- le volume horaire total engagé ;
- le tarif horaire réellement négocié, qui peut différer du tarif standard du catalogue.

Cette structure assure une **historisation naturelle des tarifs** : chaque contrat repart de zéro pour une année donnée et fige ses conditions.

### 2.5 Séances (saisie manuelle)

Suivi des séances d'enseignement effectivement dispensées, rattachées à une ligne de contrat. Chaque séance précise sa date, son nombre d'heures et un statut (planifiée, réalisée, annulée).

La saisie est **manuelle** dans cette version. Le suivi des séances permet de comparer les heures réalisées aux heures contractualisées et de calculer le reste à effectuer, module par module.

> L'alimentation automatique de cette table depuis l'agenda Outlook est prévue dans une phase ultérieure (voir § 6) ; la structure de la table reste compatible avec cette évolution.

### 2.6 Documents financiers

Trois types de documents partagent une même logique de numérotation :

| Type | Préfixe | Série | Exemple |
|------|---------|-------|---------|
| Devis | `D` | 1000+ | `D-2026-5020-1012` |
| Facture provisoire | `FP` | 8000+ | `FP-2026-5070-8032` |
| Facture définitive | `F` | 8000+ | `F-2026-5070-8032` |

**Format :** `TYPE-ANNÉE-CODE_ÉCOLE-COMPTEUR`. Le compteur est **global par année** (toutes écoles confondues) et **incrémenté automatiquement**.

**Cycle de validation :** une facture provisoire (`FP`) devient définitive (`F`) par simple retrait du « P » ; le numéro de compteur est conservé. L'opération est tracée et irréversible.

**Régime de TVA :** en franchise en base, les montants ne portent pas de TVA. La mention légale « TVA non applicable, art. 293 B du CGI » doit figurer sur les documents.

Chaque facture se décompose en **lignes de facture** (description, quantité d'heures, prix unitaire, montant), idéalement reliées aux lignes de contrat correspondantes pour assurer la traçabilité.

### 2.7 Paiements

Enregistrement des règlements reçus par facture : date, montant, mode (virement, chèque, prélèvement, autre), référence. Un rapprochement automatique calcule le montant payé et le reste dû.

### 2.8 Relances

Suivi gradué des impayés sur quatre niveaux : rappel courtois, relance ferme, relance urgente, mise en demeure. Chaque relance porte une date prévue, une date d'envoi effective et un statut (planifiée, envoyée).

La gestion est **manuelle** dans cette version : l'utilisatrice saisit et suit ses relances, sans envoi automatisé d'e-mail.

---

## 3. Automatisations attendues

| Automatisation | Description |
|----------------|-------------|
| Numérotation des documents | Calcul du prochain numéro selon le type, l'année et le code école, en s'appuyant sur un compteur initialisé (devis à 1011, factures à 8031). |
| Validation FP → F | Transformation d'une facture provisoire en facture définitive avec conservation du numéro. |
| Calcul des restes dus | Différence entre montant facturé et somme des paiements. |
| Calcul des heures restantes | Différence entre heures contractualisées et heures réalisées, par module et par contrat. |

---

## 4. Indicateurs et restitutions

### Suivi pédagogique
- Heures réalisées vs heures contractualisées, par module et par contrat.
- Heures restant à effectuer sur l'année.
- Liste des séances saisies.

### Suivi financier
- Chiffre d'affaires par école, par année, par module.
- Encours de facturation (émis non payé).
- Échéancier des factures et alertes de retard.
- Liste des devis non transformés en facture.

### Pilotage de l'activité
- Répartition du chiffre d'affaires par établissement.
- Comparaison annuelle (évolution du volume et du CA).
- Taux de transformation devis → facture.

---

## 5. Fonctionnalités complémentaires suggérées

Au-delà du besoin exprimé, les fonctions suivantes apporteraient une valeur ajoutée notable — toutes réalisables sans Outlook ni messagerie.

### Génération de documents PDF
Production automatique des devis et factures au format PDF à partir d'un modèle reprenant l'identité de l'auto-entrepreneur, les mentions légales obligatoires (numéro SIRET, mention de franchise de TVA, conditions de règlement, pénalités de retard) et le détail des lignes. Cela éviterait toute ressaisie et garantirait l'homogénéité des documents.

### Tableau de bord d'accueil
Écran de synthèse à l'ouverture : encours total, factures en retard, heures restant à dispenser, devis en attente de réponse. Vue d'ensemble immédiate sans navigation.

### Mentions légales et conformité
Stockage centralisé des informations de l'auto-entrepreneur (SIRET, adresse, coordonnées bancaires/IBAN, mentions légales) pour alimenter automatiquement les documents. Vérification de la présence des mentions obligatoires sur chaque facture.

### Échéancier et calendrier de trésorerie
Projection des encaissements attendus à partir des dates d'échéance, pour anticiper la trésorerie. Utile notamment pour les déclarations URSSAF trimestrielles.

### Aide à la déclaration de chiffre d'affaires
Calcul du CA encaissé par période (mois ou trimestre) pour faciliter la déclaration auprès de l'URSSAF, avec distinction entre CA facturé et CA effectivement encaissé.

### Historique et journalisation
Conservation d'un historique des modifications sur les documents financiers (qui, quand, quoi) pour la traçabilité, en particulier sur les passages FP → F et les changements de statut.

### Export comptable
Export des données de facturation et de paiement au format tableur (CSV/Excel) pour transmission à un comptable ou archivage annuel.

### Sauvegarde et portabilité
Sauvegarde régulière de la base et possibilité d'export complet des données pour ne pas dépendre d'un poste unique.

---

## 6. Fonctionnalités reportées à une phase ultérieure

Les éléments suivants sont volontairement exclus de la présente version et seront étudiés plus tard. La structure de données est conçue pour les accueillir sans refonte.

| Fonctionnalité reportée | Impact sur la version actuelle |
|-------------------------|-------------------------------|
| Import des séances depuis l'agenda Outlook | La table Séances existe et se remplit manuellement ; elle pourra être alimentée automatiquement par la suite. |
| Convention de catégories Outlook et rapprochement automatique | Sans objet pour l'instant ; le rattachement séance → ligne de contrat se fait manuellement. |
| Déduction automatique du type de cours (via le `+`) | Le type de cours (Spécialité / Commun) est saisi manuellement. |
| Envoi automatisé des relances par e-mail | Les relances sont saisies et suivies manuellement, sans génération ni envoi de message. |

---

## 7. Contraintes et points d'attention

- **Régime de franchise de TVA :** aucun calcul de TVA ; mention légale obligatoire sur les documents.
- **Intégrité de la numérotation :** le compteur ne doit jamais produire de doublon ni de trou ; la séquence légale des factures doit être continue.
- **Conservation des documents :** les factures doivent être conservées dix ans ; une fois émises, leurs montants sont figés.
- **Mono-utilisateur :** l'outil est conçu pour une utilisatrice unique ; pas de gestion d'accès concurrents.

---

## 8. Modèle de données (synthèse)

L'application repose sur douze entités principales :

**Référentiels** — Niveaux, Spécialités.
**Tiers** — Écoles, Contacts.
**Offre** — Modules.
**Engagements** — Contrats, Lignes de contrat, Séances.
**Finances** — Factures, Lignes de facture, Paiements, Relances.

Les relations garantissent l'intégrité référentielle : un contact appartient à une école, une ligne de contrat référence un module et un contrat, une séance est rattachée à une ligne de contrat, une facture est rattachée à une école et un contact, une ligne de facture relie une facture à une ligne de contrat, etc.

---

*Document de cadrage — version recentrée hors Outlook et messagerie, susceptible d'évoluer selon les retours d'usage.*

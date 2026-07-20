# Architecture Technique – DAMS BI

## Flux Financier End-to-End

```
┌─────────────────────────────────────────────────────────────────┐
│                    VENTE TERRAIN (DAMS PROD)                    │
│                                                                  │
│  Agent terrain vend → core_vente.pk créée                       │
│  ├─ agent_id, detail_distribution_id                            │
│  ├─ quantite, prix_vente_unitaire                                │
│  ├─ date_vente                                                  │
│  └─ Mode paiement (comptant/crédit)                             │
│                                                                  │
│  ⚠ superviseur_id, produit_id, fournisseur_id, prix_achat_unit. │
│    NE SONT PAS des colonnes de core_vente — dérivés via :        │
│    detail_distribution → distribution_agent (superviseur_id)    │
│    detail_distribution → lot_entrepot (produit, fournisseur,    │
│    prix_achat_unitaire)                                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  RECOUVREMENT AGENT → SUPERVISEUR                │
│                                                                  │
│  Recouvrement.pk créée                                          │
│  ├─ agent_id, superviseur_id, montant_recouvre                 │
│  ├─ date_recouvrement                                           │
│  └─ bonus_accorde (si applicable)                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  REMISE SUPERVISEUR → ROT                        │
│                                                                  │
│  RecouvrementSuperviseur.pk créée                               │
│  ├─ superviseur_id, rot_id, montant                             │
│  ├─ date_recouvrement                                           │
│  └─ [ROT détient le cash]                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
               ┌──────────────┴──────────────┐
               ↓                             ↓
        ┌────────────────┐        ┌──────────────────┐
        │  DÉPENSES ROT  │        │ VERSEMENT BANQUE │
        │                │        │                  │
        │ Depense.pk     │        │ VersementBancaire│
        │ ├─ categorie   │        │ ├─ montant_vente │
        │ ├─ montant     │        │ ├─ date          │
        │ └─ date        │        │ └─ rot_id        │
        └────────────────┘        └──────────────────┘
               ↓                             ↓
        ┌────────────────┐        ┌──────────────────┐
        │  CASH DÉPENSÉ  │        │   SOLDE BANQUE   │
        └────────────────┘        └──────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                  SALAIRES & INCENTIVES (FLUX PAIE)               │
│                                                                  │
│  Salaire.pk créée mensuellement                                 │
│  ├─ Agent Terrain : base + (kg_vendus × 25 FCFA)                │
│  ├─ Agent Gros   : cartons_vendus × 250 FCFA (ou paliers)       │
│  ├─ Superviseur  : base + dotation + bonus(kg_palier)           │
│  └─ [Versé par ROT ou direct bancaire]                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     RENTABILITÉ NETTE (CALCUL)                   │
│                                                                  │
│  ∑(CA) − ∑(coût_achat) − ∑(salaires) − ∑(dépenses) = RÉSULTAT   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture Data (Schéma en Étoile)

```
┌────────────────────────────────────────────────────────────────┐
│                      FACTS (CENTRE)                             │
│                                                                 │
│  fct_ventes                                                     │
│  ├─ vente_id (pk)                                               │
│  ├─ agent_id (fk)      ──→ dim_agent      [core_vente]          │
│  ├─ superviseur_id (fk)──→ dim_superviseur                      │
│  │    [dérivé : detail_distribution → distribution_agent]       │
│  ├─ produit_id (fk)    ──→ dim_produit                          │
│  │    [dérivé : detail_distribution → lot_entrepot]              │
│  ├─ fournisseur_id (fk)──→ dim_fournisseur                      │
│  │    [dérivé : detail_distribution → lot_entrepot]              │
│  ├─ date_id (fk)       ──→ dim_temps                            │
│  ├─ quantite                                    [core_vente]    │
│  ├─ quantite_en_kg      ⚠ PAS quantite brut : si produit         │
│  │    conditionné (poids_unitaire_kg renseigné sur core_produit)│
│  │    quantite_en_kg = quantite × poids_unitaire_kg ; sinon     │
│  │    (vente au kg/vrac) = quantite. Pivot de tout KPI volume   │
│  │    (objectif 50kg/jour, incentive terrain) — répliquer cette │
│  │    logique en dbt, ne jamais sommer `quantite` brut pour un  │
│  │    KPI en kg.                                                │
│  ├─ prix_achat_unitaire         [dérivé : lot_entrepot]         │
│  ├─ prix_vente_unitaire                         [core_vente]    │
│  ├─ marge_unitaire (prix_vente - prix_achat)                    │
│  ├─ total_vente (quantite × prix_vente)                         │
│  └─ total_cout_achat (quantite × prix_achat)                    │
│                                                                 │
│  fct_salaires                                                   │
│  ├─ salaire_id (pk)                                             │
│  ├─ agent_id (fk)      ──→ dim_agent                            │
│  ├─ superviseur_id (fk)──→ dim_superviseur                      │
│  ├─ date_id (fk)       ──→ dim_temps                            │
│  ├─ salaire_base                                                │
│  ├─ incentive                                                   │
│  └─ salaire_total                                               │
│                                                                 │
│  fct_depenses                                                   │
│  ├─ depense_id (pk)                                             │
│  ├─ agent_id (fk)      ──→ dim_agent                            │
│  │    [source réelle : core_depense.effectue_par_id → core_agent│
│  │     — pas de colonne "rot_id". Confirmé (REFERENCE_TECHNIQUE │
│  │     _BI.md) : effectue_par_id n'est pas contraint à un type  │
│  │     — exposer type_agent en BI pour filtrer/valider plutôt   │
│  │     que de supposer que seul un ROT y écrit]                 │
│  ├─ date_id (fk)       ──→ dim_temps                            │
│  ├─ categorie          ⚠ 21 lignes NULL en base malgré le default│
│  │    non-NULL du modèle — prévoir un fallback 'INCONNU' + test │
│  │    dbt en warn, pas en erreur                                │
│  └─ montant                                                     │
│                                                                 │
│  fct_stocks                                                     │
│  ├─ stock_id (pk)                                               │
│  ├─ produit_id (fk)    ──→ dim_produit                          │
│  ├─ fournisseur_id (fk)──→ dim_fournisseur                      │
│  ├─ date_id (fk)       ──→ dim_temps                            │
│  ├─ quantite_restante  [LotEntrepot.quantite_restante — état    │
│  │    courant, pas d'historique quotidien natif ; ⚠ ne pas se   │
│  │    fier au champ stocké DetailDistribution.quantite_vendue   │
│  │    pour la partie "vendu" — recalculer depuis Vente (comme   │
│  │    la property quantite_restante_calculee), le champ stocké  │
│  │    peut être désynchronisé selon le chemin de vente emprunté │
│  │    (5 chemins de code identifiés, REFERENCE_TECHNIQUE_BI §4)]│
│  ├─ valeur_stock (quantite × prix_achat_moyen)                  │
│  └─ jours_en_stock     [snapshot uniquement en S1, cf. sprints/] │
│                                                                 │
│  fct_paiements_fournisseur                                      │
│  ├─ paiement_id (pk)                                            │
│  ├─ fournisseur_id (fk)──→ dim_fournisseur                      │
│  ├─ lot_id (fk)        ──→ dim_produit (indirect)               │
│  ├─ date_id (fk)       ──→ dim_temps                            │
│  └─ montant                                                     │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                 DIMENSIONS (CHAMPS CONTEXTE)                    │
│                                                                 │
│  dim_agent                                                      │
│  ├─ agent_id (pk)                                               │
│  ├─ nom_complet         [join core_agent + auth_user requis —   │
│  │    pas de nom sur core_agent lui-même]                       │
│  ├─ type_agent : valeurs réelles = direction, rot, entrepot     │
│  │    (= "superviseur" métier ⚠ pas 'superviseur' en base),     │
│  │    terrain, agent_gros, agent_polivalent, stagiaire,         │
│  │    gestionnaire_stock (8 valeurs, confirmées REFERENCE_      │
│  │    TECHNIQUE_BI.md §3)                                       │
│  ├─ superviseur_id (fk to dim_agent if applicable)              │
│  ├─ est_actif                                                   │
│  └─ date_debut, date_fin                                        │
│                                                                 │
│  dim_superviseur                                                │
│  ├─ superviseur_id (pk)                                         │
│  ├─ nom_complet                                                 │
│  └─ est_actif                                                   │
│                                                                 │
│  dim_produit                                                    │
│  ├─ produit_id (pk)                                             │
│  ├─ nom                                                         │
│  ├─ categorie          ⚠ n'existe pas sur core_produit          │
│  │    (champ à retrancher du modèle ou à ajouter côté DAMS —    │
│  │     décision différée au PO)                                  │
│  ├─ fournisseur_id (fk) ⚠ n'existe pas sur core_produit         │
│  │    (le fournisseur est porté par le LOT, pas le produit ;    │
│  │     un produit peut avoir plusieurs fournisseurs selon les   │
│  │     lots — au mieux dérivable, pas une vraie FK 1:1)          │
│  └─ poids_unitaire_kg (pour conversion conditionné/vrac)        │
│                                                                 │
│  dim_fournisseur                                                │
│  ├─ fournisseur_id (pk)                                         │
│  ├─ nom                                                         │
│  └─ est_actif                                                   │
│                                                                 │
│  dim_temps                                                      │
│  ├─ date_id (pk, format: YYYYMMDD)                              │
│  ├─ date                                                        │
│  ├─ jour_semaine                                                │
│  ├─ semaine                                                     │
│  ├─ mois                                                        │
│  └─ annee                                                       │
└────────────────────────────────────────────────────────────────┘
```

---

## Data Lineage (Source → Target)

```
┌───────────────────────────────┐
│  DAMS Production               │
│  (Django + PG, schéma public,  │
│   tables préfixées core_)      │
│  ├─ core_vente                 │
│  ├─ core_detaildistribution    │
│  ├─ core_distributionagent     │
│  ├─ core_lotentrepot           │
│  ├─ core_agent + auth_user     │
│  ├─ core_salaire               │
│  ├─ core_depense                │
│  ├─ core_produit                │
│  ├─ core_fournisseur           │
│  ├─ core_mouvementstock        │
│  └─ core_perte                  │
└──────────┬──────────────────────┘
           │
           │ Extract (PG dump ou SELECT)
           ↓
┌───────────────────────────────┐
│  Staging Layer                 │
│  (dbt staging/)                │
│  ├─ stg_ventes                 │
│  ├─ stg_detail_distribution    │
│  ├─ stg_distribution_agent     │
│  ├─ stg_lots                   │
│  ├─ stg_agents                 │
│  ├─ stg_salaires               │
│  ├─ stg_depenses               │
│  ├─ stg_produits               │
│  ├─ stg_fournisseurs           │
│  ├─ stg_mouvements_stock       │
│  └─ stg_pertes                 │
└──────────┬──────────────────────┘
           │
           │ Transform (dbt models/)
           ↓
┌─────────────────────┐
│  Dimension Tables   │
│  (dbt marts/)       │
│  ├─ dim_agent       │
│  ├─ dim_superviseur │
│  ├─ dim_produit     │
│  ├─ dim_fournisseur │
│  └─ dim_temps       │
└────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│  Fact Tables (dbt marts/)                │
│  ├─ fct_ventes (core facts)              │
│  ├─ fct_salaires                         │
│  ├─ fct_depenses                         │
│  ├─ fct_stocks                           │
│  └─ fct_paiements_fournisseur            │
└──────────┬───────────────────────────────┘
           │
           │ Materialized Views
           ↓
┌──────────────────────────────────────────┐
│  Aggregates pour Dashboards              │
│  ├─ vw_rentabilite_globale              │
│  ├─ vw_rentabilite_produit              │
│  ├─ vw_performance_superviseur          │
│  ├─ vw_performance_agent                │
│  └─ vw_analyse_stock                    │
└──────────┬───────────────────────────────┘
           │
           │ Connect
           ↓
┌──────────────────────────────────────────┐
│  Metabase Dashboards                     │
│  ├─ Dashboard 1 : Santé globale         │
│  ├─ Dashboard 2 : Rentabilité produit   │
│  ├─ Dashboard 3 : Performance superviseur│
│  ├─ Dashboard 4 : Performance agent     │
│  └─ Dashboard 5 : Stock & Fournisseur   │
└──────────────────────────────────────────┘
           │
           │ Export
           ↓
┌──────────────────────────────────────────┐
│  Rapports PDF/Excel mensuels            │
└──────────────────────────────────────────┘
```

---

## Stack Technique Détaillé

| Composant | Technologie | Version | Coût |
|-----------|-------------|---------|------|
| **Base transactionnelle** | PostgreSQL | 13+ | 0€ (LWS) |
| **Data Warehouse** | PostgreSQL (schéma `bi_`) | 13+ | 0€ |
| **ETL / Transformation** | dbt Core | 1.5+ | 0€ |
| **Orchestration** | cron + dbt | - | 0€ |
| **BI / Dashboards** | Metabase | 46+ | 0€ |
| **IDE dbt** | dbt Cloud (free tier) ou VS Code | - | 0€ |
| **Docs / Lineage** | dbt docs + dbt Cloud | - | 0€ |

---

## Processus ETL (dbt Run)

**Exécution** : Chaque nuit à 23h00 Mali

```bash
# Dans le projet dbt local ou VM
dbt run --profiles-dir ~/.dbt --select bi_

# Temps estimé
# ├─ Staging (extract DAMS) : 2-3 min
# ├─ Dimensions : 3-5 min
# ├─ Facts : 5-10 min
# ├─ Aggregates / Views : 2-3 min
# └─ TOTAL : ~15-30 min
```

**Erreurs** :
- Alerter (email) si dbt run échoue
- Rollback sur schéma `bi_` (pas d'impact DAMS)

---

## Infrastructure Déploiement

```
┌──────────────────────┐
│   Machine Locale     │
│   (Mahamane PC)      │
│                      │
│  ├─ dbt project      │
│  ├─ ~/.dbt/          │
│  ├─ Git repo         │
│  └─ Python 3.10+     │
└──────────┬───────────┘
           │
           │ Git Push
           ↓
┌──────────────────────┐
│  GitHub Repo         │
│  (private)           │
│                      │
│  ├─ dbt/             │
│  ├─ docs/            │
│  ├─ scripts/         │
│  └─ README.md        │
└──────────┬───────────┘
           │
           │ Deploy (cron sur VM)
           ↓
┌──────────────────────┐
│  VM Production       │
│  (Cheap VPS ou      │
│   serveur local)     │
│                      │
│  ├─ dbt-prod/        │
│  ├─ Cron job        │
│  │  23:00 → dbt run │
│  └─ Logs            │
└──────────┬───────────┘
           │ PostgreSQL cible
           ↓
┌──────────────────────┐
│  PostgreSQL (LWS)    │
│  ├─ Schema public    │
│  │  (DAMS prod)      │
│  └─ Schema bi_       │
│     (Analytique)     │
└──────────┬───────────┘
           │
           │ JDBC / SQL
           ↓
┌──────────────────────┐
│  Metabase Docker     │
│  (sur même VM)       │
│                      │
│  ├─ Port 3000        │
│  └─ Dashboards       │
└──────────────────────┘
```

---

## Champs et tables à exclure / traiter avec prudence

Confirmé par [architecte/REFERENCE_TECHNIQUE_BI.md](REFERENCE_TECHNIQUE_BI.md) (audit code + base réelle) :

**Champs dépréciés — ne jamais utiliser en BI, aucun flux actif ne les alimente** :
- `VersementBancaire.superviseur` (utiliser `effectue_par`)
- `Depense.versement` (jamais renseigné à la création)

**Tables vides ou quasi jamais alimentées — à exclure du modèle dbt pour le MVP** :
`Client`, `Dette`, `PaiementDette`, `JournalModificationDistribution`, `AjustementSolde` (0 ligne dans la base de référence).

**Source de vérité pour le "reste à vendre" d'une distribution** : utiliser un recalcul depuis `Vente` (équivalent à la property `DetailDistribution.quantite_restante_calculee`), pas le champ stocké `quantite_vendue` — ce dernier peut être désynchronisé selon le chemin de vente emprunté (au moins 5 chemins de code identifiés côté DAMS).

**Biais connu sur le coût de paie superviseur** : `RegleSalaire.dotation_fonction` n'est jamais appliquée en production (bug confirmé, `type_agent` mal aligné) — `Salaire.salaire_total` d'un superviseur peut être structurellement sous-évalué. La BI reste fidèle aux montants réellement stockés/payés (source de vérité = DAMS), ce biais n'est pas à corriger côté BI mais à documenter (voir `chef_projet/RISQUES.md` R14).

---

## Calendrier MVP

| Semaine | Tâche | Livrables |
|---------|-------|-----------|
| **S1 (Juillet)** | Modeling dbt | dbt project structuré, staging + dims |
| **S2** | Fact tables | fct_ventes, fct_salaires, fct_depenses, fct_stocks |
| **S3** | Dashboards Metabase | 5 dashboards version 1 |
| **S4** | Validation + Exports | Tests dbt, rapports Excel, go-live |
| **Août+** | Maintenance | Refresh nuit stable, bug fixes, améliorations |

---

## Maintenance & Support

**Responsabilités** :
- **Mahamane** : dbt code, transformations, logique métier, documentation
- **Superviseurs** : validation outputs, questions métier

**Monitoring** :
- Logs dbt : vérifier exit code chaque nuit
- Alerte email si erreur
- Dashboard "Qualité données" optionnel

**Scalabilité** :
- S1 : 50M lignes ventes
- S2 2026 : passer à refresh hourly ?
- 2027 : Snowflake si besoin

---

## Note de traçabilité

Le schéma source (noms de tables, colonnes, clés étrangères) documenté ci-dessus a été **confirmé le 16/07/2026** par lecture directe de `input/dams_2026-07-12.dump` (dump PostgreSQL de production, format custom, inspecté sans restauration via extraction des instructions `CREATE TABLE` / `FOREIGN KEY`). Avant cette vérification, ce document supposait un schéma PostgreSQL séparé `core` et des colonnes directes sur `Vente` (`superviseur_id`, `produit_id`, `fournisseur_id`, `prix_achat_unitaire`) qui n'existent pas en réalité — voir les annotations ⚠ dans les sections ci-dessus pour le détail des écarts corrigés.

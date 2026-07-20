# DAMS BI — Engineering OS

Plateforme **Business Intelligence** pour les opérations de distribution **DAMS**.

**Owner** : Mahamane Daouda Maïga
**Scope MVP** : période 01/01 – 30/06 2026 — 5 dashboards, ~25 KPI
**Stack** : PostgreSQL + dbt + app Django `bi` (SSR + Chart.js) — Metabase abandonné, voir [architecte/04_ADR.md](architecte/04_ADR.md#adr-009--metabase-abandonné--restitution-django-ssr--chartjs) (coût 0 €)

> **Le problème** : beaucoup de données sur ce qu'on vend, mais aucune vue claire sur ce que ça **rapporte réellement** après tous les coûts (salaires + dépenses). Le KPI centre du projet est la **rentabilité nette**.

---

## 🚀 Par où commencer

| Ton temps | Lis |
|-----------|-----|
| 3 min | [shared/INDEX.md](shared/INDEX.md) — résumé complet |
| 15 min | [shared/README_ENGINEERING_OS.md](shared/README_ENGINEERING_OS.md) — guide de lecture |
| Vision métier | [owner/01_Vision_Produit.md](owner/01_Vision_Produit.md) |

---

## 📁 Organisation par rôle

Les documents sont rangés par responsabilité. Chaque rôle lit **son** dossier en priorité ; les docs communes sont dans `shared/`.

### 📂 [owner/](owner/) — Product Owner (vision métier)
- [01_Vision_Produit.md](owner/01_Vision_Produit.md) — pourquoi on construit ça
- [02_Backlog.md](owner/02_Backlog.md) — quoi faire ensuite (stories priorisées)
- [03_Roadmap.md](owner/03_Roadmap.md) — quand et dans quel ordre (jalons)

### 📂 [architecte/](architecte/) — Data Architect (comment on le construit)
- [04_ADR.md](architecte/04_ADR.md) — décisions techniques (PostgreSQL + dbt + app Django `bi`, Metabase abandonné ADR-009)
- [05_Architecture.md](architecte/05_Architecture.md) — stack, flux, lineage, schéma en étoile
- [FLUX_PAIEMENT.md](architecte/FLUX_PAIEMENT.md) — diagrammes du circuit financier
- [REFERENCE_TECHNIQUE_BI.md](architecte/REFERENCE_TECHNIQUE_BI.md) — référence technique DAMS (modèles, propriétés calculées, workflows réels, écarts) produite par audit de code+base, source de vérité pour la construction dbt
- [AMELIORATIONS_DAMS.md](architecte/AMELIORATIONS_DAMS.md) — journal des améliorations à apporter à l'ERP DAMS (rempli en continu)
- [setup.md](architecte/setup.md) — rôles PostgreSQL (dbt_user, bi_reader) et ordre de mise en route

### 📂 [bi/](bi/) — BI Developer (dashboards + KPI)
- [07_Dictionnaire_KPI_Technique.md](bi/07_Dictionnaire_KPI_Technique.md) — version **technique** (formules SQL, sources dbt) → pour l'implémentation
- [07_Dictionnaire_KPI_Metier.md](bi/07_Dictionnaire_KPI_Metier.md) — version **métier** (langage courant, simplifiée) → pour Direction / PO
- [08_Dashboard_Catalog.md](bi/08_Dashboard_Catalog.md) — spécifications des 5 dashboards

### 📂 [chef_projet/](chef_projet/) — Chef de Projet (qualité + planning)
- [09_Qualite_DoD.md](chef_projet/09_Qualite_DoD.md) — Definition of Done (générique par type de livrable)
- [PLANNING.md](chef_projet/PLANNING.md) — vue d'ensemble du calendrier 4 semaines
- [RISQUES.md](chef_projet/RISQUES.md) — registre des risques

### 📂 [sprints/](sprints/) — Chef de Projet (exécution du MVP)
- [README.md](sprints/README.md) — cadence, cérémonies, index des 4 sprints
- [SPRINT_1_Fondations.md](sprints/SPRINT_1_Fondations.md) → [SPRINT_4_GoLive.md](sprints/SPRINT_4_GoLive.md) — backlog, plan jour par jour, DoD et gate de chaque sprint

### 📂 [shared/](shared/) — Pour tout le monde
- [INDEX.md](shared/INDEX.md) — résumé du projet entier
- [MASTER_INDEX.md](shared/MASTER_INDEX.md) — index maître des livrables
- [README_ENGINEERING_OS.md](shared/README_ENGINEERING_OS.md) — comment lire les docs
- [SYNTHESE_REVISIONS.md](shared/SYNTHESE_REVISIONS.md) — historique des changements
- [GLOSSAIRE.md](shared/GLOSSAIRE.md) — définitions métier (agent, superviseur, trésorier…)

### 📄 Racine
- [STRUCTURE_DOSSIERS.md](STRUCTURE_DOSSIERS.md) — description de l'organisation cible

---

## 🗺️ Parcours de lecture recommandé

| Rôle | Ordre de lecture |
|------|------------------|
| **Product Owner** | `01_Vision_Produit.md` → `02_Backlog.md` → `03_Roadmap.md` |
| **Architecte** | `04_ADR.md` → `05_Architecture.md` → `FLUX_PAIEMENT.md` |
| **BI Developer** | `07_Dictionnaire_KPI.md` → `08_Dashboard_Catalog.md` |
| **Chef de Projet** | `09_Qualite_DoD.md` → `PLANNING.md` → `sprints/README.md` → sprint courant → `RISQUES.md` |

---

## 📊 Responsabilités

| Rôle | Lit | Édite |
|------|-----|-------|
| **PO** | `owner/*` | Vision |
| **Architecte** | `architecte/*` | ADR, Architecture, Flux |
| **BI Dev** | `bi/*` | KPI, Dashboards |
| **Chef Projet** | `chef_projet/*`, `sprints/*` | DoD, Planning, Sprints, Risques |
| **Tout le monde** | `shared/*` | Index, Glossaire (lecture) |

> **Note** : ces 5 rôles sont tous portés par **une seule personne** (Mahamane). Le découpage par dossier sert à séparer les *types de décision* (vision produit ≠ arbitrage technique ≠ implémentation ≠ suivi qualité), pas à coordonner une équipe. En conséquence, pas de réunions de synchronisation entre rôles (standup, passation, validation croisée) — les cérémonies dans [sprints/README.md](sprints/README.md) sont réduites à des points de contrôle solo en fin de sprint, pas des réunions d'équipe.

---

## 📌 À venir (non encore créés)

Éléments prévus dans la structure cible mais pas encore créés (projet en démarrage) :
`architecte/06_Modele_Multidimensionnel.drawio`, le code `dbt/` (models, tests),
les dossiers `bi/queries/` et `bi/tests/`, et un README par dossier.

---

*Dernière réorganisation : 16 juillet 2026 (découpage du MVP en sprints).*

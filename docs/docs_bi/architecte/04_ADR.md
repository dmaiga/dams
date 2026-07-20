# Architecture Decision Records (ADR) – DAMS BI

---

## ADR-001 : PostgreSQL comme Data Warehouse

**Date** : Juillet 2026  
**Status** : ✅ ACCEPTÉE  
**Décideur** : Mahamane (Architect)

### Problème
On a besoin d'une base analytique pour les 5 dashboards. Choix : PostgreSQL vs BigQuery vs Snowflake.

### Options Évaluées

| Aspect | PostgreSQL | BigQuery | Snowflake |
|--------|------------|----------|-----------|
| **Coût démarrage** | Gratuit | Paiement requête | Gratuit trial → payant |
| **Maintenance** | Auto (LWS cPanel) | Serverless | Serverless |
| **Temps setup** | 1 jour | 2 heures | 4 heures |
| **Performance (100M lignes)** | Bonne | Excellente | Excellente |
| **Scalabilité** | Limite ~500M | Illimitée | Illimitée |
| **Skillset existant** | ✅ Mahamane | ❌ Non | ❌ Non |

### Décision
**PostgreSQL** (même instance que DAMS production, schéma `bi_` séparé)

### Justification
1. **Coût** : Zéro (déjà payée chez LWS)
2. **Maintenance** : Aucune (cPanel géré)
3. **Scalabilité suffisante** : 6 mois de données = ~50M lignes max
4. **Mahamane maîtrise** PostgreSQL
5. **Peut passer à Snowflake en V2** si besoin (migration triviale)

### Conséquences
- ✅ Aucun coût additionnel
- ❌ Performances limites si beaucoup de requêtes simultanées (mitigé par cache)
- ❌ Pas de historique temps réel (refresh nuit)

---

## ADR-002 : dbt pour l'ETL

**Date** : Juillet 2026  
**Status** : ✅ ACCEPTÉE  
**Décideur** : Mahamane (Data Architect)

### Problème
On doit transformer les données DAMS transactionnelles en schéma analytique. Choix : dbt vs Airflow vs Python pur.

### Options Évaluées

| Aspect | dbt | Airflow | Python pur |
|--------|-----|---------|-----------|
| **Setup** | 1 jour | 3 jours | 2 heures |
| **Maintenance SQL** | 💪 Native | Faible | ❌ Mélangé |
| **Orchestration** | ✅ Intégrée | ✅✅ Robuste | ❌ Manuel |
| **Documentation** | 🌟 Excellente | Bonne | Faible |
| **Coût** | Gratuit | Gratuit (OSS) | Gratuit |
| **Test data quality** | ✅ Built-in | Plugin | À coder |
| **Learning curve** | Rapide | Raide | Moyen |

### Décision
**dbt** (dbt Cloud gratuit, ou dbt Core self-hosted)

### Justification
1. **SQL-first** : ta force est SQL, pas Python orchestre
2. **Documentation auto** : génère lineage + tests automatiquement
3. **Data quality intégrée** : tests de nullité, unicité, etc.
4. **Scalabilité future** : passe facilement de dbt Core → dbt Cloud
5. **Comunauté large** : exemples + support faciles

### Conséquences
- ✅ Transformations claires et testables
- ✅ Lineage généré automatiquement
- ❌ Nécessite apprentissage dbt (rapide)
- ❌ Externalisation de logique complexe (Python UDF si besoin)

### Confirmation Sprint 1 (17/07/2026)
L'environnement de développement avait `dbt-fusion 2.0.0-preview.176` (moteur Rust preview) déjà installé, différent de "dbt Core" choisi ci-dessus. Confirmé **dbt Core** au moment de l'implémentation (mature, documentation/communauté — la justification initiale reste valide face à une alternative encore en preview) : **dbt-core 1.12.0** + **dbt-postgres 1.11.0**, installés dans un venv Python dédié (`.venv/`, gitignoré), `require-dbt-version` figée dans `dbt_project.yml`.

---

## ADR-003 : Superset ou Metabase pour BI

**Date** : Juillet 2026  
**Status** : ⏳ FLEXIBLE (évaluer les deux)  
**Décideur** : Mahamane (Product Owner)

### Problème
Afficher les 5 dashboards. Choix : Superset vs Metabase vs Power BI.

### Options Évaluées

| Aspect | Superset | Metabase | Power BI |
|--------|----------|----------|----------|
| **Coût** | Gratuit OSS | Gratuit OSS | Payant (~$10/user) |
| **Setup** | Docker (1h) | Docker (30min) | SaaS |
| **UI/UX** | Moderne | Intuitive | Professionnelle |
| **Customization** | 🔥 Avancée | Limitée | Bonne |
| **SQL direct** | ✅ Oui | Oui (limité) | Oui |
| **Alertes** | ✅ Oui | Oui | Oui |
| **Intégration LDAP** | ✅ Oui | Oui | Oui |

### Décision
**Metabase** en MVP (plus rapide), possibilité de passer à **Superset** si besoin d'advanced features.

### Justification
1. **Déploiement rapide** : Metabase se lance en 30 min
2. **Suffisant pour MVP** : 5 dashboards statiques OK
3. **Pas de code** : SQL uniquement
4. **Passage à Superset facile** : même source de données PostgreSQL

### Alternative (V2)
Si besoin de customization poussée (embedding, filtres complexes) → **Superset**.

### Conséquences
- ✅ On livre les dashboards vite
- ✅ Zéro coût
- ❌ Features avancées limitées (OK pour MVP)

---

## ADR-004 : Scope Période Figée (01/01 – 30/06)

**Date** : Juillet 2026  
**Status** : ✅ ACCEPTÉE  
**Décideur** : Mahamane (Product Owner)

### Problème
Faire une analyse "ponctuelle" ou "évolutive" ? Période figée ou glissante ?

### Options

**A) Période figée (01/01 – 30/06)**
- Une seule analyse de 6 mois
- Pas de rafraîchissement
- Statique mais clair

**B) Analyse mensuelle récurrente**
- Chaque mois → nouveau rapport
- Évolutif dans le temps
- Nécessite plus d'infra

### Décision
**Période figée 01/01 – 30/06** (MVP)

### Justification
1. **Scope clair** : "Avons-nous gagné au S1 2026 ?"
2. **Pas d'infra temps réel** : extract une fois, analyser
3. **Reproductibilité** : mêmes nombres toujours
4. **Simple à déployer** : pas de refresh quotidien
5. **V2** : passer à mensuel/continu

### Conséquences
- ✅ Déploiement simplifié
- ✅ Données figées = reproductibles
- ❌ Pas de suivi temps réel
- ℹ️ **Transition V2** : ajouter refresh nuit dès septembre

---

## ADR-005 : Schéma `bi_` Isolé dans PostgreSQL

**Date** : Juillet 2026  
**Status** : ✅ ACCEPTÉE  
**Décideur** : Mahamane (Data Architect)

### Problème
Où créer les tables analytiques ? Dans `public` (DAMS) ou schéma isolé ?

### Décision
**Schéma PostgreSQL séparé : `bi_`**

```sql
CREATE SCHEMA bi_;

-- Tables de fait
CREATE TABLE bi_.fct_ventes (...)
CREATE TABLE bi_.fct_salaires (...)
CREATE TABLE bi_.fct_depenses (...)

-- Dimensions
CREATE TABLE bi_.dim_agent (...)
CREATE TABLE bi_.dim_superviseur (...)
...

-- VUEs matérialisées pour dashboards
CREATE MATERIALIZED VIEW bi_.vw_rentabilite_produit AS ...
```

### Justification
1. **Isolement** : DAMS production intact
2. **Clarté** : `bi_` = données analytiques
3. **Permissions faciles** : grant `SELECT` sur `bi_.*` uniquement
4. **Migration facile** : exporter schéma `bi_` complet

### Conséquences
- ✅ Séparation claire
- ✅ Zéro impact production
- ❌ Duplication données (OK pour MVP)

---

## ADR-006 : Refresh ETL = Nuit (Batch, pas Temps Réel)

**Date** : Juillet 2026  
**Status** : ✅ ACCEPTÉE  
**Décideur** : Mahamane (Data Architect)

### Problème
Quand rafraîchir les données ? Temps réel vs batch nuit ?

### Décision
**Batch nuit** (23h00 Mali time)

```bash
# Chaque nuit, dbt refresh
dbt run --profiles-dir ~/.dbt --select bi_
# Approx 15-30 min
```

### Justification
1. **Suffisant** : dashboards lus le matin
2. **Pas de coût** : une seule exécution/jour
3. **Pas de complexité** : pas de streaming, pas de dépendances
4. **Reproductibilité** : même fenêtre tous les jours

### Conséquences
- ✅ Simple
- ✅ Zéro coût infra
- ❌ Données "d'hier" (OK pour BI stratégique)

---

## ADR-007 : Conformité Twelve-Factor App

**Date** : Juillet 2026
**Status** : ✅ ACCEPTÉE
**Décideur** : Mahamane (Data Architect)

### Problème
Le code (`dbt/`, futurs scripts) n'existe pas encore (Sprint 1). Avant de l'écrire, fixer les règles de conception pour que le futur pipeline (dbt + Metabase + PostgreSQL) reste portable, sans état caché et sans secret en dur — plutôt que de les découvrir après coup. Grille de référence : [Twelve-Factor App](https://12factor.net).

Certains facteurs ne s'appliquent pas tels quels à un pipeline batch mono-opérateur à coût 0€ (pas de scaling horizontal, pas de vrai "process web" côté dbt) : le tableau ci-dessous documente ce qui s'applique, ce qui est adapté, et ce qui est explicitement hors scope MVP plutôt que de forcer une conformité artificielle.

### Décision — mapping par facteur

| # | Facteur | Application DAMS BI | Statut |
|---|---------|---------------------|--------|
| I | **Codebase** | Un seul repo Git (celui-ci), un seul déploiement (VM prod). Pas de multi-repo. | ✅ Déjà en place |
| II | **Dependencies** | Dépendances dbt déclarées explicitement : version de `dbt-core` figée dans `dbt_project.yml` (`require-dbt-version`), packages externes dans `packages.yml`. Jamais de dépendance implicite (paquet système supposé présent). | ✅ Fait Sprint 1 (`require-dbt-version: ">=1.12.0,<1.13.0"`, `dbt_utils` dans `packages.yml`) |
| III | **Config** | Aucun identifiant PostgreSQL en dur dans le code. `profiles.yml` (credentials dbt) et tout `.env` restent **hors git** (déjà couvert par `.gitignore` : `.dbt/`, `profiles.yml`, `.env`). Un `.env.example` documente les variables attendues sans valeurs réelles. | ✅ Renforcé Sprint 1/ADR-008 : `dbt/profiles.yml` versionné dans le repo (contenu sans secret, tout via `env_var()`), plus de dépendance à `~/.dbt/profiles.yml` hors repo |
| IV | **Backing services** | PostgreSQL (schéma `bi_`) et l'app-DB de Metabase sont des ressources attachées, référencées par variables de connexion (host/port/db/user via env), jamais codées en dur — remplaçables sans changer le code dbt. | ✅ Fait pour PostgreSQL (Sprint 1) · ⏳ Metabase Sprint 2 |
| V | **Build, release, run** | `dbt compile`/`dbt build` (build) séparé de `dbt run` planifié par cron (run). Une release = un commit Git + la config de l'environnement au moment du run — pas de modification manuelle en prod hors Git. | ✅ Fait Sprint 1 (`dbt build` en dev) · ⏳ cron prod Sprint 4 |
| VI | **Processes** | `dbt run` est stateless : tout l'état vit dans PostgreSQL (`bi_`), jamais dans des fichiers locaux au process. Écart assumé : l'app-DB interne de Metabase (SQLite par défaut) est stateful → **mitigation** : volume Docker persistant + backup, migration vers une DB Postgres dédiée à évaluer en V1.5. | ✅ Fait pour dbt (Sprint 1) · ⏳ Metabase Sprint 2 · écart documenté |
| VII | **Port binding** | Metabase expose son propre serveur HTTP via port binding (Docker `-p`), sans dépendre d'un serveur web externe. `dbt run` n'est pas un service réseau — c'est un processus batch (couvert par le facteur XII), pas concerné par ce facteur. | N/A pour dbt · ✅ Port binding scaffoldé (ADR-008, `docker-compose.yml`) · ⏳ config Metabase Sprint 2 |
| VIII | **Concurrency** | Un seul process dbt, un seul conteneur Metabase — suffisant au volume MVP (≤ 50M lignes, ADR-001). Scaling horizontal **hors scope MVP**, à revisiter si le volume ou le nombre d'utilisateurs simultanés grossit (V2). | Hors scope MVP (assumé) |
| IX | **Disposability** | `dbt run` doit être idempotent (ré-exécutable sans corrompre `bi_` en cas d'échec partiel). Conteneur Metabase jetable/redémarrable sans perte de données (données dans le volume, pas dans le conteneur). | ✅ Fait pour dbt (marts en `materialized: table`, ré-exécutable sans erreur) · ⏳ Metabase Sprint 2 |
| X | **Dev/prod parity** | Même moteur PostgreSQL et même version de dbt en dev qu'en prod. Dev local possible sur le dump `input/dams_*.dump` (base d'investigation) avant de toucher au schéma `bi_` de prod. Écart assumé : un seul environnement prod réel (pas de staging séparé) — accepté vu la contrainte 0€. | ✅ Renforcé ADR-008 : conteneurisation Docker Compose, versions figées dans `dbt/Dockerfile`, environnement reproductible à l'identique sur toute machine · écart staging/prod toujours assumé |
| XI | **Logs** | Logs de `dbt run` et du cron redirigés en flux (fichier `logs/` + sortie cron), jamais routés/formatés par le code dbt lui-même. Alerte email si échec (ADR-006). | ⏳ À faire Sprint 4 |
| XII | **Admin processes** | `dbt seed`, `dbt docs generate`, corrections SQL ad-hoc s'exécutent avec le même code et la même config que `dbt run` normal — jamais de script à part avec ses propres credentials. | ✅ Fait Sprint 1 (`dbt docs generate` exécuté avec le même profil que `dbt build`) |

### Conséquences pratiques pour le Sprint 1
- Créer `.env.example` à la racine (variables PostgreSQL attendues, sans valeurs)
- `dbt_project.yml` avec `require-dbt-version` figée + `packages.yml`
- Aucun `profiles.yml` commité — vérifier `.gitignore` avant le premier `dbt init`
- Ajouter au DoD dbt Model ([chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md)) : « aucun secret/host en dur, credentials via env »

### Conséquences
- ✅ Pipeline portable (dev local sur dump, prod sur VM) sans réécriture
- ✅ Aucun secret dans l'historique Git
- ❌ Deux facteurs (VI, X) partiellement respectés par choix budgétaire assumé (Metabase stateful, pas de staging) — reste à documenter comme dette technique, pas à cacher

---

## ADR-008 : Conteneurisation via Docker Compose

**Date** : Juillet 2026
**Status** : ✅ ACCEPTÉE
**Décideur** : Mahamane (Data Architect)

### Problème
Le Sprint 1 a été développé sur une installation native (PostgreSQL 17 Windows + venv Python + `~/.dbt/profiles.yml` hors repo) — fonctionnelle mais non portable : reproduire l'environnement sur une autre machine, ou déployer sur un serveur si la Direction le décide, demanderait de refaire tout le setup manuellement. Décision assumée en parallèle : ne pas toucher au PostgreSQL de production — le dump `input/dams_2026-07-12.dump` reste la source de données pour tout le développement (R15, [chef_projet/RISQUES.md](../chef_projet/RISQUES.md)).

### Décision
Conteneuriser Postgres + dbt (+ Metabase, scaffold pour le Sprint 2) via **Docker Compose** :
- `postgres` (image officielle `postgres:17-alpine`) : volume nommé persistant, restauration du dump **une seule fois** via `docker-entrypoint-initdb.d/` (ne s'exécute que si le volume est vide — pas de script de vérification maison à maintenir).
- `dbt` : image buildée depuis `dbt/Dockerfile`, invoquée à la demande (`docker compose run --rm dbt <commande>`), pas un service permanent.
- `dbt/profiles.yml` versionné dans le repo (au lieu de `~/.dbt/profiles.yml`), lu via `env_var()` — un seul fichier de profil pour le chemin conteneurisé et le chemin local (fallback).

Le setup natif Sprint 1 (venv + PostgreSQL Windows) reste documenté comme fallback dans `dbt/README.md`, pas supprimé.

### Justification
1. **Portabilité** : le projet devient reproductible en 3 commandes sur n'importe quelle machine avec Docker.
2. **Dev/prod parity renforcée** (ADR-007, facteur X) : mêmes versions de dbt/Postgres en dev qu'en cible de déploiement.
3. **Restauration one-shot native** : pas de logique custom pour éviter de re-restaurer à chaque démarrage — l'image Postgres officielle le fait déjà.
4. **Config toujours dans le repo** (ADR-007, facteur III) : `dbt/profiles.yml` remplace la dépendance à un fichier hors repo.

### Conséquences
- ✅ Portable : redéploiement sur serveur ou autre machine sans réinstallation manuelle
- ✅ Un seul jeu de variables d'environnement (`.env`) pour les deux chemins (Docker et local)
- ❌ Docker Desktop sur Windows s'est montré instable dans l'environnement de développement — projet copié dans WSL2 (Docker natif Linux) pour contourner ; à surveiller si ça se reproduit ailleurs
- ❌ `metabase` n'est que du scaffolding à ce stade (pas de configuration DB/dashboards, Sprint 2)

---

## ADR-009 : Metabase abandonné — restitution Django SSR + Chart.js

**Date** : 20 juillet 2026
**Status** : ✅ ACCEPTÉE (remplace ADR-003)
**Décideur** : Mahamane (Architect / Product Owner)

### Problème
ADR-003 laissait Metabase « flexible », à évaluer contre Superset. Au moment d'implémenter la restitution des 5 dashboards, se pose la question : faut-il réellement déployer/opérer un service BI dédié (Metabase, conteneurisé — scaffold ADR-008) pour ce périmètre ?

### Constat
- Le scope est **figé** : exactement 5 dashboards (`bi/08_Dashboard_Catalog.md`), pas de self-service, pas d'exploration ad hoc attendue de la Direction.
- Aucun besoin de créer de nouveaux graphiques à la volée, de croiser librement les données, ni de gérer des utilisateurs/permissions Metabase séparés.
- Le projet DAMS est déjà une application Django servie ; ajouter Metabase revient à opérer un **second service** (conteneur, DB interne, auth, sauvegarde — cf. ADR-007 facteur VI, déjà noté comme stateful/à surveiller) pour un gain d'UX marginal sur un périmètre entièrement connu à l'avance.

### Décision
**Abandon de Metabase.** Restitution des 5 dashboards directement dans l'app Django `bi` : templates SSR (Django Template Language), graphiques via **Chart.js** chargé en CDN (aucune dépendance Python/npm supplémentaire), cartes KPI en HTML/CSS pur (code couleur 🟢/🟡/🔴 piloté par `bi/constants.py`, pas de valeurs en dur dans les templates).

### Justification
1. **Un service de moins à opérer** : plus de conteneur Metabase, plus de DB interne à sauvegarder, plus d'auth séparée à maintenir — la seule surface d'exploitation reste PostgreSQL + dbt (déjà en place) + Django (déjà en place).
2. **Zéro besoin self-service** : les 5 dashboards sont entièrement spécifiés (`08_Dashboard_Catalog.md`), aucune valeur ajoutée à payer le coût d'un outil BI généraliste pour les afficher.
3. **Réutilise l'existant** : Django sert déjà toutes les autres interfaces DAMS (auth, permissions, sidebar) — la Direction se connecte au même endroit, pas de second portail/second mot de passe.
4. **Modèles managed=False** : les vues `bi_.vw_*` restent la seule source de vérité des KPI (aucune agrégation métier en Python), Django ne fait que les lire et les mettre en forme — le changement de restitution ne touche pas au contrat dbt.

### Conséquences
- ✅ Un service de moins (conteneur, DB, auth) à opérer et sauvegarder
- ✅ Portail unique Direction (même session Django que le reste de DAMS)
- ✅ Coût toujours 0 € (Chart.js CDN gratuit, aucune nouvelle dépendance Python)
- ❌ Pas d'exploration ad hoc / self-service — si ce besoin apparaît en V2, il faudra soit réintroduire un outil BI, soit étendre les templates Django (filtre supplémentaire = code à écrire, pas un simple glisser-déposer Metabase)
- ❌ ADR-008 (Docker Compose Metabase) devient obsolète pour son scaffolding Metabase — le reste (Postgres + dbt conteneurisés) reste valide

### Documents mis à jour en conséquence
`README.md` (stack), `shared/INDEX.md` (stack), `bi/07_Dictionnaire_KPI_Technique.md` (encadrés KPI-403/405).

---

## Résumé Stack

```
DAMS (Django, PostgreSQL)
        ↓
    dbt run (nightly 23h)
        ↓
PostgreSQL schéma `bi_`
(facts + dimensions)
        ↓
App Django `bi` (SSR + Chart.js CDN) — Metabase abandonné, voir ADR-009
        ↓
PDF exports Excel (rapports)
```

**Infrastructure** :
- PostgreSQL (LWS cPanel) – 0€
- dbt Core (local ou VM) – 0€
- App Django `bi` (déjà servie par l'app DAMS existante) – 0€
- **Total : 0€ (MVP)**

**Timing**:
- Semaine 1-2 : dbt modeling + tests
- Semaine 3 : dashboards Metabase
- Semaine 4 : validation + exports
- **Go-live** : Fin juillet 2026

# Sprint 2 — Dimensions + Dashboards v1 (12–18 juillet 2026)

> ℹ️ **Ajusté après Sprint 1 (17/07/2026).** Les dimensions sont déjà livrées (`dim_agent`, `dim_produit`, `dim_fournisseur`, `dim_temps`) — voir [sprints/SPRINT_1_Fondations.md](SPRINT_1_Fondations.md). **`dim_superviseur` séparée n'existe pas** : un superviseur est un `Agent` avec `type_agent='entrepot'` (confirmé [architecte/REFERENCE_TECHNIQUE_BI.md](../architecte/REFERENCE_TECHNIQUE_BI.md)) — les dashboards filtrent `dim_agent WHERE type_agent='entrepot'`, pas de table séparée à créer. Le jour "Lun 12" ci-dessous est donc libéré pour démarrer Metabase plus tôt.
>
> **Préalable ajouté avant le reste du sprint : conteneurisation (ADR-008).** Le projet (Postgres + dbt + scaffold Metabase) est désormais orchestré via `docker-compose.yml` à la racine — restauration du dump `input/*.dump` automatique et unique au premier démarrage du volume Postgres (`docker/postgres/init/01-restore.sh`), profil dbt versionné dans le repo (`dbt/profiles.yml`). Voir `dbt/README.md` pour les commandes. Décision associée : on ne touche pas au PostgreSQL de production (R15 mis à jour dans `chef_projet/RISQUES.md`) — le dump reste la source de données. Docker Desktop Windows s'étant montré instable, le développement se poursuit depuis WSL2 (R16) ; validation du `docker compose up`/`dbt build` en conteneur faite côté utilisateur, hors session agent.
>
> **17/07/2026 (suite) — Metabase connecté, hors Docker.** Le build de l'image `dbt` custom (WSL2) est resté bloqué >1h sur un `uv pip install` (souci réseau, R16). Contournement : Metabase OSS installé nativement sur Windows (`java -jar metabase.jar`, port 3001 — 3000 pris par Grafana en local), connecté directement au PostgreSQL local (`dams_dev`, schéma `bi_`) déjà utilisé pour les tests dbt. Connexion validée par l'utilisateur, données `bi_` consultables dans Metabase. Reste : construire les 5 dashboards (Mar 13–Ven 16 du plan) à partir des 5 vues `vw_*` ci-dessous.
>
> **17/07/2026 — Modèles dbt des 5 dashboards livrés en local (fallback venv, pendant que le build Docker/WSL2 tournait en parallèle).** 5 vues d'agrégats créées dans `dbt/models/marts/aggregates/` (matérialisation `view`, schéma `bi_`) : `vw_rentabilite_globale` (D1), `vw_rentabilite_produit` (D2), `vw_performance_superviseur` (D3), `vw_performance_agent` (D4, statut vs objectif 50 kg/jour), `vw_analyse_stock` (D5). `dbt build` complet local (contre `dams_dev` restaurée localement, hors conteneur) : 111 PASS, 1 WARN (déjà connu, R14/Sprint 1), 0 ERROR. Temps d'exécution mesurés par `EXPLAIN ANALYZE` sur les 5 vues : 1–5 ms (jeu de données dev, largement sous le seuil 2s — à reconfirmer une fois Metabase branché sur le volume Docker, le jeu de données de prod pouvant être plus volumineux). Reste à faire une fois les conteneurs up : brancher Metabase sur `bi_`, construire les 5 dashboards visuels à partir de ces vues (le SQL est prêt, le travail restant est de la mise en forme Metabase).

**Objectif** : Metabase connecté + 5 dashboards v1 (requêtes < 2s). *(dimensions déjà faites en Sprint 1)*
**Jalon Roadmap** : G2 — *Dashboards v1 opérationnels*
**Owner sprint** : BI Dev (exécution) / Chef Projet (gate)

---

## Backlog du sprint

Voir détail complet dans [owner/02_Backlog.md](../owner/02_Backlog.md).

| # | Story | Priorité |
|---|-------|----------|
| S-003 | ~~Finalisation des 5 dimensions~~ | ✅ Fait Sprint 1 (4 dims — superviseur = `dim_agent` filtrée, pas de 5ᵉ table) |
| S-101 | CA, coût d'achat, marge brute du semestre (Dashboard 1) | 🔴 MUST |
| S-201 | Classement produits par marge (Dashboard 2) | 🔴 MUST |
| S-301 | CA et marge par superviseur (Dashboard 3) | 🔴 MUST |
| S-401 | Agents atteignant l'objectif 50kg/jour (Dashboard 4) | 🔴 MUST |
| S-501 | Valeur totale du stock immobilisé (Dashboard 5) | 🔴 MUST |

---

## Plan jour par jour

| Jour | Livrable | Owner | Validation |
|------|----------|-------|------------|
| Lun 12 | Metabase configuré (service déjà scaffoldé dans `docker-compose.yml`, ADR-008), connecté au schéma `bi_` du conteneur `postgres` | Architecte | BI Dev |
| Mar 13 – Mer 14 | 5 dashboards shells créés | BI Dev | Architecte |
| Jeu 15 – Ven 16 | 5 dashboards v1 avec visualisations de base (< 2s) | BI Dev | PO + Architecte |
| **17/07 (hors planning, en parallèle du build Docker)** | **5 vues SQL `vw_*` livrées et testées en local** (`dbt/models/marts/aggregates/`) — le socle requête de chaque dashboard existe et est validé < 2s ; reste le câblage Metabase (Lun 12) et la mise en forme visuelle (Mar 13–Ven 16) une fois les conteneurs up | BI Dev | — |

---

## Definition of Done du sprint

Sous-ensemble de [chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md) applicable — *pour une Dimension* et *pour un Dashboard Metabase (v1)* :

- [x] Dimensions : table < 1k lignes, clé primaire simple, ≥ 3 colonnes descriptives *(Sprint 1)*
- [ ] Dashboard : au moins 5 visualisations (charts, tables, cards) — *bloqué sur Metabase (conteneurs en build)*
- [x] Requêtes SQL optimisées : temps d'exécution < 2s *(vues `vw_*` validées 1–5 ms sur `dams_dev` local, 17/07 — à reconfirmer volumétrie prod une fois Metabase branché)*
- [x] Aucun NULL anormal affiché (ou justifié) *(coalesce systématique dans les 5 vues ; NULL restants sont volontaires — ex. `marge_pct` non calculable si CA=0)*
- [ ] Titres explicites (ex: "Rentabilité Nette Superviseur (FCFA)") — *à faire côté Metabase*

## Gate de sortie (G2)

- [x] Dimensions en place *(Sprint 1)*
- [ ] 5 dashboards opérationnels, requêtes < 2s
- [ ] Premiers KPI visibles dans chaque dashboard

**Décision** : GO Sprint 3 / NO-GO (bloquants à documenter dans [chef_projet/RISQUES.md](../chef_projet/RISQUES.md))

---

## Rétrospective

- Qu'est-ce qui a bien marché ?
- Qu'est-ce qui a bloqué ?
- Statut : 🟢 / 🟡 / 🔴
- Ajustements pour Sprint 3 :

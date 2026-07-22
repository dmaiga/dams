# Suivi de mission – DAMS BI

**Propriétaire** : Chef de Projet
**Destinataire** : Direction / suivi de mission
**Date** : 22 juillet 2026 (Sprint 3, jour prévu de la réunion Direction — [SPRINT_3_Validation_Metier.md](../sprints/SPRINT_3_Validation_Metier.md))
**Portée** : état d'avancement du MVP + reste à faire, suite à la première revue utilisateur du 20/07/2026.

---

## 1. Résumé exécutif

Le socle du MVP est livré et fonctionnel : infrastructure dbt, 5 fact tables, 4 dimensions,
5 vues d'agrégats, **5 dashboards en production** (Sprints 1 et 2 clos, gates G1/G2 passées).
La première revue utilisateur (20/07) a validé le fond (chiffres cohérents) et remonté 3
questions fonctionnelles (Q1–Q3) + 5 suggestions, toutes documentées dans
[QUESTIONS_OUVERTES.md](QUESTIONS_OUVERTES.md).

Ce document ajoute au périmètre déjà tranché **quatre axes non couverts jusqu'ici** :
**UI/UX, performance, optimisation, orchestration**. Il regroupe tout ce qui reste à faire
dans un plan de charge unique, et propose un tri MUST/SHOULD/COULD pour tenir le go-live du
**30 juillet** sans sacrifier la qualité.

**Statut global** : 🟢 dans les temps, aucun bloquant P1 (voir [RISQUES.md](RISQUES.md)).

---

## 2. Ce qui est livré (Sprints 1–2, clos)

| Livrable | Statut | Écart au plan initial |
|----------|--------|------------------------|
| Projet dbt (`dbt_bi/`) + schéma `bi_` | ✅ | — |
| 5 fact tables + 4 dimensions | ✅ | Pas de `dim_superviseur` séparée (superviseur = `Agent` filtré), assumé et documenté |
| 71+ tests dbt | ✅ | 111 PASS / 1 WARN documenté / 0 ERROR |
| 5 vues d'agrégats (`vw_*`) | ✅ | Requêtes 1–5 ms en dev — à reconfirmer sur volumétrie prod (voir §5.2) |
| 5 dashboards | ✅ | **Restitution Django SSR + Chart.js, pas Metabase** ([ADR-009](../architecte/04_ADR.md#adr-009--metabase-abandonné--restitution-django-ssr--chartjs)) — décision prise en cours de route, impact positif (un service de moins à opérer) mais rend obsolètes les tâches Metabase encore écrites dans [SPRINT_2](../sprints/SPRINT_2_Modeles_Dashboards.md)/[SPRINT_4](../sprints/SPRINT_4_GoLive.md) |
| Accès BI | ⚠️ garde-fou temporaire | Restreint au seul compte `mdmaiga` (`bi/views.py`) — pas un vrai contrôle de rôle, cf. suggestion §4 |

**Conséquence à noter** : le Sprint 4 tel qu'écrit (« Déploiement Metabase », `docker-compose`
scaffold Metabase) doit être relu à la lumière d'ADR-009 avant exécution — les tâches
concernées sont déjà obsolètes, pas seulement en retard.

---

## 3. Retour de la revue utilisateur du 20/07 (Q1–Q3)

Détail complet dans [QUESTIONS_OUVERTES.md](QUESTIONS_OUVERTES.md). Résumé :

| # | Sujet | Nature | Statut |
|---|-------|--------|--------|
| Q1 | Agrégations paramétrables (group by produit/agent/catégorie) | Fonctionnel, nécessite clarification Direction | 🆕 |
| Q2 | Dashboard 4 : filtre période inopérant + objectif à lire en série temporelle | Fonctionnel + technique (nouvelle vue dbt) | 🔎 diagnostiqué |
| Q3 | Dashboard 5 : vue trop détaillée, vision globale par fournisseur attendue | Fonctionnel, nécessite clarification | 🆕 |

Suggestions capturées en marge (non demandées explicitement, à trier) : contrôle d'accès par
rôle, comparaison M-1/tendance 6 mois, export Excel/CSV, dépenses non catégorisées, recherche/
tri sur les tableaux.

---

## 4. Axes non couverts jusqu'ici (ajoutés à ce document)

Ces quatre axes n'apparaissaient dans aucun livrable remis à ce jour — ni dans les questions
ouvertes, ni dans les sprints — et sont désormais tracés dans le backlog (§6).

- **UI/UX** : les 5 dashboards fonctionnent mais n'ont pas reçu de passe de polish dédiée
  (cohérence visuelle entre les 5 pages, lisibilité du feu tricolore 🔴🟡🟢, responsive écran
  réduit, états vides/erreur).
- **Performance** : les temps de requête (1–5 ms) n'ont été mesurés que sur `dams_dev`
  (dump local, volumétrie de développement). Jamais reconfirmés sur une volumétrie proche de
  la production, ni sous charge (plusieurs utilisateurs Direction simultanés).
- **Optimisation** : pas d'index dédiés ajoutés sur les colonnes de jointure/filtre des vues
  `bi_.vw_*` (R4 dans [RISQUES.md](RISQUES.md), toujours 🟡 WATCH, jamais traité concrètement).
- **Orchestration** : le refresh nuit (`dbt run` 23h00 Mali, ADR-006) n'est pas déployé — reste
  une story `SHOULD` du Sprint 4 (S-005), jamais démarrée. Sans elle, les dashboards restent
  figés sur la dernière exécution manuelle, ce qui contredit l'hypothèse « données à jour
  chaque matin » du DoD.

---

## 5. Plan de charge — reste à faire

Estimations en jours-homme (solo, Mahamane — cf. R3). À valider/ajuster une fois les
clarifications Direction obtenues (Q1/Q3 notamment, dont l'effort dépend fortement de la
réponse).

### 5.1 Fonctionnel (issu de la revue du 20/07)

| Item | Effort estimé | Dépendance |
|------|---------------|------------|
| Q2 — nouvelle dimension temporelle `vw_performance_agent` (semaine/mois) + filtres superviseur/type_agent | 2–3 j | Aucune, prêt à démarrer |
| Q1 — agrégations paramétrables | 0,5 j clarification + 2–4 j dev | Réponse Direction : dashboard(s) visé(s) + vue dbt figée ou group-by dynamique |
| Q3 — vue globale par fournisseur + filtres | 0,5 j clarification + 1–2 j dev | Réponse Direction : simple regroupement visuel ou valeur agrégée (rejoint Q1) |
| Contrôle d'accès par rôle (remplacer `bi_access_required` username) | 0,5 j | Aucune |
| Comparaison M-1 / tendance 6 mois (rejoint Q2) | 1–2 j | Mutualisable avec Q2 |
| Export Excel/CSV des tableaux | 1 j | Aucune |
| Recherche/tri côté tableaux | 1 j | Aucune |
| Dépenses « Non catégorisé » | 0,5 j (signalement DAMS, pas un dev BI) | Décision Direction sur la saisie DAMS |

### 5.2 Performance / optimisation

| Item | Effort estimé | Dépendance |
|------|---------------|------------|
| Reconfirmer < 2s sur volumétrie proche prod (pas seulement `dams_dev`) | 0,5 j | Accès à un jeu de données représentatif |
| Index PostgreSQL sur colonnes de jointure/filtre des `vw_*` (R4) | 0,5–1 j | Après §5.2 mesure |
| Test de charge basique (plusieurs sessions Direction simultanées) | 0,5 j | Optionnel — volumétrie MVP faible (ADR-001) |

### 5.3 Orchestration

| Item | Effort estimé | Dépendance |
|------|---------------|------------|
| Cron `dbt run` nightly 23h00 Mali (ADR-006, S-005) | 1 j | Accès serveur production confirmé (R15 — jamais validé, cf. Sprint 4) |
| Logs + alerte email en cas d'échec du run (ADR-007, facteur XI, jamais fait) | 0,5–1 j | Après mise en place du cron |
| Re-scoper le Sprint 4 pour retirer les tâches Metabase obsolètes (ADR-009) | 0,5 j | Aucune — à faire en premier, avant tout le reste |

### 5.4 UI/UX

| Item | Effort estimé | Dépendance |
|------|---------------|------------|
| Passe de cohérence visuelle sur les 5 dashboards (couleurs, titres, espacement) | 1 j | Aucune |
| Vérification responsive / lisibilité feu tricolore | 0,5 j | Aucune |
| États vides / erreurs (ex. aucune donnée sur la période) | 0,5 j | Aucune |

**Total estimé** : **~14–21 jours-homme**, hors aléas de clarification Direction (Q1/Q3).

---

## 6. Tri proposé pour tenir le Go-Live du 30/07

Il reste **6 jours ouvrés** entre aujourd'hui (22/07) et le go-live prévu (30/07,
[SPRINT_4_GoLive.md](../sprints/SPRINT_4_GoLive.md)). Le total du plan de charge (~14–21 j)
ne rentre pas dans cette fenêtre en solo. Proposition de tri, cohérente avec le MoSCoW déjà
posé dans [02_Backlog.md](../owner/02_Backlog.md) et avec [03_Roadmap.md](../owner/03_Roadmap.md)
(qui prévoit déjà un traitement des nouvelles questions métier post-go-live) :

**🔴 Avant le 30/07 (bloquant qualité/sécurité du go-live)**
- Re-scoper Sprint 4 (retirer Metabase obsolète)
- Contrôle d'accès par rôle (sécurité, pas du confort)
- Cron nightly + logs (le DoD promet « données à jour chaque matin »)
- Reconfirmer perf sur volumétrie prod + index si besoin

**🟡 Si le temps le permet avant le 30/07**
- Q2 (retour direct de la Direction le 20/07, donc visible si non traité)
- Passe UI/UX minimale (cohérence + responsive)

**🟢 Repoussé en v1.5 (août), déjà cohérent avec la Roadmap**
- Q1, Q3 (nécessitent clarification + développement dbt conséquent)
- Export Excel/CSV, recherche/tri tableaux
- Comparaison M-1/tendance (déjà prévue v1.5 dans [03_Roadmap.md](../owner/03_Roadmap.md))
- Dépenses non catégorisées (dépend d'une décision côté saisie DAMS, hors main BI)

**Décision à valider par la Direction** : confirmer ce tri lors de la réunion du 22/07, ou
lors du sign-off, avant de figer le plan du Sprint 4.

---

## 7. Suivi

Toutes les stories listées ici sont ajoutées au backlog produit
([02_Backlog.md](../owner/02_Backlog.md), EPIC 7) avec leur priorité. Ce document est un
instantané au 22/07 — à remettre à jour à la prochaine review de risques (Ven 25 Juil) ou plus
tôt si le tri §6 change.

# DAMS BI – Backlog Produit

**Propriétaire** : Product Owner (Mahamane Daouda Maïga)
**Audience** : Toute l'équipe (Architecte, BI Dev, Chef Projet)
**Fréquence mise à jour** : Chaque sprint
**Dernière modification** : 2 juillet 2026
**Version** : 1.0

---

## Comment lire ce backlog

Chaque story suit le format : **En tant que** [rôle], **je veux** [besoin], **afin de** [valeur].

Priorités (MoSCoW) :
- 🔴 **MUST** — indispensable au MVP (livraison 30 juil.)
- 🟡 **SHOULD** — important, dans le MVP si le temps le permet
- 🟢 **COULD** — confort, repoussable en V1.5
- ⚪ **WON'T (now)** — hors périmètre MVP (voir [03_Roadmap.md](03_Roadmap.md))

Chaque story est rattachée à une **question métier** (Q1–Q10 de [01_Vision_Produit.md](01_Vision_Produit.md)) et à un **dashboard** (D1–D5 de [../bi/08_Dashboard_Catalog.md](../bi/08_Dashboard_Catalog.md)).

---

## EPIC 0 — Fondations données (infrastructure)

| # | Story | Priorité | Rattachement |
|---|-------|----------|--------------|
| S-001 | En tant qu'**Architecte**, je veux un projet dbt + schéma `bi_` isolé, afin de construire sans impacter la prod DAMS. | 🔴 MUST | — |
| S-002 | En tant que **BI Dev**, je veux 5 fact tables (ventes, salaires, dépenses, stocks, + agrégats), afin d'alimenter tous les KPI. | 🔴 MUST | tous |
| S-003 | En tant que **BI Dev**, je veux 5+ dimensions (agent, superviseur, produit, fournisseur, temps), afin de filtrer/croiser les analyses. | 🔴 MUST | tous |
| S-004 | En tant que **Chef Projet**, je veux 15+ tests dbt (nullité, unicité, logique métier), afin de garantir la fiabilité des chiffres. | 🔴 MUST | tous |
| S-005 | En tant qu'**Architecte**, je veux un refresh batch nuit (23h00 Mali), afin d'avoir des données à jour chaque matin. | 🟡 SHOULD | tous |

---

## EPIC 1 — Santé financière globale → **Dashboard 1**

> Répond à : Q1 (santé globale), Q9 (janvier vs juin)

| # | Story | Priorité |
|---|-------|----------|
| S-101 | En tant que **Directeur**, je veux voir **CA, coût d'achat, marge brute** du semestre, afin de savoir si on gagne de l'argent. | 🔴 MUST |
| S-102 | En tant que **Directeur**, je veux le KPI **Rentabilité nette** (marge − salaires − dépenses), afin de connaître le vrai bénéfice après tous les coûts. | 🔴 MUST |
| S-103 | En tant que **Directeur**, je veux une **courbe d'évolution mensuelle** (jan → juin), afin de voir si la tendance s'améliore ou baisse. | 🔴 MUST |
| S-104 | En tant que **Directeur**, je veux un **feu tricolore** 🟢🟡🔴 sur la santé, afin de comprendre en 3 secondes. | 🟡 SHOULD |

---

## EPIC 2 — Rentabilité produit → **Dashboard 2**

> Répond à : Q2 (produits rentables), Q5 (fournisseurs), Q8 (anomalies à perte)

| # | Story | Priorité |
|---|-------|----------|
| S-201 | En tant que **Manager Produit**, je veux le **classement des produits par marge**, afin de savoir lesquels développer. | 🔴 MUST |
| S-202 | En tant que **Manager Produit**, je veux repérer les **produits vendus à perte** (prix vente < prix achat), afin de les arrêter. | 🔴 MUST |
| S-203 | En tant que **Manager Produit**, je veux la **marge par fournisseur**, afin d'identifier qui tue nos marges. | 🟡 SHOULD |
| S-204 | En tant que **Manager Produit**, je veux voir les **produits qui dorment en stock**, afin de libérer du capital. | 🟡 SHOULD |

---

## EPIC 3 — Performance superviseur → **Dashboard 3**

> Répond à : Q3 (superviseurs), Q7 (dépenses), Q10 (trésorier/ROT)

| # | Story | Priorité |
|---|-------|----------|
| S-301 | En tant que **Manager RH/Ops**, je veux le **CA et la marge par superviseur**, afin de savoir qui rapporte le plus. | 🔴 MUST |
| S-302 | En tant que **Manager RH/Ops**, je veux le **coût équipe réel** (salaires + incentives) par superviseur, afin de repérer les équipes non rentables. | 🔴 MUST |
| S-303 | En tant que **Manager RH/Ops**, je veux les **dépenses ROT par catégorie** (transport, carburant, maintenance), afin de savoir où va l'argent. | 🟡 SHOULD |
| S-304 | En tant que **Finance**, je veux le KPI **Dépenses ROT %** (dépenses / cash superviseur), afin d'alerter quand > 15% du CA. | 🟢 COULD |

---

## EPIC 4 — Performance agent → **Dashboard 4**

> Répond à : Q4 (qui vend / ne travaille pas), Q8 (anomalies)

| # | Story | Priorité |
|---|-------|----------|
| S-401 | En tant que **Superviseur**, je veux voir quels agents **atteignent l'objectif de 50 kg/jour**, afin de repérer les sous-performants. | 🔴 MUST |
| S-402 | En tant que **Manager RH/Ops**, je veux le KPI **Agents déficitaires** (incentive > marge générée), afin de restructurer. | 🔴 MUST |
| S-403 | En tant que **Superviseur**, je veux voir les agents qui **vendent au rabais** (CA correct mais marge faible), afin de les recadrer. | 🟡 SHOULD |
| S-404 | En tant que **Superviseur**, je veux des **alertes visuelles** 🔴 sur les agents sous objectif, afin d'agir vite. | 🟡 SHOULD |

---

## EPIC 5 — Stock & fournisseurs → **Dashboard 5**

> Répond à : Q6 (argent gelé en stock), Q5 (fournisseurs)

| # | Story | Priorité |
|---|-------|----------|
| S-501 | En tant que **Manager Produit**, je veux la **valeur totale du stock** immobilisé, afin de connaître le capital gelé. | 🔴 MUST |
| S-502 | En tant que **Manager Produit**, je veux la **rotation de stock** par produit (CA / stock moyen), afin de distinguer les produits rapides des morts. | 🔴 MUST |
| S-503 | En tant que **Manager Produit**, je veux les **jours en stock** par produit, afin de repérer ce qui dort > 1 mois. | 🟡 SHOULD |

---

## EPIC 6 — Documentation & mise en service

| # | Story | Priorité |
|---|-------|----------|
| S-601 | En tant que **utilisateur**, je veux un **dbt docs (lineage)**, afin de comprendre d'où vient chaque chiffre. | 🟡 SHOULD |
| S-602 | En tant que **Directeur**, je veux un **export Excel mensuel**, afin de partager les chiffres hors outil. | 🟡 SHOULD |
| S-603 | En tant que **Direction**, je veux une **formation (30 min)** + guide de lecture, afin d'être autonome sur les dashboards. | 🔴 MUST |
| S-604 | En tant que **Direction**, je veux une **feuille de route d'amélioration de DAMS** (données manquantes, règles, contrôles), afin de tirer une valeur durable au-delà des dashboards. → journal à tenir en continu dans [../architecte/AMELIORATIONS_DAMS.md](../architecte/AMELIORATIONS_DAMS.md) | 🟡 SHOULD |

---

## Hors périmètre MVP (⚪ WON'T now)

Ces demandes sont capturées mais planifiées après le go-live (voir [03_Roadmap.md](03_Roadmap.md)) :

- Assistant BI conversationnel (RAG + LLM)
- Alertes automatiques par email (prix anormal, produit déficitaire)
- Prévisions de ventes (ML / time-series)
- Recommandations produit (quoi commander)
- Analyse des dettes clients (crédit)
- Périodes calendaires flexibles (multi-périodes)

---

## Définition de « prêt » et « terminé »

- **Prêt (Ready)** : story rattachée à une question + un dashboard, KPI défini dans [../bi/07_Dictionnaire_KPI_Technique.md](../bi/07_Dictionnaire_KPI_Technique.md).
- **Terminé (Done)** : voir [../chef_projet/09_Qualite_DoD.md](../chef_projet/09_Qualite_DoD.md) (implémenté en dbt + testé + visible en Metabase + validé PO).

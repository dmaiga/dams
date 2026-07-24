# Feuille de route – Améliorations du système DAMS

**Propriétaire** : Architecte Data (avec contributions BI Dev)
**Audience** : Architecte, BI Dev, Chef Projet, Direction (synthèse)
**Fréquence mise à jour** : En continu, tout au long du projet
**Dernière modification** : 24 juillet 2026 (RM-02, FL-01 — corrections `paie`)
**Version** : 1.1

---

## Pourquoi ce document

Le projet BI ne se limite pas à produire des tableaux de bord. En analysant les données réelles de DAMS (période 01/01 → 30/06), nous découvrons inévitablement des **limites du système lui-même** : données manquantes, règles non appliquées, flux perfectibles.

Ce fichier est le **journal vivant** de ces observations. Il alimente la *« feuille de route d'amélioration continue »* promise à la Direction dans [../owner/00_Note_Direction.md](../owner/00_Note_Direction.md).

> **Règle simple** : dès qu'une anomalie ou une opportunité d'amélioration DAMS est constatée pendant le développement dbt / l'exploration des données, on **l'ajoute ici tout de suite** (une ligne suffit). On triera et priorisera plus tard.

---

## Comment remplir

- **Catégorie** : voir les 5 axes ci-dessous.
- **Impact** : 🔴 fort / 🟡 moyen / 🟢 faible (effet sur la fiabilité des décisions).
- **Effort** : estimation grossière (S = petit, M = moyen, L = gros).
- **Statut** : 🆕 relevé · 🔎 à confirmer · ✅ transmis à l'équipe DAMS · ⏸️ reporté.

---

## 1. Règles métier à renforcer

*Contrôles métier qui devraient exister dans DAMS mais ne sont pas (ou mal) appliqués.*

| # | Observation | Impact | Effort | Statut | Date |
|---|-------------|--------|--------|--------|------|
| RM-01 | *(exemple)* Ventes enregistrées avec prix de vente < prix d'achat sans blocage ni alerte | 🔴 | M | 🆕 | — |
| RM-02 | Génération de paie : le filtre d'éligibilité agent se basait sur `est_actif` **au moment de la génération**, pas sur la période réellement travaillée — un agent parti depuis produisait des mois d'historique sous-évalués (impact direct sur KPI-005/006/009 côté BI). Corrigé dans `paie/services/agent_eligibilite.py` (23/07/2026, filtre sur la période travaillée). | 🟡 | S | ✅ | 2026-07-23 |
| | | | | | |

---

## 2. Contrôles automatiques à ajouter

*Vérifications automatiques (saisie, cohérence) à intégrer dans DAMS.*

| # | Observation | Impact | Effort | Statut | Date |
|---|-------------|--------|--------|--------|------|
| CA-01 | | | | | |
| | | | | | |

---

## 3. Données actuellement manquantes

*Informations dont on aurait besoin pour l'analyse mais qui ne sont pas collectées par DAMS.*

| # | Observation | Impact | Effort | Statut | Date |
|---|-------------|--------|--------|--------|------|
| DM-01 | Renégociations fournisseur post-réception non capturables dans DAMS : le prix d'achat négocié réellement (ex. 300 cartons saisis à 12 000, réalité 150 à 11 000 + 150 à 10 500) peut diverger du `prix_achat_unitaire` figé sur `core_lotentrepot` à la réception, sans mécanisme de correction dans DAMS. Contournement BI : `bi.AjustementPrixAchat` (saisie admin Direction), agrégé en moyenne pondérée dans `vw_marge_fournisseur` (dbt-2, 20/07/2026) — corrige uniquement le reporting, pas la donnée source `core_lotentrepot`. | 🟡 | M | ✅ | 2026-07-20 |
| | | | | | |

---

## 4. Simplification de flux opérationnels

*Étapes ou processus DAMS qui pourraient être simplifiés / automatisés.*

| # | Observation | Impact | Effort | Statut | Date |
|---|-------------|--------|--------|--------|------|
| FL-01 | Génération des salaires mensuels nécessitait un clic manuel Direction chaque mois. Nouvelle commande `generer_salaires_mensuel` (app `paie`) pour rattraper/générer les salaires sans intervention manuelle — répond au même besoin de fraîcheur des données que le cron `dbt run` nightly (S-711, encore non fait côté BI) ; les deux pourraient être orchestrés ensemble une fois en production. | 🟡 | S | ✅ | 2026-07-23 |
| | | | | | |

---

## 5. Nouveaux indicateurs à intégrer dans l'ERP

*KPI utiles qui gagneraient à être calculés directement dans DAMS (pas seulement en BI).*

| # | Observation | Impact | Effort | Statut | Date |
|---|-------------|--------|--------|--------|------|
| IND-01 | | | | | |
| | | | | | |

---

## Synthèse pour la Direction (à remplir en fin de projet)

En clôture (semaine 4), consolider ici les 5 à 10 recommandations les plus importantes, en langage clair, pour la présentation de go-live.

1. …
2. …
3. …

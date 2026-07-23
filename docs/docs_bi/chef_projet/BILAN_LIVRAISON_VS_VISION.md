# Bilan de livraison — Vision/Backlog vs réalisé (session du 23/07/2026)

**Propriétaire** : Chef de Projet / PO
**Audience** : Direction, Product Owner, toute l'équipe
**Fréquence mise à jour** : à chaque session de développement significative
**Dernière modification** : 23 juillet 2026
**Version** : 1.0

---

## 1. Objectif de ce document

[QUESTIONS_OUVERTES.md](QUESTIONS_OUVERTES.md) capture les retours de la revue du 20/07.
[SUIVI_MISSION_BI.md](SUIVI_MISSION_BI.md) fige un plan de charge au 22/07. Depuis, une session
de développement dense (23/07) a livré une bonne partie de ce plan — mais pas tout, et pas
toujours de la façon prévue. Ce document :

1. Confronte ce qui était **prévu** (owner/, bi/08_Dashboard_Catalog.md, backlog EPIC 7) à ce
   qui est **réellement livré** aujourd'hui.
2. Signale ce qui a été **ajouté sans être demandé** dans le backlog (initiatives nées de la
   discussion directe avec la Direction pendant la session).
3. Liste ce qu'il **reste à faire**, avec un tri repris du plan de charge du 22/07.
4. Propose des **mises à jour concrètes** des documents owner/bi pour rester synchronisés avec
   le code réel.

**Ne remplace pas** `SUIVI_MISSION_BI.md` (toujours valide sur le contexte du 22/07) ni le
backlog (`02_Backlog.md`, source de vérité des priorités) — vient en complément, à date plus
récente sur ce qui est effectivement livré.

---

## 2. EPIC 7 (backlog du 22/07) — statut après la session du 23/07

| # | Story | Statut au 22/07 | Statut au 23/07 | Écart |
|---|-------|------------------|------------------|-------|
| S-701 | Agrégations paramétrables (group by) | 🆕 non traité | ⚪ non traité | Toujours en attente de clarification Direction — voir §5 |
| S-702 | Filtre période Dashboard 4 + objectif en série temporelle | 🔎 diagnostiqué | 🟡 **partiel** | Filtre mois opérant (nouveau grain `vw_performance_agent` agent x mois) ; mais série lue **mensuelle**, pas hebdomadaire comme demandé — l'objectif reste une photo par mois, pas une courbe de progression |
| S-702b | Filtre superviseur + type_agent sur Dashboard 4 | 🆕 non traité | 🟡 **partiel** | Filtre **superviseur** livré ; filtre **type_agent** absent |
| S-703 | Vision globale par fournisseur (Dashboard 5) | 🆕 non traité | 🟡 **partiel** | Filtres produit/fournisseur livrés ; mais toujours un tableau plat, pas le regroupement visuel "Fournisseur → liste produits" demandé |
| S-703b | Filtres fournisseur/produit (Dashboard 5) | 🆕 non traité | ✅ **livré** | + la calibration prix d'achat (`vw_marge_fournisseur`) est aussi devenue fournisseur x **produit** x mois (non demandé, va au-delà) |
| S-704 | Contrôle d'accès par rôle (remplacer `username == 'mdmaiga'`) | 🔴 MUST, non traité | ❌ **non traité** | Toujours le garde-fou temporaire par username. Marqué 🔴 bloquant avant go-live dans `SUIVI_MISSION_BI.md` §6 — **risque non réduit** |
| S-705 | Comparaison M-1 / tendance 6 mois | 🟡 non traité | ❌ **non traité** | — |
| S-706 | Export Excel/CSV des tableaux | 🟢 non traité | ❌ **non traité** | — |
| S-707 | Signaler les dépenses "Non catégorisé" à la Direction | 🟢 non traité | 🟡 **traité différemment** | Décision prise : les rattacher silencieusement à `DIVERS` plutôt que les signaler comme demandé. Ce n'est pas ce que demandait la story — voir §4.4 |
| S-708 | Recherche/tri dans les tableaux | 🟢 non traité | ❌ **non traité** | — |
| S-709 | Passe de cohérence UI/UX | 🔴 MUST, non traité | 🟡 **partiel** | Graphiques rendus responsives (conteneur dimensionné, `maintainAspectRatio:false`) ; filtres repositionnés à côté du filtre temporel. Pas de passe systématique couleurs/titres/espacement/états vides sur les 5 pages |
| S-710 | Perf sur volumétrie prod + index PostgreSQL (R4) | 🔴 MUST, non traité | 🟡 **partiel** | Cause racine trouvée et corrigée : vues agrégées passées de `materialized: view` à `table` (recalcul à chaque requête → recalcul au `dbt run` seulement). Mesure sur volumétrie proche prod et index PostgreSQL dédiés **toujours pas faits** |
| S-711 | Cron `dbt run` nightly + logs/alerte email | 🔴 MUST, non traité | ❌ **non traité côté dbt** | Rien fait sur le refresh dbt nocturne. Une automatisation **paie** (`generer_salaires_mensuel`, hors périmètre de cette story) a été livrée pour un besoin connexe — voir §4.5 |
| S-712 | Re-scoper Sprint 4 (retirer Metabase obsolète) | 🔴 MUST, non traité | ❌ **non traité** | Tâche de planning pure, pas de code — reste à faire par le Chef de Projet |

**Lecture rapide** : sur les 4 items marqués 🔴 MUST avant le 30/07 dans `SUIVI_MISSION_BI.md`
§6, **aucun n'est complètement clos** — S-704 (sécurité) et S-711 (fraîcheur des données) sont
les deux qui restent entièrement à zéro. S-709 et S-710 ont progressé mais ne sont pas finis.

---

## 3. Ce qui a été ajouté sans être dans le backlog

Initiatives nées d'échanges directs avec la Direction pendant la session, absentes du backlog
EPIC 7 — à statuer (garder, documenter, ou objecter) plutôt qu'à ignorer :

### 3.1 Restructuration des dashboards
Le "Dashboard 3 : Performance Superviseur & Dépenses" (tel que spécifié dans
`bi/08_Dashboard_Catalog.md`) a été **scindé** : la partie Superviseur a été fusionnée dans le
Dashboard 4 ("Performance Agent & Équipes"), et la partie Dépenses est devenue un dashboard
autonome. Le Dashboard_Catalog reste donc **désynchronisé du produit réel** sur ce point (voir
§6.1).

### 3.2 "Dernier mois par défaut" généralisé
Toutes les pages filtrables affichent désormais le dernier mois disponible par défaut (au lieu
de "Toutes périodes" cumulé) — décision produit prise en session, absente du backlog, mais qui
répond indirectement à l'esprit de S-705 (situer un chiffre dans le temps).

### 3.3 Nouveaux KPI hors dictionnaire
`KPI-002` (Coût d'achat) et `KPI-010` (Marge nette %) ont été ajoutés à Santé Globale sans
exister dans `bi/07_Dictionnaire_KPI_Technique.md` / `07_Dictionnaire_KPI_Metier.md` — **ces
deux dictionnaires sont maintenant incomplets par rapport au code** (voir §6).

### 3.4 Priorité Marge Brute > Rentabilité Nette (Santé Globale)
Écart le plus structurant : `00_Note_Direction.md` et `01_Vision_Produit.md` posent la
**rentabilité nette** (marge − salaires − dépenses) comme *"le chiffre central de tout le
projet"*, et une des cases à valider par la Direction est *"la rentabilité nette est bien le
chiffre le plus important à suivre"*. La session du 23/07 a **inversé cette priorité pour la
phase actuelle** : Santé Globale met en avant la marge brute (carte principale, section dédiée)
et relègue la marge nette à une section secondaire. C'était une demande explicite et assumée
("pour la phase de ce projet, l'objectif est plus de déterminer la marge brute que la nette"),
mais **la Vision Produit n'a pas été mise à jour en conséquence** — un lecteur de
`01_Vision_Produit.md` aujourd'hui se ferait une idée fausse de ce que montre le dashboard 1.

### 3.5 Fenêtre d'analyse glissante (dépasse la période figée MVP)
`03_Roadmap.md` classe explicitement les **"périodes calendaires flexibles (multi-périodes)"**
en **v2.0 hors MVP**, et `04_ADR.md` (ADR-004) fige la période à 01/01–30/06/2026. Or le système
livré fonctionne désormais sur un **mois glissant** (dernier mois disponible, y compris
juillet 2026 et au-delà) sans aucune borne de fin — une capacité v2 a donc été livrée de facto,
en avance sur la roadmap, sans que l'ADR-004 soit amendé ou que la Direction ait tranché sur
l'extension de la période d'analyse.

### 3.6 Corrections côté `paie` (hors périmètre BI, mais impactant les KPI)
Deux corrections ont été apportées à l'app `paie` pour que le KPI coût salarial soit fiable :
- Le filtre d'éligibilité agent (génération de paie) se basait sur `est_actif` **au moment de
  la génération**, pas sur la période réellement travaillée — un agent parti depuis produisait
  des mois d'historique sous-évalués. Corrigé (`paie/services/agent_eligibilite.py`).
- Nouvelle commande `generer_salaires_mensuel` pour rattraper/générer les salaires sans clic
  manuel mensuel Direction.

Ce sont exactement le type d'améliorations que `00_Note_Direction.md` §"Valeur ajoutée pour
DAMS" annonçait ("règles métier à renforcer", "feuille de route d'amélioration continue") —
**mais elles ne sont tracées nulle part** dans `architecte/AMELIORATIONS_DAMS.md`, le journal
prévu pour ce type de constat (cf. S-604 du backlog). À faire.

### 3.7 Calibration prix d'achat rattachée au lot
`AjustementPrixAchat` (dbt-2, KPI-403/404/405) a été repensé : rattaché directement à un
`LotEntrepot` au lieu d'un fournisseur/année/mois/produit saisis à la main. Corrige au passage
un bug de contamination croisée entre produits d'un même fournisseur (la correction de prix
s'appliquait à tort à tous les produits livrés par ce fournisseur ce mois-là). Non demandé par
le backlog, mais aligné avec l'esprit dbt-2 déjà planifié.

---

## 4. Ce qui manque encore (priorités reprises du 22/07, encore valables)

Le tri du 22/07 (`SUIVI_MISSION_BI.md` §6) reste largement d'actualité. Mise à jour :

**🔴 Toujours bloquant avant toute diffusion à plusieurs personnes de la Direction**
- **S-704 — Contrôle d'accès par rôle.** C'est le seul écart de cette liste qui est un vrai
  risque de sécurité, pas un confort. Tant que l'accès reste `username == 'mdmaiga'`, aucune
  autre personne de la Direction ne peut utiliser les dashboards sans partager un compte.
- **S-711 — Cron `dbt run` nightly + alerte.** Sans lui, chaque nouveau chiffre (y compris les
  corrections de cette session) doit être poussé manuellement en base — le DoD promet des
  données à jour chaque matin, ce n'est pas le cas.
- **S-710 (reste)** — mesurer sur une volumétrie proche prod et ajouter les index PostgreSQL
  manquants ; la matérialisation en table a traité la cause la plus visible, pas nécessairement
  toute la question de performance à l'échelle.
- **S-712** — re-scoper le Sprint 4 (tâche de planning, 0,5 j, aucune dépendance).

**🟡 Si le temps le permet**
- Compléter S-702/S-702b (série hebdomadaire, filtre type_agent).
- Finir la passe UI/UX (S-709) au-delà des graphiques responsives.
- Compléter S-703 (vue groupée par fournisseur, pas seulement des filtres).

**🟢 Toujours repoussable en v1.5**
- S-701, S-705, S-706, S-708 — inchangés, aucun développement cette session.
- S-707 — à retrancher/reformuler : le choix de `DIVERS` a résolu le symptôme différemment
  (absorption silencieuse) de la demande initiale (signalement explicite) ; la Direction devrait
  confirmer si l'absorption dans `DIVERS` suffit ou si un signalement reste souhaité.

---

## 5. Recommandations pour alimenter le backlog / se projeter vers une v2

1. **Ouvrir une story dédiée pour S-704 en priorité absolue** — c'est le seul point non traité
   qui bloque littéralement l'usage multi-utilisateur des dashboards. Recommandation :
   `type_agent == 'direction'`, sur le modèle de ce qui existe déjà pour l'admin
   `AjustementPrixAchat` (`bi/admin.py:_est_direction`).
2. **Amender ADR-004** (ou créer un ADR-010) pour documenter que la période d'analyse est
   désormais glissante, pas figée au 30/06 — sinon l'architecture documentée contredit le
   comportement réel du système.
3. **Mettre à jour `bi/08_Dashboard_Catalog.md`** pour refléter les 5 dashboards réels
   (Santé Globale, Rentabilité Produit, **Performance Agent & Équipes**, **Dépenses**, Stock &
   Fournisseur) — la partition actuelle du catalogue (Dashboard 3 = Superviseur+Dépenses) ne
   correspond plus au produit livré.
4. **Compléter `bi/07_Dictionnaire_KPI_Technique.md` et `07_Dictionnaire_KPI_Metier.md`** avec
   KPI-002 (Coût d'achat) et KPI-010 (Marge nette %), et noter le changement de priorité
   Marge Brute / Rentabilité Nette sur Dashboard 1.
5. **Faire trancher la Direction sur la priorité Marge Brute vs Rentabilité Nette** — la
   Vision Produit dit une chose, le produit livré en fait une autre pour l'instant assumée
   "pour cette phase" ; il faut acter explicitement si c'est un changement durable ou une
   étape transitoire, et le documenter dans `01_Vision_Produit.md`.
6. **Journaliser les corrections `paie`** (agents éligibles par période, génération automatique)
   dans `architecte/AMELIORATIONS_DAMS.md`, comme prévu par S-604.
7. **Ajouter une story v2 explicite** pour la fenêtre d'analyse glissante (déjà livrée de facto)
   plutôt que de la laisser non documentée — capitaliser sur ce qui existe déjà techniquement.
8. **Considérer le cron `dbt run` + automatisation paie comme un socle commun v1.5** —
   `generer_salaires_mensuel` (paie) et le cron dbt (S-711) répondent au même besoin de
   fraîcheur des données sans intervention manuelle ; les regrouper dans une seule story
   d'orchestration éviterait de les traiter comme deux chantiers séparés.

---

## 6. Documents propriétaires à mettre à jour (hors ce fichier)

| Document | Propriétaire | Mise à jour nécessaire |
|----------|---------------|------------------------|
| `bi/08_Dashboard_Catalog.md` | BI Dev | Refléter la fusion Superviseur/Agent et le dashboard Dépenses autonome (§3.1) |
| `bi/07_Dictionnaire_KPI_Technique.md` + `_Metier.md` | BI Dev | Ajouter KPI-002, KPI-010 ; noter le changement de priorité marge brute/nette (§3.3, §3.4) |
| `owner/01_Vision_Produit.md` | PO | Trancher et documenter marge brute vs rentabilité nette comme chiffre central (§3.4) |
| `architecte/04_ADR.md` (ADR-004) | Architecte | Amender ou compléter sur la fenêtre d'analyse glissante (§3.5) |
| `architecte/AMELIORATIONS_DAMS.md` | Architecte/PO | Journaliser les corrections `paie` (§3.6) |
| `owner/02_Backlog.md` (EPIC 7) | PO | Mettre à jour les statuts S-701 à S-712 selon le tableau §2 |
| `chef_projet/RISQUES.md` | Chef de Projet | Réévaluer R4 (perf) à la lumière de la matérialisation en table (§2, S-710) |

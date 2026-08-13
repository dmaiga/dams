# 📘 App : `surveillance` (Gouvernance, Surveillance des Prix & Analyse des Flux)

## 📌 Rôle & Vision

L'application `surveillance` constitue la **tour de contrôle analytique et réglementaire** du système DAMS. Contrairement aux modules purement opérationnels de saisie terrain, son rôle principal est de surveiller en continu les indicateurs de performance clés (KPI), de détecter les anomalies commerciales (notamment les ventes à perte ou "rouges") et de mesurer les variations de volumes (kg vendus) d'une période à l'autre.

Elle offre aux profils de direction et de contrôle une visibilité à 360° sur l'activité des superviseurs d'entrepôts, des agents et sur la rentabilité des stocks de produits.

---

## ⚙️ Architecture Applicative & Structure des Vues

L'application repose sur l'utilisation systématique de **Class-Based Views (CBV)** héritant de `TemplateView`. Elle applique un cloisonnement strict entre la gestion des requêtes HTTP (les vues) et la logique métier de calcul ou d'agrégation, entièrement déléguée à une couche de **Services**.

```text
+-------------------------------------------------------------+
|                     surveillance / views.py                 |
|  (Interception requêtes HTTP, Injection listes de choix)    |
+-------------------------------------------------------------+
                               |
                               v  (Appels méthodes statiques)
+-------------------------------------------------------------+
|                  surveillance / services /                  |
|  (ComparaisonPeriode, VenteSurveillance, SurveillancePrix)  |
+-------------------------------------------------------------+

```

---

## 🗂️ Matrice des Composants & Vues Métier

### 1. Tableau de Bord de Surveillance (`DashboardSurveillanceView`)

Génère la synthèse globale de la santé commerciale et des alertes de l'écosystème.

* **Template associé** : `surveillance/dashboard_surveillance.html`
* **Logique métier & Indicateurs calculés** :
* Extrait de manière dynamique les périodes temporelles (semaine actuelle vs précédente, mois actuel vs précédent) via `ComparaisonPeriodeService`.
* Calcule le volume total en kilogrammes vendus et calcule le pourcentage de variation d'une période à l'autre (`ComparaisonService.variation`).
* Intercepte l'ensemble des **ventes dites "rouges"** (ventes à perte) via le `PrixSurveillanceService` et transmet le compte total ainsi que les 10 premières anomalies pour affichage immédiat.
* Injecte les classements de performances et variations hebdomadaires des 5 premiers superviseurs et produits.



### 2. Suivi et Analyse des Volumes (`ListeKgVenduView`)

Interface d'analyse granulaire permettant d'évaluer les flux de marchandises sortantes (kg) selon des filtres temporels et structurels.

* **Template associé** : `surveillance/kg_vendu/liste_kg_vendu.html`
* **Paramètres d'URL interceptés (`GET`)** : `periode` (semaine ou mois — implémenté le 2026-08-13, la vue
  ne le lisait pas jusque-là malgré cette section), `superviseur` (ID), `produit` (ID).
* **Données et Contextes injectés** :
* Les statistiques globales et de performance (`kpis`, `superviseurs_stats`, `agents_stats`) générées dynamiquement par `ListeKgVenduService` — le service reste agnostique de `periode`, il reçoit juste `(date_debut, date_fin)` déjà résolues par la vue (`ComparaisonPeriodeService.mois()`/`week_utils.parse_semaine`).
* La liste des superviseurs actifs d'entrepôt (utilisateurs filtrés sur `Agent.objects.filter(type_agent="entrepot", est_actif=True)`).
* L'intégralité du catalogue des produits pour alimenter les listes de sélection des filtres de l'interface.

**Filtre période partagé** (`partials/_filtre_periode.html`, 2026-08-13) : bascule Semaine/Mois
(liens `?periode=semaine|mois`, défaut semaine) + champ de saisie adapté (`<input type="week">` ou
`<input type="month">`). Réutilisé par `liste_kg_vendu.html` et `detail_produit.html` — remplace
`partials/_filtre_semaine.html` sur ces deux pages (`_filtre_semaine.html` reste utilisé tel quel par
`dashboard_surveillance.html`/`detail_superviseur.html`, qui n'ont pas de mode mensuel). Utilitaires
associés : `week_utils.parse_mois`/`date_to_month_string`/`qs_mois`,
`ComparaisonPeriodeService.mois(debut)`/`mois_prec(debut)` (variantes paramétrées de
`mois_actuel()`/`mois_precedent()`, qui restent inchangées pour leurs appelants existants).

`detail_superviseur.html` a par ailleurs reçu (2026-08-13) un filtre **produit** dédié sur son tableau
Agents (`DetailSuperviseurService.get_data(..., produit=...)`), sur le même modèle que
`ListeKgVenduService.get_agents(..., produit=...)` — restreint uniquement ce tableau, jamais les KPI
globaux du superviseur.



### 3. Module d'Audit des Tarifs & Rentabilité (`SurveillancePrixView` & `DetailPrixView`)

Assure la surveillance de la cohérence des prix pratiqués par rapport aux seuils de rentabilité des stocks.

* **Vues implémentées** :
* `SurveillancePrixView` (Vue d'ensemble) : Récupère le résumé global des prix de marché et des marges via `SurveillancePrixService.get_resume()`. Template : `surveillance/prix/surveillance_prix.html`.
* `DetailPrixView` (Vue granulaire) : Cible un lot d'entrepôt spécifique (`LotEntrepot`) passé en paramètre d'URL via sa clé primaire (`lot_id`). Elle injecte l'analyse détaillée des coûts et prix appliquée à ce lot exact. Template : `surveillance/prix/detail_prix.html`.



### 4. Fiches de Suivi Détaillées (`DetailProduitView` & `DetailSuperviseurView`)

Permettent de zoomer sur un acteur ou une marchandise pour en comprendre l'historique de surveillance.

* **`DetailProduitView`** : Récupère l'historique et les indicateurs propres à un modèle `Produit` ciblé par sa clé primaire (`pk`) via `DetailProduitService.get_data()`. Template : `surveillance/produits/detail_produit.html`.
* **`DetailSuperviseurView`** : Récupère les métriques de contrôle d'un superviseur (modèle `Agent`) ciblé par sa clé primaire (`pk`) via `DetailSuperviseurService.get_data()`. Template : `surveillance/superviseur/detail_superviseur.html`.

Ces deux vues sont transverses : atteignables depuis "Kg vendus", "Anomalies prix" et "Stock & Rotation". Le paramètre `?from=kg|prix|stock` porté par chaque lien entrant est lu par la vue (`self.request.GET.get("from", "kg")`) et exposé en contexte sous `origine` — voir section Navigation.

### 5. Suivi Durée de Vie du Stock (`StockRotationView`)

Vue dédiée au thème "Stock & Rotation" (Sprint 04 / Chantier 2 du backlog). Délégation complète au
service `StockAgeService` (`surveillance/services/stock_age_service.py`).

**Recadrage du 2026-08-13** : cette page affiche désormais **uniquement le stock dormant à l'entrepôt
central** (non distribué). Elle n'affiche plus ni la rétention chez les superviseurs/agents, ni
l'activité commerciale des agents — ces deux tableaux ont été retirés (`RotationLenteListView`
supprimée, avec sa route `/surveillance/stock-rotation/rotation-lente/`, son template et son partial
`_table_rotation_lente.html`) car ils faisaient doublon, avec moins de précision, avec
`direction.suivi_distributions` (filtrable par agent/superviseur/produit/période, quantité restante
réelle par distribution) — les mélanger sur cette page induisait en erreur plutôt qu'il n'aidait.

* **Template associé** : `surveillance/stock_rotation/dashboard_stock.html`.
* **Source** : `StockAgeService.lots_dormants_entrepot()` / `count_lots_dormants_entrepot()` /
  `valeur_stock_dormant_entrepot()` — méthodes dédiées UI, requêtes SQL pures sur `LotEntrepot`
  uniquement (`quantite_restante > 0`, `date_reception` antérieure à `DELAI_STOCK_DORMANT_JOURS = 15`
  jours, postérieure à `DATE_PLANCHER_STOCK`). Aucun calcul de rétention superviseur/agent déclenché
  par cette page.
* Vue dédiée « voir tout » : `StockDormantListView` (`/surveillance/stock-rotation/stock-dormant/`),
  paginée (`Paginator`, 20/page), réutilisant `partials/_table_stock_dormant.html` (recentré
  entrepôt-only : plus de branche superviseur/agent dans le template).
* Le dashboard global (`DashboardSurveillanceView`) affiche le même total (`nb_lots_dormants`,
  entrepôt uniquement) dans sa carte « Stock dormant ».

#### Ce que cette page ne fait plus (et pourquoi) — voir `monitoring/APP_MONITORING.md`

L'UI et la notification Telegram n'ont pas la même portée : `StockAgeService` garde ses méthodes
3-origines (`lots_stock_dormant()`, `count_lots_stock_dormant()`, `valeur_stock_dormant()`, seuils
différenciés entrepôt/superviseur/agent) et son calcul d'activité commerciale globale
(`agents_sans_vente_recente()`), mais **exclusivement pour le moteur d'alertes de `monitoring`** —
plus aucune vue `surveillance` ne les appelle.

**Incident de performance corrigé** : avant ce recadrage, `StockRotationView` appelait ces méthodes
3-origines, dont le calcul de rétention agent (`_lignes_stock_retenu_agents`, N+1 sur
`DetailDistribution.quantite_restante_calculee`, property à 2 requêtes par ligne) — répété 3 fois par
requête HTTP (liste + `count_*` + `valeur_*`, chacun recalculant indépendamment). Observé en
production : ~2400 requêtes SQL, 7s de temps de réponse sur `/surveillance/stock-rotation/`. Les
nouvelles méthodes entrepôt-only n'exécutent jamais ce calcul. Testé (`StockRotationViewTestCase`,
`surveillance/tests.py`) : la page reste sous un budget de 40 requêtes même avec plusieurs
distributions âgées en base.

---

## 🧭 Navigation thématique commune

Un seul partial, `surveillance/templates/partials/_nav_themes.html`, porte les 4 onglets de premier niveau (Vue d'ensemble / Volumes / Prix / Stock & Rotation), inclus par les 10 templates de l'app (7 vues historiques + `stock_rotation` + les 2 pages de liste complète). Il remplace les blocs de liens ad hoc précédemment dupliqués (tabs sur le dashboard, paires de `btn btn-outline` ailleurs), chacun avec un style différent. Sur chaque page, la nav est placée sur sa propre ligne pleine largeur sous le titre (`overflow-x-auto`), pour ne pas entrer en conflit avec le filtre semaine quand les deux coexistent dans le header.

Chaque vue injecte `context["theme"]` (`"accueil"|"kg"|"prix"|"stock"`) pour marquer l'onglet actif. Pour `DetailProduitView`/`DetailSuperviseurView`, `theme` prend la valeur d'`origine` (le thème d'où vient l'utilisateur), puisque ces fiches sont transverses et n'ont pas de thème propre.

Le filtre semaine (`semaine_selectionnee` / `qs_semaine`) est propagé dans les liens de nav partout où il s'applique (dashboard, Kg vendus, fiches produit/superviseur). Les pages Prix et Stock & Rotation n'ont pas de filtre semaine actif ; `SurveillancePrixView` se contente de reporter un `semaine` éventuellement présent dans l'URL entrante, pour ne pas casser le contexte de nav si l'utilisateur y accède depuis une page filtrée.

---

## 🧪 Points de Vigilance pour la Maintenance et le Code

* **Couplage Fort avec l'application `core**` : Les vues effectuent des requêtes directes et des vérifications sur les modèles partagés `Produit`, `Agent` (notamment le champ `type_agent="entrepot"`) et `LotEntrepot`. Toute modification de structure sur ces modèles dans l'application `core` doit être répercutée et testée ici.
* **Sécurisation des Identifiants (`kwargs`)** : Portez une attention particulière au nommage des paramètres capturés dans vos fichiers d'URLs (`urls.py`). La vue `DetailPrixView` recherche explicitement la clé `self.kwargs["lot_id"]` tandis que les vues de détails de produit et superviseur s'appuient sur la clé standard `self.kwargs["pk"]`.
* **Performance des Requêtes (Slicing)** : Le tableau de bord et les listes effectuent des limitations rigoureuses en fin de traitement (ex: `ventes_rouges[:10]`, `superviseurs[:5]`). Pour optimiser la charge sur la base de données PostgreSQL en production, il conviendra de s'assurer que ces limites sont appliquées directement au niveau des requêtes SQL (via l'ORM dans les Services correspondants) plutôt que sur des listes Python déjà chargées en mémoire.
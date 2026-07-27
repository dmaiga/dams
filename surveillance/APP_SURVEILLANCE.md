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
* **Paramètres d'URL interceptés (`GET`)** : `periode` (semaine ou mois), `superviseur` (ID), `produit` (ID).
* **Données et Contextes injectés** :
* Les statistiques globales et de performance (`kpis`, `superviseurs_stats`, `agents_stats`) générées dynamiquement par `ListeKgVenduService`.
* La liste des superviseurs actifs d'entrepôt (utilisateurs filtrés sur `Agent.objects.filter(type_agent="entrepot", est_actif=True)`).
* L'intégralité du catalogue des produits pour alimenter les listes de sélection des filtres de l'interface.



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

Vue dédiée au thème "Stock & Rotation" (Sprint 04 / Chantier 2 du backlog). Délégation complète au service `StockAgeService` (`surveillance/services/stock_age_service.py`), sur le modèle exact de `SurveillancePrixService`.

* **Template associé** : `surveillance/stock_rotation/dashboard_stock.html`.
* **Pas de filtre semaine** : les deux alertes se calculent sur une fenêtre glissante depuis `timezone.now()` (constantes `DELAI_ROTATION_JOURS = 2`, `DELAI_STOCK_DORMANT_JOURS = 14` dans `surveillance/constants.py`), pas depuis une semaine calendaire sélectionnée.
* **Alerte 1 — rotation lente** (`StockAgeService.agents_sans_vente_recente()`) : `DetailDistribution` dont la distribution (`DistributionAgent.date_distribution`) date de plus de 2 jours, et dont la dernière `Vente` non supprimée associée (s'il y en a une) date aussi de plus de 2 jours. Une seule requête SQL (agrégation `Max` + filtre `HAVING` via `Q(OR)`), jamais de boucle Python avec requête par itération. Chaque ligne porte l'ID de la `DistributionAgent` et du `DetailDistribution` (liens directs vers l'admin Django), pour permettre la suppression d'un enregistrement erroné.
* **Alerte 2 — stock dormant** (`StockAgeService.lots_stock_dormant()`) : deux sources fusionnées, chacune filtrée avec `quantite_restante > 0` et une ancienneté de plus de 14 jours —
  * `LotEntrepot` encore en entrepôt central (ancienneté sur `date_reception`) ;
  * `AffectationLotSuperviseur` mis à disposition d'un superviseur mais pas encore redistribué à un agent terrain (ancienneté sur `date_affectation`).

  Chaque ligne porte `reference_lot`, la localisation ("Entrepôt central" ou le superviseur concerné) et l'ID de l'objet source (lien admin direct : `LotEntrepot` ou `AffectationLotSuperviseur` selon l'origine).
* **Plancher `DATE_PLANCHER_STOCK`** (`date(2026, 5, 15)`, alignée sur `DATE_DEBUT_SUIVI_TERRAIN` dans `direction/views.py`) : les distributions/affectations antérieures sont ignorées par les deux alertes — données historiques non fiables pour ce type de détection.
* Chaque alerte a sa méthode `count_*` (COUNT SQL pur, pour les badges) et sa méthode de détail avec `limit` appliqué au niveau SQL.
* Le dashboard global (`DashboardSurveillanceView`) n'affiche qu'un résumé chiffré agrégé (carte "Stock & Rotation", même traitement que la carte "Anomalies prix") — pas de tableau détaillé dupliqué. La vue `StockRotationView` affiche un aperçu (10 premiers par alerte) avec un lien "Voir tout →" vers deux vues dédiées sans limite : `RotationLenteListView` (`/surveillance/stock-rotation/rotation-lente/`) et `StockDormantListView` (`/surveillance/stock-rotation/stock-dormant/`), toutes deux réutilisant les partials `partials/_table_rotation_lente.html` et `partials/_table_stock_dormant.html`.

---

## 🧭 Navigation thématique commune

Un seul partial, `surveillance/templates/partials/_nav_themes.html`, porte les 4 onglets de premier niveau (Vue d'ensemble / Volumes / Prix & Rentabilité / Stock & Rotation), inclus par les 8 templates de l'app (y compris les fiches de détail). Il remplace les blocs de liens ad hoc précédemment dupliqués (tabs sur le dashboard, paires de `btn btn-outline` ailleurs), chacun avec un style différent.

Chaque vue injecte `context["theme"]` (`"accueil"|"kg"|"prix"|"stock"`) pour marquer l'onglet actif. Pour `DetailProduitView`/`DetailSuperviseurView`, `theme` prend la valeur d'`origine` (le thème d'où vient l'utilisateur), puisque ces fiches sont transverses et n'ont pas de thème propre.

Le filtre semaine (`semaine_selectionnee` / `qs_semaine`) est propagé dans les liens de nav partout où il s'applique (dashboard, Kg vendus, fiches produit/superviseur). Les pages Prix et Stock & Rotation n'ont pas de filtre semaine actif ; `SurveillancePrixView` se contente de reporter un `semaine` éventuellement présent dans l'URL entrante, pour ne pas casser le contexte de nav si l'utilisateur y accède depuis une page filtrée.

---

## 🧪 Points de Vigilance pour la Maintenance et le Code

* **Couplage Fort avec l'application `core**` : Les vues effectuent des requêtes directes et des vérifications sur les modèles partagés `Produit`, `Agent` (notamment le champ `type_agent="entrepot"`) et `LotEntrepot`. Toute modification de structure sur ces modèles dans l'application `core` doit être répercutée et testée ici.
* **Sécurisation des Identifiants (`kwargs`)** : Portez une attention particulière au nommage des paramètres capturés dans vos fichiers d'URLs (`urls.py`). La vue `DetailPrixView` recherche explicitement la clé `self.kwargs["lot_id"]` tandis que les vues de détails de produit et superviseur s'appuient sur la clé standard `self.kwargs["pk"]`.
* **Performance des Requêtes (Slicing)** : Le tableau de bord et les listes effectuent des limitations rigoureuses en fin de traitement (ex: `ventes_rouges[:10]`, `superviseurs[:5]`). Pour optimiser la charge sur la base de données PostgreSQL en production, il conviendra de s'assurer que ces limites sont appliquées directement au niveau des requêtes SQL (via l'ORM dans les Services correspondants) plutôt que sur des listes Python déjà chargées en mémoire.
# Sprint 11 — Fiche détail agent (BI) : objectifs, produits vendus, stock en main

**Statut** : ✅ terminé (18/08/2026) — demande de mdmaiga (approfondir la couche BI, ajouter une
fiche détail par agent), quatre décisions d'architecture actées le même jour (trois avant
rédaction du sprint, une quatrième pendant l'implémentation — voir § Décisions actées et
§ Décision actée en cours d'implémentation).

Réalisé : `stg_pertes.sql` étendu (`detail_distribution_id`), deux nouveaux marts
(`fct_stock_agent.sql`, `aggregates/vw_ventes_agent_produit.sql`, testés `dbt run`/`dbt test`
avec succès), `vw_performance_agent(_semaine).sql` corrigés pour le kilo net, deux nouveaux
modèles Django `managed=False` (`bi/models.py`), une nouvelle vue
`bi/views.py::dashboard_agent_detail` + route `bi:agent_detail`, un nouveau template
`bi/templates/bi/dashboard_agent_detail.html`, un lien cliquable ajouté depuis
`dashboard_agents.html`. Vérifié en conditions réelles via le client Django (page 200, trois
blocs rendus avec données réelles). Documentation mise à jour
(`08_Dashboard_Catalog.md`, `07_Dictionnaire_KPI_Metier.md`).

**Extension le même jour** (mdmaiga, plusieurs demandes après la première version) :
- Bascule Mois / Semaine sur le bloc "Atteinte des objectifs" (comme `dashboard_agents`), avec
  comparaison n vs n-1 (delta kg vendus vs la période précédente, valeur + %) — la réunion
  hebdomadaire du lundi porte sur le progrès semaine par semaine, pas seulement mensuel.
- Incentive calculée en direct (kg net × `RegleSalaire.incentive_par_kg`, lue en direct côté
  Django, pas en dbt). **Correction en cours de route** : j'avais d'abord justifié cet ajout par
  "l'incentive officielle dépend d'une génération manuelle de paie" — mdmaiga a signalé que ce
  n'était plus vrai, et la vérification (`paie/services/salaire_liste_service.py`) lui a donné
  raison sur le fond : la vue Direction "liste des salaires" appelle déjà
  `CalculatorSalaire.calcul_salaire_mamy(...)` **en direct**, sans jamais lire le modèle `Salaire`
  stocké — aucune génération manuelle n'est requise pour connaître un salaire au quotidien. Le
  modèle `Salaire`/`SalaireGenerationService` existe toujours mais sert un usage séparé et
  optionnel (verrouiller/archiver un montant). L'incentive affichée sur la fiche détail reproduit
  donc exactement le calcul déjà utilisé par `paie` — retiré le terme "projetée" (renommée en
  simplement "Incentive") et l'incentive verrouillée (`fct_salaires`) n'est plus affichée que si
  elle existe réellement (`{% if periode_courante.incentive %}`), en complément, pas comme
  référence. Masquable avec CA/marge via le même bouton "Masquer les données sensibles" que le
  reste de l'app.
- Lien vers la fiche détail ajouté aussi depuis le graphique "Kg/jour vs objectif" (pas seulement
  depuis le tableau en dessous).
- Tableau "Performance agent vs objectif" allégé : Jours actifs/Jours ouvrés fusionnés en un seul
  champ ("15/26"), delta kg vendus vs période précédente ajouté (même pattern que le delta
  superviseur), colonne "Statut objectif" retirée au profit d'un badge de couleur directement sur
  la valeur Kg/jour. Colonne Type retirée (reste filtrable via le sélecteur existant).
  **Correction** : j'avais aussi retiré Rentabilité par erreur d'interprétation — mdmaiga a
  clarifié que la colonne restait un bon indicateur à garder, seul son caractère
  masquable/affichable (comme CA/marge, via le bouton "Masquer les données sensibles" déjà
  présent) devait être préservé. Réintégrée avec `class="bi-sensible"`, couverte automatiquement
  par le toggle existant.

**Fiche détail superviseur** (mdmaiga, cadrée par questions avant codage — voir § Décisions
actées superviseur) : pendant de la fiche agent à l'échelle d'une équipe.
- Bascule Mois/Semaine + n vs n-1, comme la fiche agent.
- Volume de ventes mis en avant en premier (axe principal demandé) : kg vendus équipe + delta,
  objectif équipe dérivé (nb_agents_actifs × 50 kg/jour), CA moyen par agent vs
  `CA_MOYEN_AGENT_CIBLE` (existait déjà, jamais branché — KPI-407), coût/rentabilité équipe (mois
  uniquement).
- Bloc agents de l'équipe (drill-down vers la fiche agent de chacun).
- Bloc produits vendus agrégé équipe, avec filtre par produit (+ tendance 6 mois du produit
  filtré).
- Bloc stock en main agrégé équipe (batch, comme la fiche agent).
- Décision d'implémentation : équipe/stock/produits calculés sur la hiérarchie ACTUELLE
  (`core.Agent.superviseur_id`), pas la hiérarchie embarquée dans `FctStockAgent`/`fct_ventes`
  (au moment de la distribution) — garantit la cohérence entre tous les blocs de la page.
- Nouvelles routes/vues : `bi:superviseur_detail`, lien ajouté depuis le tableau "Performance
  équipes/superviseurs" (Partie 1). Nouvelle fonction `bi/constants.py::statut_ca_moyen_agent`.
  Aucun nouveau mart dbt requis (tout est réutilisé/agrégé côté Django).
- Vérifié en conditions réelles (mois, semaine, filtre produit, cas nb_agents_actifs=0).

## Décisions actées superviseur (mdmaiga, 18/08/2026, avant codage)

1. Contenu : liste des agents de l'équipe (lien), coût/rentabilité équipe, CA moyen par agent vs
   cible, stock en main agrégé équipe — les quatre retenus.
2. Objectif équipe : somme des 50 kg/jour de chaque agent actif (pas de nouveau seuil arbitraire).
3. Volume décomposé par produit, avec un filtre par produit (pas seulement une tendance globale).

**Révision demandée par mdmaiga après la première version** :
- Retrait du KPI "Coût équipe" — les 4 KPI restants (Kg vendus, Objectif équipe, CA moyen,
  Rentabilité nette) tiennent sur la même ligne.
- Le filtre produit devait aussi agir sur le **tableau agents** (pas seulement le tableau
  produits) : ajout de `kg_vendus_produit`/`kg_vendus_produit_delta` par agent, affichés à la
  place des totaux équipe quand un produit est filtré (mois uniquement — pas de grain
  hebdomadaire pour `vw_ventes_agent_produit`, message explicite affiché en vue semaine).
- Comparaison n vs n-1 ajoutée aussi sur le tableau produits (pas seulement le KPI global et le
  tableau agents).
- Graphique de tendance repensé : un seul graphique combiné (barres = kg vendus équipe, courbes
  = kg vendus par produit, une couleur par produit) plutôt qu'un mini-graphique séparé pour le
  produit filtré. Sans filtre, les 5 produits les plus vendus sur la fenêtre sont tracés
  (évite un graphique surchargé) ; avec filtre, uniquement le produit sélectionné.
- Ordre de page imposé : KPIs → tableau produits → tableau agents → graphes tendance → stock en
  main (auparavant : KPIs+tendance ensemble, puis agents, puis produits+mini-tendance, puis
  stock).

## Passage UI/UX (mdmaiga, 18/08/2026) — boutons d'en-tête mal organisés

Constat : sur `dashboard_agents.html`, `dashboard_agent_detail.html` et
`dashboard_superviseur_detail.html`, les contrôles d'en-tête (bouton Retour, bascule Mois/Semaine,
formulaire de période, bouton "Masquer les données sensibles") étaient chacun dans leur propre
`<div>`, empilés verticalement — jusqu'à 4 rangées avant tout contenu utile.

Correctifs (spec précise fournie par mdmaiga, suivie à la lettre) :
- Nouvelle classe `.bi-toolbar` (`bi/static/bi/dashboard.css`) : une seule rangée flex,
  `justify-content: space-between`, filtres à gauche (`.bi-toolbar-left`, `flex-wrap: nowrap`),
  bouton données sensibles à droite (`.bi-toolbar-right`). `.bi-periode-form` passé en
  `inline-flex` compact.
- Grille KPI à exactement 4 cartes sur les deux fiches détail : plutôt que de modifier la règle
  CSS partagée `.bi-kpi.bi-principal` (utilisée aussi par `dashboard_sante.html`,
  `dashboard_produits.html`, `dashboard_stock.html` — la modifier aurait cassé leurs grilles),
  la classe a été retirée directement du markup des deux fiches détail. Sur la fiche agent, la
  vraie cause de la rupture de ligne était une **5ᵉ carte** ("Incentive verrouillée", visible
  seulement si une paie était générée) — fusionnée comme sous-ligne dans la carte "Incentive"
  plutôt que gardée comme carte séparée, pour garantir 4 cartes en toute circonstance.
- Vérifié : exactement 4 `.bi-kpi` dans `.bi-kpis` sur les deux fiches, mois et semaine ;
  `bi-principal` absent des deux ; `dashboard_sante/produits/stock` toujours 200 (non-régression).
- Non vérifié visuellement (pas d'outil de capture d'écran/navigateur disponible dans cet
  environnement) — à confirmer par mdmaiga en conditions réelles.

**Deuxième passe (mdmaiga, même jour)** : la toolbar avait beau être compacte, elle était encore
réécrite en entier (avec son wrapper `.bi-toolbar`) par chacune des 3 pages qui l'utilisaient —
duplication et risque de divergence future. Remontée dans le gabarit parent
`bi/templates/bi/base_dashboard.html` : la structure `.bi-toolbar > .bi-toolbar-left (bloc
`retour` + bloc `filtre_periode`) / .bi-toolbar-right (bloc `toolbar_actions`)` est désormais
définie **une seule fois**, avec deux nouveaux blocs overridables (`retour`, `toolbar_actions`)
en plus de `filtre_periode`/`extra_filtres` qui existaient déjà. Chaque page enfant ne fournit
plus que son contenu spécifique (le bouton Retour, la bascule + le formulaire, le bouton
masquer/afficher), sans plus jamais réécrire le wrapper. Bénéfice non cherché mais bienvenu :
`dashboard_sante.html`, `dashboard_produits.html`, `dashboard_depenses.html` et
`dashboard_stock.html` (qui n'avaient jamais été touchés) héritent automatiquement de la même
toolbar propre, sans aucune modification de leur part — vérifié (`bi-toolbar` présent une seule
fois sur les 7 pages BI, `bi-retour`/`bi-toggle-sensible` uniquement là où prévu).

**Troisième passe (mdmaiga, même jour)** : retour en arrière partiel sur les blocs `retour`/
`toolbar_actions` — mdmaiga a jugé que forcer ces deux slots nommés dans le gabarit pour des
éléments qui ne concernent que 3 pages sur 7 était un sur-travail imposé au gabarit plutôt qu'une
simplification. Structure finale : `base_dashboard.html` ne fournit plus que le `<div
class="bi-toolbar">` vide et **un seul** bloc `filtre_periode` (comme à l'origine) ; chaque page
qui a besoin d'un bouton Retour, d'une bascule mois/semaine ou d'un bouton "données sensibles"
compose entièrement son `.bi-toolbar-left`/`.bi-toolbar-right` à l'intérieur de ce bloc unique.
Les pages qui n'ont besoin que du formulaire par défaut (`dashboard_sante.html`,
`dashboard_produits.html`, etc.) restent inchangées. Vérifié par recherche exacte des balises
(`<div class="bi-toolbar-left">`/`<div class="bi-toolbar-right">`, pas une recherche de
sous-chaîne — un faux positif du panneau Debug Toolbar en environnement DEBUG, qui réinjecte le
texte des commentaires Django template ailleurs dans la page, avait d'abord fait croire à un
doublon) : exactement 1 `.bi-toolbar-left` sur les 7 pages, `.bi-toolbar-right` uniquement sur
les 3 pages agent/équipe.

Reste à faire manuellement en déploiement : `dbt run` complet (les nouveaux marts et les deux
corrigés) sur la base de production.

## Contexte

L'app `bi` (v1 livrée le 24/07/2026, cf. `docs/docs_bi/chef_projet/BILAN_LIVRAISON_VS_VISION.md`
§8) expose aujourd'hui 5 dashboards (`bi/urls.py`) : `sante`, `produits`, `agents`, `depenses`,
`stock` — **tous plats, aucun drill-down individuel**. Le "Dashboard 3 : Agent"
(`docs/docs_bi/bi/08_Dashboard_Catalog.md`, lignes 101-176) affiche un tableau multi-agents
(kg vendus, kg/jour, statut objectif 50kg, rentabilité) mais aucune page ne permet de cliquer sur
un agent pour voir son détail. C'est le trou que ce sprint comble : une fiche détail accessible
depuis une ligne du tableau `dashboard_agents.html`, avec trois blocs demandés par mdmaiga —
atteinte des objectifs, produits vendus, stock actuellement en main.

Ce sprint est aussi l'occasion de noter (§ Constat 4, hors périmètre immédiat) que les 4 autres
dashboards (`produits`, `depenses`, `stock`, et le volet équipe de `agents`) partagent le même
manque de profondeur — susceptible de justifier des sprints du même type plus tard.

---

## Décisions actées (mdmaiga, 18/08/2026)

1. **Objectif agent** : pas de nouveau champ/table. La fiche réutilise les deux seuils déjà en
   place — 50 kg/jour (`vw_performance_agent.sql`, déjà en dbt) et 750 kg/mois (seuil du salaire
   fixe, `paie/services/salaire_calculator.py`). Aucun objectif personnalisable par agent pour
   l'instant.
2. **Stock en main** : nouveau mart dbt (batch), pas de lecture temps réel depuis Django/OLTP.
   Motivation explicite de mdmaiga : garder les deux couches (OLTP transactionnel vs schéma BI)
   séparées, et ce dashboard n'est consulté qu'hebdomadairement — un décalage d'un cycle de
   refresh dbt est acceptable, pas besoin de temps réel.
3. **"Produits vendus" par type** : clarifié par mdmaiga — pas une vraie notion de catégorie
   (`Produit` n'en a pas, décision différée par le PO, `dim_produit.sql` lignes 1-3), simplement la
   liste des produits (par nom) vendus par l'agent avec leur volume, pour voir lesquels
   contribuent le plus à l'atteinte de son objectif. Pas de nouveau champ sur `Produit`.

## Décision actée en cours d'implémentation (mdmaiga, 18/08/2026)

4. **Cohérence du kilo 50 kg/jour avec le kilo net (sprint-10)** : en cadrant ce sprint, constat
   que `vw_performance_agent(_semaine).sql` calculait `kg_vendus`/`kg_par_jour`/
   `statut_objectif_50kg` en **brut** (jamais corrigé au sprint-10, qui n'avait touché que
   `fct_salaires.sql`), alors que la fiche détail affiche ces deux chiffres côte à côte. Décision :
   aligner sur le net, comme l'incentive — un agent qui a déclaré une perte ne doit pas sembler à
   objectif sur un volume qu'il n'a pas réellement écoulé. Contrairement à Django (non
   rétroactif), dbt recalcule tout l'historique à chaque run : les KPI 50kg/jour passés reflètent
   désormais aussi le net.

---

## Constat 1 — Ce qui existe déjà (réutilisable tel quel)

- `bi/models.py` : `VwPerformanceAgent` (grain agent x mois) et `VwPerformanceAgentSemaine` (grain
  agent x semaine) — `kg_vendus`, `kg_par_jour`, `statut_objectif_50kg`, `marge`, `incentive`,
  `rentabilite_agent`. Déjà utilisé par `bi/views.py::dashboard_agents` (lignes 357-488) pour le
  tableau plat — la fiche détail réutilise les **mêmes vues**, filtrées sur un seul `agent_id`,
  sur plusieurs périodes (tendance) plutôt qu'une période unique (tableau).
- `dim_agent.sql` : `agent_id`, `nom_complet`, `type_agent`, `superviseur_id`, `est_actif`,
  `type_contrat`, `date_debut_fonction`, `date_fin_contrat` — pour l'en-tête de la fiche.
- `fct_ventes.sql` : grain 1 ligne = 1 vente, avec `agent_id`, `produit_id`, `quantite_en_kg`,
  `marge_unitaire`, `total_vente` — c'est la matière première du bloc "produits vendus", mais il
  n'existe **aucun mart agrégé** au grain agent x produit aujourd'hui (il faut le créer, § Tâche 2).
- `bi/constants.py` : pattern de seuils centralisés + fonctions `statut_*` (ex.
  `statut_objectif_agent`, `statut_rentabilite_agent`) — à réutiliser à l'identique pour toute
  nouvelle logique de statut introduite par ce sprint, pas de seuil codé en dur dans la vue/le
  template (règle déjà actée, `bi/constants.py` lignes 1-9).

## Constat 2 — Ce qui n'existe pas et doit être créé

- **Stock en main par agent** : `fct_stocks.sql` s'arrête au grain lot/fournisseur, aucune notion
  d'agent. Le concept existe uniquement côté OLTP
  (`DetailDistribution.quantite_restante_calculee`, `core/models.py:1539-1557` — quantité
  distribuée moins ventes moins pertes déclarées sur cette ligne). Il faut répliquer cette formule
  en SQL dbt (§ Tâche 1).
- **Répartition des ventes par produit et par agent** : aucun mart n'agrège `fct_ventes` par
  `(agent_id, produit_id)` sur une période — à créer (§ Tâche 3).
- `stg_pertes.sql` (créé/étendu au sprint-10) n'expose pas `detail_distribution_id`, nécessaire
  pour répliquer `quantite_restante_calculee` par ligne de distribution (elle filtre les pertes par
  `detail_distribution`, pas par lot) — à ajouter (§ Tâche 1).

---

## Tâches

### 1. Nouveau mart `dbt_bi/models/marts/fct_stock_agent.sql` — stock en main, grain agent x lot

Réplique `DetailDistribution.quantite_restante_calculee` (core/models.py:1539-1557) en SQL, agrégée
au niveau utile pour l'affichage (agent x produit, avec le détail par lot disponible en drill si
besoin) :

```
stock_restant_ligne = detail_distribution.quantite
                     - sum(ventes.quantite pour ce detail_distribution)
                     - sum(pertes.quantite_perdue pour ce detail_distribution)
```

- Prérequis : étendre `dbt_bi/models/staging/stg_pertes.sql` pour exposer `detail_distribution_id`
  (colonne `core_perte.detail_distribution_id`, absente du staging actuel — cf. Constat 2).
- Joindre `stg_distribution_agent` (pour `agent_terrain_id`) → `stg_detail_distribution` →
  `stg_lots` (pour `produit_id`) → soustraire ventes (`stg_ventes` groupées par
  `detail_distribution_id`) et pertes (`stg_pertes` groupées par `detail_distribution_id`).
- Grain de sortie proposé : `agent_id, produit_id, lot_id, stock_restant_kg` (garder le lot en
  détail permet un futur affichage "depuis quand ce stock dort chez l'agent", pas construit dans ce
  sprint mais évite une deuxième réécriture du mart plus tard).
- Ne pas retenir les lignes où `stock_restant_kg <= 0` (agent qui a tout vendu/perdu sur cette
  ligne) — pas utile à afficher.

### 2. Nouveau mart `dbt_bi/models/marts/aggregates/vw_ventes_agent_produit.sql` — grain agent x produit x mois

- Depuis `fct_ventes` : `sum(quantite_en_kg)`, `sum(total_vente)`, `sum(marge)`, `count(*)` par
  `(agent_id, produit_id, mois)`.
- Sert le bloc "produits vendus" de la fiche détail : quels produits l'agent a vendu, en quel
  volume, triés par kg vendus décroissant (pour voir immédiatement ce qui contribue le plus à son
  atteinte du 50 kg/jour).

### 3. Django — `bi/models.py`

Deux nouveaux modèles `managed=False` pointant sur les vues dbt ci-dessus (même pattern que
`VwPerformanceAgent`, `bi/models.py:140`) : `FctStockAgent`, `VwVentesAgentProduit`.

### 4. Django — `bi/views.py::dashboard_agent_detail(request, agent_id)`

- Nouvelle URL `bi/urls.py` : `path("agents/<int:agent_id>/", views.dashboard_agent_detail, name="agent_detail")`.
- En-tête : nom, superviseur, type d'agent, statut actif (`dim_agent`).
- Bloc "Atteinte des objectifs" : tendance sur N derniers mois (réutilise `VwPerformanceAgent`
  filtré sur `agent_id`, comme `dashboard_agents` le fait déjà pour tous les agents d'une période —
  ici l'inverse, un agent sur plusieurs périodes) — kg/jour vs seuil 50kg (`statut_objectif_agent`,
  `bi/constants.py`), et statut vis-à-vis du seuil 750kg mensuel (à lire depuis `fct_salaires` ou
  recalculer depuis `VwPerformanceAgent.kg_vendus` du mois, cohérent avec
  `paie/APP_PAIE.md` § 1.quater — seuil désormais sur le kilo **net des pertes**, pas le brut : bien
  vérifier quelle colonne du mart reflète le net avant de l'utiliser ici).
- Bloc "Produits vendus" : tableau `VwVentesAgentProduit` filtré sur `agent_id`, période
  sélectionnable (réutiliser le pattern granularité mois de `dashboard_agents`), trié par kg
  vendus décroissant.
- Bloc "Stock en main" : tableau `FctStockAgent` filtré sur `agent_id` — produit, kg restants,
  éventuellement le lot d'origine.
- Filtres de période cohérents avec le reste de l'app (pas de "Toutes périodes" sur le volet
  agent, cf. `dashboard_agents.html` commentaire ligne 360-362 déjà actée).

### 5. Template `bi/templates/bi/dashboard_agent_detail.html`

- Reprendre les composants visuels déjà utilisés dans `dashboard_agents.html` (badges de statut,
  cartes KPI) plutôt que d'en inventer de nouveaux — cohérence visuelle du sommaire BI.
- Lien vers cette page depuis chaque ligne agent de `dashboard_agents.html` (~ligne 140,
  `{{ a.nom_complet }}`).

### 6. Documentation

- `docs/docs_bi/bi/08_Dashboard_Catalog.md` : nouvelle entrée "Dashboard 3bis : Détail Agent" (ou
  sous-section du Dashboard 3 existant), décrivant les trois blocs et leurs sources.
- `docs/docs_bi/bi/07_Dictionnaire_KPI_Metier.md` : nouveaux KPI si les blocs "produits vendus"/
  "stock en main" introduisent des métriques pas déjà cataloguées (ex. KPI-305 "kg en stock chez
  l'agent").
- `docs/docs_bi/architecte/REFERENCE_TECHNIQUE_BI.md` : ajouter `fct_stock_agent` et
  `vw_ventes_agent_produit` à l'inventaire des marts (même esprit que le reste du fichier — à
  vérifier que les autres entrées n'ont pas déjà dérivé avant d'ajouter, comme observé au
  sprint-08 pour d'autres docs).

---

## Constat 4 — Hors périmètre immédiat, mais même manque ailleurs (notes ouvertes)

Comme le sprint-09, ce constat est une observation, pas une tâche décidée :

- `dashboard_produits` (`bi/views.py:313`) est plat lui aussi — un drill-down "détail produit" côté
  `bi` ferait doublon partiel avec `direction.ProductDetailView`
  (`direction/services/product_analysis_service.py`, déjà approfondie au sprint-10 pour les
  pertes) : à clarifier un jour si `bi` doit avoir sa propre fiche produit ou simplement lier vers
  la page `direction` existante plutôt que dupliquer.
- `dashboard_stock` (`bi/views.py:520`) et `dashboard_depenses` (`bi/views.py:492`) sont plats
  aussi — pas de demande explicite de mdmaiga dessus pour l'instant, à ne pas anticiper avant qu'un
  besoin réel se présente (cohérent avec la posture "ship avant modèle stable" déjà actée).

---

## Definition of Done

- `fct_stock_agent` et `vw_ventes_agent_produit` tournent sans erreur (`dbt run`/`dbt test`), avec
  au moins un test `not_null`/`unique` sur leurs clés (cohérent avec le reste de
  `dbt_bi/models/*/schema.yml`).
- La fiche détail agent est accessible depuis un clic sur une ligne de `dashboard_agents.html`,
  affiche les trois blocs demandés, respecte le pattern de filtre de période existant, et n'a
  aucun seuil codé en dur (tout passe par `bi/constants.py`).
- Le seuil 750 kg affiché sur la fiche est bien le **kilo net des pertes**
  (`paie/APP_PAIE.md` § 1.quater, sprint-10), pas le kilo brut — point de vigilance explicite vu la
  proximité avec le sprint précédent.
- `docs/docs_bi/bi/08_Dashboard_Catalog.md` et `07_Dictionnaire_KPI_Metier.md` mis à jour.

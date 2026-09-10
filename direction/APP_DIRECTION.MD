# 📝 Notes de Conception & Spécifications : Module `app_direction` (DAMS)

## 1. Moteurs d’Analyse Extratemporelle & Décisionnelle

Le module `app_direction` agit comme la couche de gouvernance et d'audit de l'application. Contrairement aux modules opérationnels de saisie terrain, il repose exclusivement sur un **paradigme d'injection de services analytiques** encapsulant la complexité des calculs métiers.

### Le Pattern "Snapshot Service"

L'interface de pilotage principale (`DashboardView`) n'effectue aucune agrégation SQL directe au sein de la vue. Elle délègue cette responsabilité au `DashboardSnapshotService`.

* **Pivot Temporel Modulaire** : Le service accepte une granularité dynamique (`semaine`, `mois`, `annee`, `custom`) permettant à la direction de commuter instantanément d'une vision macro-économique annuelle à un audit micro-opérationnel.
* **Génération de Contexte Cohérent** : Le dictionnaire retourné par le snapshot fusionne les données de performance globales avec des structures analytiques précalculées.

---

## 2. Formulaires de Contrôle & Business Rules

### `CalculSalaireForm`

Formulaire d'interrogation et de simulation des rémunérations sous conditions restrictives de sécurité et de volumétrie.

* **Isolation du Queryset (`__init__`)** : La vue filtre dynamiquement le champ `agent` à l'initialisation pour exclure explicitement les profils de type `direction`. Seuls les agents opérationnels (`terrain` et `entrepot`) ayant le statut `est_actif=True` sont éligibles au calcul, classés par ordre alphabétique.
* **Garde-fous Temporels (`clean()`)** :
* **Inversion chronologique** : Interdiction stricte de soumettre une `date_debut` postérieure à la `date_fin`.
* **Contrôle de charge mémoire** : Limitation de l'écart à **90 jours maximum (3 mois)** pour prémunir le serveur contre des opérations d'agrégation de masse pénalisantes sur les tables de distribution et de vente.



---

## 3. Architecture des Services d’Audit des Agents

Le pilotage des forces de vente et des gestionnaires physiques est segmenté en sous-services spécialisés, garantissant une séparation claire des responsabilités :

### A. Pilotage de la Chaîne Logistique Amont (`SuperviseurAnalysisService`) — révisé 2026-08-03

`get_superviseurs_finance()` ne recalcule plus rien localement : il délègue entièrement à
`finance.services.lister_soldes_superviseurs()` (app `finance`, source de vérité unique du solde
superviseur — décisions n°13/14/15, sprint-03). L'ancien calcul "post-clôture" (`ClotureMensuelle`/
`solde_cloture` comme référence d'ouverture) est abandonné : la référence d'ouverture est désormais
`finance.services.DATE_DEBUT_FINANCE`, pas une clôture.

`get_rots_finance()` — la "situation financière ROT" — est **supprimée**, dépréciée : elle faisait
doublon avec `finance.services` sans jamais avoir été alignée dessus. Le même alignement a été
appliqué aux doublons équivalents ailleurs dans l'app :
- `direction/services/agent_dashboard_service.py::get_superviseurs_finance` (dashboard `agent_dashboard.html`) — délègue à `finance.services`, `get_rot_finance()` supprimée, la fenêtre "trimestre en cours" disparaît (le solde superviseur est un solde courant, pas un flux de fenêtre).
- `direction/services/agent_supervisseur_liste_analyse.py::SuperviseurAnalysisService` (template `superviseur_list.html`) — idem.
- `direction/services/analyse_financiere_service.py::build()` — la clé `agents.rot` est retirée du dict retourné à `analyse_financiere.html`.

`direction/services/agent_analysis_service.py::get_superviseurs_finance` / `get_encadrement_financier_mensuel`
/ `get_superviseur_detail` restent en place mais sont marquées **code mort / déprécié** en commentaire
(aucun appelant) — à trancher plus tard (suppression ou fusion), volontairement non touchées.

Cache `agents_dashboard:v3` (bump de version suite au changement de forme des données).

### B. Audit de Zone de Distribution (`SuperviseurAgentsService`)

Utilisé par la vue de détail pour matérialiser les flux croisés au sein d'un entrepôt spécifique :

* `get_agents_ventes(...)` : Extrait les performances individuelles des agents rattachés au superviseur sur une période donnée.
* `get_flux(...)` : Reconstitue le journal des mouvements financiers opérationnels (cash physique encaissé versus versements effectués au ROT).
* `get_matrice_distribution(...)` : Représente la matrice quantitative des produits alloués, vendus et en reliquat au sein du périmètre de l'entrepôt.

### C. Analyse Opérationnelle du Terrain (`AnalyseOperationnelleService`)

* Offre un moteur de filtrage multidimensionnel croisant la temporalité (par défaut, du 1er janvier à la date du jour), l'identifiant unique de l'agent et la référence produit.
* Permet d'isoler les comportements de vente et de déceler les anomalies de distribution à l'échelle de l'agent individuel.

---

## 4. Performance & Optimisation du Tunnel des Ventes (`ToutesLesVentesView`)

La consultation globale des ventes par la direction est une zone critique de l'application (risque d'anomalie de requêtes en boucle *N+1*). Le système implémente une stratégie d'**optimisation SQL agressive** :

### Annotations SQL Unifiées (Zéro Requête en Boucle)

Le Queryset est enrichi à l'aide d'expressions logiques et de sous-requêtes (`Subquery`), reléguant l'intégralité des calculs lourds au moteur de base de données :

```python
# Modèle conceptuel des annotations SQL intégrées dans la vue
qs.annotate(
    total_vente_sql = F("quantite") * F("prix_vente_unitaire"),
    cout_total      = F("quantite") * F("detail_distribution__lot__prix_achat_unitaire"),
    marge           = F("total_vente_sql") - F("cout_total"),
    date_recouvrement = Subquery(dernier_recouvrement.values("date_recouvrement")[:1]),
    stagiaire_nom_complet = Concat(F("stagiaire__user__first_name"), Value(" "), F("stagiaire__user__last_name"))
)

```

* **`total_vente_sql` & `marge**` : Calculent le chiffre d'affaires et la rentabilité nette par ligne de vente en effectuant une jointure implicite vers le coût d'achat du Lot d'origine.
* **`date_recouvrement`** : Injection par `Subquery` de la date précise de la dernière action de recouvrement associée, évitant le chargement ultérieur d'instances de la table `Recouvrement`.
* **Sécurité d'Accès (`UserPassesTestMixin`)** : Restreint structurellement la visibilité de cette vue aux seuls profils `direction` et `superviseur`.

### KPI CA/Marge et affichage (révisé 2026-08-04)

* **Filtre période par défaut = `mois`** (mois calendaire courant), plus `annee` — les KPI "CA"/"Marge" en haut de page suivent le filtre choisi (comme avant), mais partent du mois en cours tant que direction n'a rien sélectionné, au lieu de l'année entière. `VenteAnalyseService.normalize_period` gère déjà les trois modes (`annee`/`mois`/`perso`), seul le défaut de `periode` a changé dans `get_queryset()`.
* **Quantité affichée en kg** (`Vente.quantite_en_kg`, `core/models.py`) et non plus la quantité brute : un produit conditionné (ex. l'ail, 1 unité = 10 kg) multiplie `quantite` par `Produit.poids_unitaire_kg` ; un produit vrac garde `quantite` telle quelle — évite de confondre "10" unités avec "10 kg".
* **Colonne Prix fusionnée** ("Prix (achat / vente)") : prix d'achat et prix de vente dans la même cellule, différenciés par un dégradé de texte (`bg-gradient-to-r` + `bg-clip-text`) plutôt que deux colonnes séparées — plus compact.
* **Icône de perte** (2026-08-04, révisée sprint-10 le 18/08/2026) : si une perte a été déclarée en même temps qu'une vente (`Vente.commentaire_perte` et/ou `Vente.pertes_liees`, vrac comme conditionné — voir `vente/APP_VENTE.md` § Déclaration de perte), un bouton ⓘ apparaît à côté du nom du produit, ouvrant un `<dialog>` au clic (plus un `title` au survol — ne se déclenchait pas de façon fiable au tactile sur tablette). Le queryset est `prefetch_related('pertes_liees')` pour rester à zéro requête en boucle.
* **Quantité nette affichée si perte déclarée** (sprint-10, 18/08/2026) : la colonne Quantité barre le kg brut vendu (`Vente.quantite_en_kg`) et affiche à la place le kg net facturable à l'incentive (`Vente.kilo_net` = brut − `Vente.kilo_perdu`, `core/models.py`), avec un badge "-X kg perdus". `kilo_perdu`/`kilo_net` somment `pertes_liees` en Python (pas `.aggregate()`) pour rester compatibles avec le `prefetch_related` existant. Cohérent avec `paie/services/salaire_calculator.py::calcul_salaire_mamy`, qui déduit ces mêmes kg de l'incentive versée.

---

### Pertes affichées côté `ProductAnalysisService` (fiche produit, KPI globaux) — corrigé 18/08/2026

`direction/services/product_analysis_service.py` (fiche produit `ProductDetailView`, KPI globaux
`get_product_kpis`, dashboard `get_products_by_period`) calcule ses "pertes" à partir de la table
`Perte`, filtrée sur `date_reception >= DATE_BASCULE_PERTES_DATETIME` (2026-06-01, périodes
antérieures jugées non fiables pour ce KPI — même logique que le "zéro avant mai" de
`fct_salaires.sql`, cf. `paie/APP_PAIE.md` § 1.bis).

**Bug corrigé (18/08/2026)** : ce service sommait uniquement `Perte.quantite_perdue`. Depuis
sprint-10 (`vente/APP_VENTE.md` § Déclaration de perte), une perte déclarée sur un produit
conditionné (sac/carton) laisse `quantite_perdue` à `0` par construction (pour ne pas fausser le
décompte de stock en sacs) et porte le kg réellement perdu dans `Perte.kilo_perdu_incentive` —
une perte de ce type était donc invisible sur la fiche produit et les KPI globaux, alors qu'elle
apparaissait bien dans l'incentive de l'agent. Toutes les agrégations de ce fichier utilisent
désormais `Coalesce(kilo_perdu_incentive, quantite_perdue)` par ligne de `Perte` plutôt que
`quantite_perdue` seule : pour une perte entrepôt classique (`kilo_perdu_incentive` toujours nul),
le comportement est inchangé ; pour une perte vrac déclarée à la vente, les deux champs coïncident
(`kilo_perdu_incentive` mirrore `quantite_perdue`) ; pour une perte conditionnée, c'est
`kilo_perdu_incentive` qui prime.

---

## 5. Module d’Audit des Justificatifs Comptables & Flux Bancaires

### A. Consolidation des Factures Fournisseurs

La direction centralise le contrôle des pièces justificatives via deux méthodes distinctes :

* **Vue d'ensemble (`dashboard_justificatif`)** : Réalise une réconciliation macro entre la valeur d'acquisition initiale des stocks fournisseurs (`valeur_stock_initiale`) et la totalité des flux sortants enregistrés sur le compte `VersementBancaire`.
* **Analyse Analytique (`liste_factures_fournisseurs`)** : Utilise un `select_related` sur les relations `lot`, `fournisseur` et `produit` pour lister les pièces téléversées, agréger les montants globaux par entité commerciale et suivre le nombre d'actes d'achat.

### B. Traçabilité Fine des Flux du ROT (`liste_versements_direction`)

Cette vue surveille de manière exclusive l'activité de versement du Responsable des Opérations (`rot`) vers les comptes de l'entreprise :

* **Découpage des Flux** : Le système applique des filtres stricts pour catégoriser la nature des fonds déposés :
* **Vente** : Provenance directe des recouvrements d'exploitation (`montant_vente > 0` et `montant_hors_vente == 0`).
* **Hors-Vente** : Flux de régularisation ou injections externes (`montant_hors_vente > 0` et `montant_vente == 0`).
* **Mixte** : Opérations combinées.


* **Audit des Pièces Manquantes** : Annotation dynamique du nombre de reçus physiques scannés (`nb_recus=Count('recus')`) pour identifier immédiatement les anomalies de versement non adossées à un justificatif bancaire valide.

---

## 6bis. Réaffectation du portefeuille d'agents entre superviseurs — ajouté 2026-09-08

Vue `reaffectation_agents` (+ `historique_reaffectation`), URLs
`direction/agents/reaffectation/` et `.../historique/`. Entrée de menu dans
`base_admin.html` (section RÉFÉRENTIELS, sous « Agents »), **visible et accessible
uniquement pour `request.user.username == "mdmaiga"`** (`_acces_reaffectation`,
`@user_passes_test`).

**Besoin** : un superviseur quitte l'équipe / un nouveau arrive → déplacer le
portefeuille d'agents d'un superviseur vers un autre sans passer par une commande
management ad hoc. Reprend le mécanisme de fond de `direction/management/commands/
affecter_superviseurs.py` (`Agent.objects.filter(...).update(superviseur=cible)`)
mais piloté depuis l'UI, agent par agent, avec motif et historisation.

**Flux** (`ReaffectationAgentsForm`, `direction/forms.py`) :
1. Choix du superviseur source (form GET auto-submit) → liste de son portefeuille
   (`type_agent in ('terrain', 'agent_gros', 'stagiaire')` = `TYPES_AGENTS_GERES`),
   chaque agent affichant le nombre de distributions encore ouvertes et le stock
   encore en circulation.
2. Cases à cocher des agents + superviseur cible + motif.
3. POST atomique :
   - `TransfertPortefeuilleAgent` (en-tête) + `LigneTransfertAgent` par agent
     (`core/models.py`, migration `0119`) ;
   - `_stock_ouvert_par_agent(agent_ids)` identifie, pour tout l'ensemble d'agents
     et en **3 requêtes fixes**, les `DistributionAgent` portant encore du stock à
     écouler, et en fige un instantané (`stock_bascule` JSON : produit / lot_id /
     quantité restante) ;
   - **ces distributions non soldées sont rebasculées vers le superviseur cible**
     (`DistributionAgent.objects.filter(id__in=...).update(superviseur=cible)`),
     avec une entrée `JournalModificationDistribution` (type `MODIFICATION`,
     anciennes/nouvelles valeurs de superviseur) par distribution touchée ;
   - enfin `Agent.superviseur` est mis à jour pour tous les agents cochés.

**Choix métier assumé** : la bascule des distributions non soldées modifie
l'attribution historique et impacte les calculs de solde / rétention de stock de
l'ancien superviseur (le suivi produit courant suit l'agent). Un bandeau
d'avertissement le rappelle dans l'écran ; l'instantané `stock_bascule` conserve
la trace de ce qui a été déplacé.

**Perf** : ne pas utiliser la property `DetailDistribution.quantite_restante_calculee`
ici (2 requêtes par détail → ~4800 requêtes sur un gros portefeuille). Les quantités
vendues / perdues sont pré-agrégées par détail (une requête `values_list(...).annotate(Sum)`
chacune, sans jointure croisée Vente×Perte qui gonflerait les sommes) puis recombinées
en Python : `_stock_ouvert_par_agent()` tourne en 3 requêtes quel que soit le nombre
d'agents, la page complète en ~10.

**Collision de menu (fix 2026-09-10)** : le lien « Agents » (`base_admin.html`) se
surlignait aussi sur `reaffectation_agents` car son check `'agent' in url_name` matche
n'importe quel nom d'URL contenant « agent ». Ajout de l'exclusion
`'reaffectation' not in request.resolver_match.url_name`.

**Fix historique superviseur des rapports de ventes (2026-09-10)** : `Agent.superviseur`
étant un pointeur vivant écrasé par la réaffectation, les rapports qui filtraient les
`Vente` via `agent__superviseur=...` réattribuaient rétroactivement les ventes passées
d'un agent transféré à son nouveau superviseur (perte d'historique). Remplacé par
`detail_distribution__distribution__superviseur=...`, qui s'appuie sur
`DistributionAgent.superviseur` — déjà figé par distribution et non réécrit sauf pour
le stock non soldé bascule lors d'un transfert (cf. choix métier ci-dessus). Fichiers
touchés : `direction/services/vente_analyses.py` (`filter_ventes`),
`direction/services/agent_analysis_service.py` (`get_superviseur_sales_kpis`),
`direction/services/agent_supervisseur_detail_analyse.py` (`get_flux`, `ventes_agents`).
`get_matrice_distribution` dans ce dernier fichier utilisait déjà le bon chemin —
c'est cette incohérence dans un même fichier qui a signalé le bug.

**Périmètre non couvert** : `SuperviseurAgentsService.get_agents_ventes` (même fichier)
liste le portefeuille **actuel** du superviseur (`Agent.objects.filter(superviseur=...)`)
puis somme les ventes par agent sans re-filtrer par superviseur — lecture différente
(« mon équipe actuelle sur la période », pas « ce qui m'était attribué sur la période »),
volontairement laissée telle quelle. Les usages de `agent__superviseur` dans
`surveillance/services/*` (stock dormant, prix, etc.) n'ont pas été audités dans ce
correctif — même risque potentiel, à vérifier si un rapport de surveillance doit rester
exact après une réaffectation.

---

## 6. Pipelines d'Exportation Métier

Pour répondre aux besoins d'audits externes et de réunions comptables, le système délègue l'extraction de données filtrées au service `VenteExportService`.

* **Héritage strict des filtres** : Les fonctions `ExportVentesExcelView` et `ExportVentesPDFView` réutilisent exactement le même moteur de filtrage normalisé (`VenteAnalyseService.filter_ventes`) que la vue web. Cela garantit une correspondance absolue au centime près entre les données affichées à l'écran et les documents téléchargés (`.xlsx` ou `.pdf`).
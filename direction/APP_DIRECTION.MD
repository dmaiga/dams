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

### C bis. Export des ventes par fournisseur (`SuperviseurAgentsService.ventes_par_fournisseur`) — ajouté 24/09/2026

Sur la fiche détail superviseur (`/direction/agents/superviseurs/<pk>`, `SuperviseurDetail`), deux
boutons (Excel/PDF) exportent les ventes réalisées par **le superviseur et l'ensemble de ses
agents** (`agent__superviseur=superviseur` OU `agent=superviseur`), sur la période déjà
sélectionnée à l'écran (`SuperviseurAgentsService.resolve_period`).

Organisation en deux niveaux, pour retracer un produit de sa réception jusqu'à sa vente :
**fournisseur** (`LotEntrepot.fournisseur`, nullable — "Sans fournisseur" en repli) → **lot**
(produit, prix d'achat, date de réception) → **ventes** (vendeur — agent ou superviseur lui-même
— date, quantité, prix). Groupé par lot individuel, pas par nom de produit agrégé : deux
réceptions du même produit à des prix/dates différents restent deux blocs distincts.

Contrairement à `get_agents_ventes` (écran de pilotage courant, agents actifs non-stagiaires
uniquement), cet export **n'exclut personne** sur le statut ou le type d'agent — c'est une trace
historique, un agent parti depuis doit rester visible dans ce qu'il a vendu.

Implémenté dans `direction/services/superviseur_ventes_fournisseur_export.py::
SuperviseurVentesFournisseurExportService` (même pattern que `StockInvestigationExportService`) :
`export_excel` — table plate, une ligne par vente, toutes les colonnes répétées (facilite le tri/
filtre dans Excel) ; `export_pdf` — hiérarchie fournisseur → produit → tableau de ventes, fidèle à
la structure demandée. Exposé par `ExportSuperviseurVentesFournisseurExcelView`/`PDFView`
(`LoginRequiredMixin` uniquement, même niveau d'accès que `SuperviseurDetail`).

### C. Analyse Opérationnelle du Terrain (`AnalyseOperationnelleService`)

* Offre un moteur de filtrage multidimensionnel croisant la temporalité (par défaut, du 1er janvier à la date du jour), l'identifiant unique de l'agent et la référence produit.
* Permet d'isoler les comportements de vente et de déceler les anomalies de distribution à l'échelle de l'agent individuel.

### D. Fiche détail agent (`AgentDetailView`, `/direction/agents/<pk>/`) et son export (24/09/2026)

`AgentDetailService.get_agent_detail` calcule les KPI agrégés (kg vendus, CA, marge, incentive, ventes
groupées par produit) sur la période résolue par `AgentDetailService.resolve_period` (`?periode=
hebdo|mensuel|custom`, hebdo par défaut). Cette page n'affichait jusqu'ici que des agrégats — aucun
export, aucune ligne de détail.

**Ajout (demande mdmaiga, 24/09/2026)** : deux boutons (Excel/PDF) permettent d'extraire, sur la même
période que celle sélectionnée à l'écran, le détail ligne à ligne de :
- **Distributions reçues** par l'agent (`DetailDistribution` dont `distribution.agent_terrain` = cet
  agent, filtrées sur `distribution.date_distribution`) — date, produit, quantité, superviseur
  distributeur, type de distribution.
- **Ventes réalisées** par l'agent (`Vente`, non supprimées, filtrées sur `date_vente`) — date, produit,
  quantité, prix unitaire, montant, type de vente, mode de paiement. Contrairement à `ventes_par_produit`
  (agrégat affiché à l'écran), l'export liste chaque vente individuellement, pas un total par produit.

Implémenté dans `direction/services/agent_detail_export.py::AgentDetailExportService` (même pattern que
`StockInvestigationExportService` : `export_excel` — un classeur à 2 feuilles — et `export_pdf` — un
document à 2 tableaux), exposé par `ExportAgentDetailExcelView`/`ExportAgentDetailPDFView`
(`direction/views.py`, `LoginRequiredMixin` uniquement, même niveau d'accès que `AgentDetailView` —
aucun contrôle de rôle supplémentaire introduit). Les deux vues relisent `AgentDetailService.
resolve_period(request)` à partir des mêmes paramètres GET que la page, pour ne jamais dupliquer la
logique de résolution de période.

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
`base_admin.html`, section **ADMIN** dédiée (déplacée depuis RÉFÉRENTIELS le
2026-09-15, sprint-13), **visible et accessible uniquement pour
`request.user.username == "mdmaiga"`** (`_acces_admin_mdmaiga`, `@user_passes_test`
— garde partagée avec les corrections administratives, voir § Corrections
administratives ci-dessous et `docs/sprints/sprint-13.md`).

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

---

## 6ter. Corrections administratives auditées — sprint-13, 2026-09-15

**Besoin** : mdmaiga corrigeait jusqu'ici, via le Django admin, des erreurs de saisie
remontées par le terrain (quantité/prix erroné à la réception d'un lot, agent ou
superviseur mal identifié en distribution, confusion prix au sac / prix au kilo à la
vente) — sans aucune trace (qui, quand, avant/après, motif). Ce sprint déplace ces
corrections dans l'application, avec effet domino correct et audit obligatoire.

**8 écrans, tous réservés à `mdmaiga`** (`_acces_admin_mdmaiga`, section ADMIN du
menu — 4 entrées directes : Corriger un lot / une distribution / une vente,
Historique) :

| Vue | URL | Rôle |
|---|---|---|
| `liste_corrections_lots` | `direction/corrections/lots/` | Liste des lots, filtrable par **produit** et **période de réception** (`debut`/`fin`), paginée 30/page — point d'entrée de la correction de lot. |
| `liste_corrections_distributions` | `direction/corrections/distributions/` | Liste des distributions, filtrable par **agent**, **superviseur**, **produit** et **période de distribution** — point d'entrée de la correction de distribution. |
| `liste_corrections_ventes` | `direction/corrections/ventes/` | Liste des ventes, filtrable par **agent**, **produit** et **période de vente** — point d'entrée de la correction de vente. |
| `corriger_lot` | `direction/corrections/lot/<lot_id>/` | Appelle `marchandise.services.CorrectionLotService.corriger_lot` |
| `corriger_distribution` | `direction/corrections/distribution/<detail_distribution_id>/` | Appelle `marchandise.services.CorrectionDistributionService.corriger_distribution` |
| `supprimer_distribution_admin` | `direction/corrections/distribution/<detail_distribution_id>/supprimer/` | Appelle `marchandise.services.CorrectionDistributionService.supprimer_distribution` — bouton « Zone dangereuse » sur `corriger_distribution.html`, POST uniquement |
| `corriger_vente` | `direction/corrections/vente/<vente_id>/` | Appelle `vente.services.CorrectionVenteService.corriger_vente` |
| `historique_corrections` | `direction/corrections/historique/` | Lecture de `CorrectionAdministrative` (filtrable par type, paginée 30/page) |

**Suppression de distribution (doublon)** — ajoutée 2026-09-16 : mdmaiga a signalé que la
correction de distribution ne couvrait pas le cas du **doublon pur** (la même affectation soumise
deux fois par le gestionnaire de stock) — corriger des champs ne suffit pas, il faut effacer
l'événement en trop. `supprimer_distribution_admin` supprime le `DetailDistribution` (et le
`DistributionAgent` s'il ne porte plus d'autre détail) et restitue la quantité au
`LotEntrepot.quantite_restante`, avec la même garde que le changement de produit/agent (refusé si
des ventes ou pertes existent déjà dessus). Voir `marchandise/APP_MARCHANDISE.md` pour le détail
du service. **Distinct de `core.views.supprimer_distribution`** (route `/distribution/<id>/
supprimer/`, réservée aux superviseurs, appelle `DistributionAgent.soft_delete()`/filtre
`est_supprime` — **champ et méthode inexistants sur ce modèle**, constaté lors de ce sprint : code
legacy cassé, non touché car hors périmètre).

**Révision du 2026-09-15 (même jour)** : une première version regroupait les 3
recherches sur un seul écran « hub » (`corrections_hub`) — remplacée à la demande de
mdmaiga par 3 entrées de menu séparées, chacune ouvrant directement une **liste**
filtrable par **agent et période** (pas une recherche texte libre), avec le produit en
filtre secondaire. `corrections_hub`/`hub.html` ont été supprimés, pas seulement
masqués.

**Correction de date ajoutée** (même révision) : la date manquait aux formulaires de
distribution et de vente alors que ce sont des erreurs réelles remontées par mdmaiga.
`CorrectionDistributionForm`/`CorrectionVenteForm` portent désormais `date_distribution`/
`date_vente` (seul le jour est corrigé, l'heure d'origine est conservée — même
principe que `VenteForm.save()` à la création). Deux nouveaux types d'audit :
`DISTRIBUTION_DATE`, `VENTE_DATE` (migration `0123`).

**Formulaires** (`direction/forms.py`) : `CorrectionLotForm`, `CorrectionDistributionForm`,
`CorrectionVenteForm` — le `motif` est **facultatif** (décision mdmaiga, 2026-09-15 :
« un point commun à tous, rendre le commentaire facultatif ») ; `clean()` exige
seulement qu'au moins un champ métier soit renseigné. Les vues traduisent une
`ValidationError` levée par le service en erreur de formulaire
(`form.add_error(None, ...)`) plutôt que de laisser remonter une 500.

**`CorrectionLotForm` porte aussi `fournisseur`** (ajouté 2026-09-15) — la correction
du lot ne se limite plus à quantité/prix/date.

**`CorrectionDistributionForm` révisé (2026-09-15)** — `superviseur` et `agent_terrain`
sont désormais **toujours pré-sélectionnés** à la valeur courante (jamais de champ vide
en attente de choix) ; `agent_terrain` se recharge par AJAX
(`/marchandise/ajax/agents-par-superviseur/`) dès que `superviseur` change côté client,
pour ne jamais laisser un agent incohérent avec le superviseur affiché. Le formulaire
porte aussi **`produit`/`lot`** (cascade AJAX `/agents/ajax/lots-par-produit/`,
identique) : la correction ne porte plus seulement sur l'agent ou la quantité, mais
aussi sur le **produit distribué** — cas réel : gestionnaire de stock qui envoie le
mauvais produit au mauvais agent en même temps.

**Points d'entrée secondaires depuis l'existant** (liens « Corriger », visibles
uniquement pour `mdmaiga`, en plus des 3 listes dédiées) : fiche lot
(`marchandise/detail_lot.html`), tableau « Suivi des distributions »
(`direction/analyses/stock/suivi_distributions.html`, un lien par ligne), liste des
ventes (`direction/analyses/ventes/liste_ventes_admin.html`, un lien par ligne).

**Journal générique** : `CorrectionAdministrative` (`core/models.py`, voir
`core/APP_CORE.md` § 11) — une ligne par champ effectivement modifié, jamais une
ligne "vide" si rien n'a changé. Voir `marchandise/APP_MARCHANDISE.md` et
`vente/APP_VENTE.md` pour le détail des cascades par service.

**Limite assumée** (`CorrectionDistributionService`) : le lien vers l'affectation
source n'existe pas comme FK explicite — une correction de produit/quantité de
distribution n'est cascadée vers le stock (`AffectationLotSuperviseur`/`LotEntrepot`)
que si cette source peut être identifiée sans ambiguïté ; sinon la correction est
refusée (pas de correction silencieuse et potentiellement fausse du stock central).
**Garde-fou** : changer le produit ou l'agent est refusé si la distribution porte déjà
des ventes ou des pertes enregistrées — seules la quantité et la date restent
corrigeables dans ce cas (voir `marchandise/APP_MARCHANDISE.md` pour le détail).

**Tests** : `marchandise/tests.py` (`CorrectionLotServiceTests`,
`CorrectionDistributionServiceTests` — dont le scénario composé agent+produit et la
suppression de doublon avec restitution de stock), `vente/tests.py`
(`CorrectionVenteServiceTests`), `direction/tests.py`
(`CorrectionsAdministrativesAccessTests` — accès, audit, motif facultatif, bout en
bout formulaire→service, y compris la suppression de distribution).

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

**Superviseur affiché sous l'agent** (sprint-14, 17/09/2026) — `direction/ventes`
(`ToutesLesVentesView`) est très consultée par la direction, qui ne pouvait pas identifier en un
coup d'œil le superviseur responsable d'un agent listé. `VenteAnalyseService.filter_ventes`
ajoute `agent__superviseur`/`agent__superviseur__user` au `select_related` (aucune requête
supplémentaire) et le template affiche `vente.agent.superviseur.full_name` en `<span>` sous le
nom de l'agent.

---

## 7. Suivi des distributions — traçabilité et investigation (sprint-14, 17/09/2026)

**Besoin** : `direction/suivi-distributions/` doit servir d'outil d'investigation, pas seulement
de traçabilité passive — mdmaiga observe qu'un produit sorti du dépôt sans vente enregistrée
derrière lui plus d'une semaine est à surveiller, plus de deux semaines est suspect (perte/vol
potentiel).

**Bug corrigé — « None FCFA »** : la colonne Valorisation affichait `DetailDistribution.prix_detail`,
qui est **structurellement toujours `None`** avant la vente (`rules/ARCHITECTURE.md` § invariants
— aucun prix n'est fixé avant `Vente.prix_vente_unitaire`). Le prix de vente a été retiré de cette
colonne ; elle affiche désormais la **valeur immobilisée réelle**
(`quantite_restante × lot.prix_achat_unitaire`, connue dès la distribution).

**Bug corrigé — indicateur de couleur sans valeur actionnable** : le texte "Sorti il y a…" était
ambre dès qu'un produit était en circulation (condition `restant > 0` testée deux fois, la seconde
toujours vraie). Remplacé par un statut réel basé sur l'ancienneté (`direction/constants.py`) :

| Statut | Seuil | Rendu |
|---|---|---|
| `ok` | < 7 j | Neutre, badge "SUR LE TERRAIN" |
| `attention` | 7-13 j | Ambre, badge "À SURVEILLER — N J" |
| `critique` | ≥ 14 j (`SEUIL_CRITIQUE_JOURS`) | Rouge, badge "À INVESTIGUER — N J" |

**Filtre par défaut** : `statut = request.GET.get("statut", "restant")` — un accès direct sans
paramètre affiche désormais uniquement les produits en circulation (avant : tout mélangé). Le
select porte 3 options explicites (`restant`/`ecoule`/`tous`), plus de placeholder ambigu.

**Nouveau tableau « Produits à investiguer »** : tous les produits en circulation depuis plus de
`SEUIL_ATTENTION_JOURS` (7 j) — pas seulement les cas critiques, décision mdmaiga : la liste doit
capter le problème tôt. Indépendant du filtre `statut` de la table 1 (toujours restreint à
`restant=True` + ancienneté).

**Révision UX (même jour, 17/09/2026)** : la première version listait une ligne par
`DetailDistribution` (produit, fournisseur, agent, superviseur, valorisation en FCFA). Retour de
mdmaiga : ce n'est **pas un document comptable**, mais une checklist remise à un agent de
vérification qui passe chez chaque agent lister confirmer la présence physique des produits —
fournisseur et valorisation n'y ont pas leur place, et une ligne par produit noie l'information
utile ("qui a quoi"). Reconstruit en vue **agrégée superviseur → agent → produits** :

- Une carte par superviseur (`agents_a_investiguer` = `StockInvestigationService.
  regrouper_par_superviseur()`), listant ses agents concernés.
- Par agent : nom + liste compacte des produits en sa possession (`quantité produit — depuis le
  date (N j)`) — pas de sous-table, pas de colonne fournisseur/valorisation.
- **Couleur affinée (même jour, second retour mdmaiga)** : la première version encadrait chaque
  ligne d'un badge plein rouge/ambre — inutile ici puisque *toute* la section est déjà la zone à
  risque (uniquement des produits > `SEUIL_ATTENTION_JOURS` j) : peindre chaque ligne en rouge noie
  le signal au lieu de le porter. Remplacé par un simple point de couleur (rouge si `critique`,
  ambre si `attention`) en début de ligne, texte neutre sinon ; seul le compteur de jours des cas
  `critique` (≥ `SEUIL_CRITIQUE_JOURS`) reste accentué en rouge — la seule distinction qui reste
  actionnable une fois qu'on sait déjà être dans la liste à investiguer.
- **Superviseurs inactifs exclus (même jour, troisième retour mdmaiga)** :
  `StockInvestigationService.a_investiguer()` filtre désormais
  `distribution__superviseur__est_actif=True` — un superviseur parti/désactivé n'est plus un
  destinataire valable de la checklist terrain. Cohérent avec le select "Superviseur" du
  formulaire de filtre, déjà restreint à `Agent.objects.filter(type_agent='entrepot',
  est_actif=True)` avant ce correctif (aucun changement nécessaire côté filtre, seul le
  regroupement du tableau 2 en manquait). Table 1 (traçabilité brute) non touchée — hors
  demande, comportement historique conservé.
- Boutons d'export **remontés en tête de page** (à côté du titre), pas dans la section elle-même —
  c'est l'action la plus utile pour la direction, elle ne doit pas nécessiter de scroller.
- Export Excel/PDF (`ExportProduitsInvestigationExcelView`/`PDFView`,
  `direction/services/stock_investigation_export.py`) reflète la même structure groupée : une
  ligne par agent (colonnes Superviseur / Agent / Produits en circulation), le détail produit tenant
  dans une seule cellule à retour à la ligne (`Alignment(wrap_text=True)` Excel,
  cellule `Paragraph` PDF). Même moteur de filtrage que l'écran
  (`StockInvestigationService.filtrer`), sans plafond de lignes côté export (contrairement à
  l'affichage écran, plafonné à `NB_MAX_PRODUITS_A_INVESTIGUER = 100` lignes avant regroupement).
- Le seuil (`SEUIL_ATTENTION_JOURS`) n'est jamais recopié en dur dans les libellés : le texte de
  la page et l'en-tête de colonne de l'export le lisent depuis `direction/constants.py`, pour que
  l'écran et l'export restent alignés si le seuil change un jour.

**Service** : `direction/services/stock_investigation_service.py::StockInvestigationService` —
`base_queryset()` porte les annotations partagées (`total_vendu`, `restant`, `valeur_immobilisee`
— toujours calculée, réservée à la table 1), `filtrer()` applique les filtres communs
(superviseur/agent/produit/période), `a_investiguer()` restreint aux lignes > `SEUIL_ATTENTION_JOURS`
jours, `annoter_statut()` calcule `jours_ecoules`/`statut_circulation` en Python (volume par page
toujours faible), `regrouper_par_superviseur()` construit la structure imbriquée superviseur →
agent → produits consommée par la table 2 et par l'export.

**Formatage des quantités (même jour, quatrième retour mdmaiga)** : la colonne « Quantités (Dist. /
Vendu / Reste) » de la table 1 et les quantités de la table 2 affichaient les `Decimal` bruts
(`20.00`, `1.00`...). Passées au filtre `direction_filters::format_number` (déjà la convention
établie ailleurs dans l'app — `agent_dashboard.html`, `analyse_operationnelle.html`,
`dashboard.html`, `fournisseurs/detail.html` — séparateur de milliers, virgule française, zéros
inutiles supprimés). mdmaiga avait suggéré `format_quantity` (même fichier) : non retenu, ce
filtre produit un format anglo-saxon à point (`20.00`) et n'est utilisé nulle part ailleurs dans
l'app — `format_number` reste la référence pour rester cohérent avec le reste de `direction`.

**Hors périmètre (décision mdmaiga, 17/09/2026)** : un axe BI dédié « produits en circulation »
a été envisagé puis écarté — cette page couvre déjà le besoin de valorisation, le dupliquer dans
le BI serait une surcharge sans valeur ajoutée à ce stade. Voir `docs/sprints/archive/sprint-14.md`
pour le détail de l'investigation BI (`fct_stock_agent.sql`).

**Tests** : `direction/tests.py` — `SuiviDistributionsProduitsEnCirculationTests` (filtre par
défaut, statut "tous", absence de "None FCFA", seuils de couleur, regroupement superviseur →
agent → produits du tableau d'investigation, exports), `VentesSuperviseurAffichageTests`.

---

## 8. Corrélation réception → distribution → vente sur un produit soldé (23/09/2026)

**Besoin** : mdmaiga signale qu'une fois un produit soldé (`restant <= 0`), la table 1 ne montrait
plus que la date de distribution — plus aucun moyen de corréler avec la date de réception au dépôt,
la date de vente déclarée par le superviseur (`Vente.date_vente`, rétroactive possible) et sa date
d'enregistrement technique (`Vente.date_creation`). Les données n'étaient jamais perdues (FK
permanente `Vente.detail_distribution`, `core/models.py:1845`) — seule la vue ne les affichait pas.

**`StockInvestigationService.base_queryset()`** annote désormais chaque `DetailDistribution` avec
`date_premiere_vente`/`date_derniere_vente` (`Min`/`Max` sur `Vente.date_vente`, ventes non
supprimées) et `date_enregistrement_derniere_vente` (`Max` sur `Vente.date_creation`), et
précharge `ventes_actives` (`Prefetch` sur `vente_set`, triées par `date_vente`) pour le détail
ligne par ligne.

**`annoter_statut()`** calcule en plus `etalement_vente_jours` (écart en jours entre première et
dernière vente) — un produit peut être écoulé en plusieurs ventes partielles sur plusieurs jours
plutôt qu'en une seule fois ; sans cet écart, "vendu le X" n'aurait montré que la dernière date et
masqué un étalement anormalement lent.

**Template** (colonne « Statut Distribution ») :
- Ligne soldée : affiche "Distribué le" puis, selon `etalement_vente_jours`, soit "Vendu le [date]"
  (vente unique) soit "Écoulé en N j (du ... au ...)" (ventes étalées) ; "Aucune vente liée" en
  rouge si soldé sans `Vente` rattachée (incohérence à investiguer).
- Ligne encore en circulation : signale une "Vente partielle le [date]" / "Vente en cours depuis
  N j" si des ventes existent déjà avant l'épuisement complet.
- **Détail complet en modale**, pas en `<details>` en ligne (retour mdmaiga : préférer une modale
  pour ne pas déformer la hauteur des lignes du tableau quand plusieurs ventes sont listées) — même
  pattern `<dialog class="modal">` + `showModal()` que la modale "Perte déclarée" de
  `direction/templates/direction/analyses/ventes/liste_ventes_admin.html`. Liste chaque `Vente`
  (quantité, date déclarée, date d'enregistrement) rattachée au `DetailDistribution`.
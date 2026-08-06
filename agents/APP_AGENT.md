# 📝 Notes de Conception & Spécifications : Module `app_agents` (DAMS)

---

## 1. Cartographie des Rôles & Périmètres de Sécurité (Dashboards)

Le module `app_agents` structure l'activité et le cloisonnement des données des différents profils opérationnels et décisionnels sur le terrain à l'aide d'architectures de services dédiées :

### A. Le Superviseur (`tableau_de_bord_superviseur`)

* **Périmètre Restreint** : Limite structurellement l'accès aux seules informations du stock physique attribué à l'entrepôt et aux agents directement rattachés à sa hiérarchie.
* **Sécurisation** : Si le profil utilisateur ne valide pas les prérequis de supervision, l'accès est révoqué avec redirection vers la page de connexion.
* **Finances (révisé 2026-08-03)** : `SuperviseurDashboardService.get_finances_superviseur` ne recalcule plus `cash_detenu`/`montant_remis_rot` localement — délègue à `finance.services.solde_superviseur` (app `finance`, source de vérité unique, voir `finance/APP_FINANCE.md`). `montant_a_recouvrer` (argent encore chez les agents, fenêtre mois courant) reste calculé ici, l'app `finance` ne couvrant pas ce concept.
* **"Engagements champ" retiré du dashboard (sprint-06, Constat 3, 06/08/2026)** : la section détaillant les avances/dépenses pour le compte du champ (dams_agro) est retirée du dashboard résumé — trop dense, source de confusion pour les superviseurs non concernés. Reprise sur une page dédiée, `finance:mes_engagements_champ`, seule porte d'entrée désormais (voir `finance/APP_FINANCE.md`). `SuperviseurDashboardService.get_engagements_champ` a été supprimée (dead code) — la logique équivalente vit dans `finance.services.lister_engagements_champ`.
* **Synchronisation engagements champ au chargement du dashboard (06/08/2026)** : `build_dashboard_perimetre` appelle `finance.services.synchroniser_engagements_champ(superviseur)` avant de construire `finances_superviseur` — sans ça, un remboursement fait côté dams_agro et pas encore appris par `dams` fausserait le KPI "Cash détenu" (`solde_superviseur`, terme `remboursements_champ`), visible directement sur ce dashboard. Best-effort, court-circuitée sans appel réseau s'il n'y a aucun engagement ouvert à vérifier pour ce superviseur — voir `finance/APP_FINANCE.md` pour le détail (ce même mécanisme est aussi déclenché sur `finance:mes_engagements_champ`).
* **"Produits en circulation" retiré du dashboard (06/08/2026, revient sur la décision "garder + cache" du Constat 2 prise plus tôt le même jour)** : le tableau et son calcul (`SuperviseurDashboardService.get_produits_en_circulation`/`_calculer_produits_en_circulation`, cache inclus) sont **supprimés** — mdmaiga a préféré remplacer ce bloc par des raccourcis vers les actions/écrans réellement utilisés au quotidien plutôt que garder un tableau mis en cache. Remplacé par un bloc "Accès rapide" (`agents/templates/agents/dashboards/superviseur.html`) : boutons vers `vente:enregistrer_vente`, `vente:historique_ventes`, `liste_agents_sup` pour tous les superviseurs ; `liste_lots`, `liste_depenses` et `finance:mes_engagements_champ` en plus, réservés à `abdoulaye.kone` (même condition username que les liens nav "Stock Entrepôt"/"Dépenses"/"Engagements champ" de `core/templates/base.html` — ces trois liens nav sont également réservés à `abdoulaye.kone` depuis le 06/08/2026, alors que "Stock Entrepôt" était auparavant ouvert à tous les superviseurs, voir `finance/APP_FINANCE.md`).

### B. Le Responsable des Opérations et de la Trésorerie - ROT (`tableau_de_bord_rot`)

* **Vision Macro-Opérationnelle** : Offre un axe de pilotage tridimensionnel croisant les volumes de stocks globaux, la performance des superviseurs et les flux de trésorerie consolidés.

### C. L'Agent de Terrain (`dashboard_agent`)

* Interroge l'instance du service `AgentDashboardService` pour retourner le contexte d'activité individuel (ventes, reliquats de stock et encours).

---

## 2. Gestion et Suivi des Stocks Superviseurs (`superviseur_lots_affectes`)

Cette vue permet à un superviseur d'auditer l'état des stocks qui lui ont été mis à disposition, en intégrant des filtres temporels et un système d'analyse d'utilisation.

### Moteur de Filtrage Temporel

Le système propose un double mécanisme de filtrage :

* **Filtres Rapides (Raccourcis)** : `today` (date du jour), `7j` (7 derniers jours) et `30j` (30 derniers jours).
* **Filtres Personnalisés** : Analyse par plage de dates via les paramètres nettoyés `date_debut` et `date_fin`.

### Optimisation SQL & Transformation des Données

Afin de prévenir toute régression de performance sur de grands volumes d'affectations, le Queryset embarque une jointure anticipée :

```python
lots_qs = lots_qs.select_related('lot__produit', 'attribue_par__user').order_by('-date_affectation')

```

La transformation des données calcule dynamiquement pour chaque ligne :

* Le **taux restant** : $(\text{quantite\_restante} / \text{quantite\_initiale}) \times 100$
* Le **taux utilisé** : $100 - \text{taux\_restant}$
* Le **statut visuel de progression** (`success` si $> 50\%$, `warning` si $> 20\%$, `danger` si inférieur).

---

## 3. Workflows de Distribution du Stock aux Agents

La distribution de marchandises depuis le stock du superviseur vers les agents terrain s'effectue selon trois canaux distincts aux niveaux de contrôle variables :

```
[Mise à Disposition ROT] ➔ [Stock Affecté Superviseur]
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
[Distribution Standard]  [Distribution Simplifiée]  [Distribution Override]
  (Calcul à la volée)      (Contrôles Backend &       (Compte Dédié & Prix
                            Transactions Atomiques)     Forcé en Mode Chef)

```

### A. Distribution Standard (`distribuer_lot_agent`) - *En cours de dépréciation*

* Évalue en temps réel l'état des stocks disponibles via le service `SuperviseurStockService` avant de valider le formulaire de distribution.

### B. Distribution Simplifiée avec Sécurisation Strict (`distribution_superviseur`)

Ce workflow applique une triple barrière de sécurité logicielle encapsulée dans une **transaction atomique** (`transaction.atomic()`) :

1. **Sécurité Agent** : Vérifie que l'agent bénéficiaire est sous la responsabilité directe du superviseur connecté, qu'il s'agit d'un auto-transfert, ou qu'il possède le statut d'`agent_polivalent`.
2. **Sécurité Affectation** : Valide que le lot d'origine appartient bien au périmètre physique du superviseur.
3. **Double-Check Backend de Stock** : Bloque l'exécution si la quantité demandée excède la valeur de `quantite_restante`, parant ainsi aux anomalies de double soumission de formulaire.

### C. Distribution Dérogatoire (`distribution_superviseur_override`)

* **Accès Restreint par Identifiant** : Ce canal est réservé de manière exclusive à l'utilisateur `"jeanclaude.sup"`.
* **Forçage des Conditions Commerciales** : Permet de passer outre les grilles tarifaires standards en effectuant un **override forcé** du prix de gros (`prix_gros`) lors de l'écriture de l'instance de `DetailDistribution`.

---

## 4. Audit & Fiches Individuelles des Forces de Vente (`detail_agent_sup`)

La vue de détail d'un agent fournit au superviseur un bilan de performance opérationnel et financier complet.

### Métriques et Calculs de Taux

Le système extrait les totaux de l'agent et isole la répartition du chiffre d'affaires par type de vente (`gros` vs `detail`) via une agrégation SQL protégée contre les valeurs nulles par la fonction `Coalesce` :

```python
ventes_par_type = Vente.objects.filter(agent=agent).values("type_vente").annotate(
    total=Coalesce(Sum(F("quantite") * F("prix_vente_unitaire"), output_field=DecimalField(...)), Decimal("0.00"))
)

```

Les indicateurs de performance clés (KPI) calculés sont :

* **Taux de recouvrement** : $(\text{total\_recouvre} / \text{total\_ventes}) \times 100$
* **Pourcentage des ventes de Gros** : $(\text{ventes\_gros} / \text{total\_ventes}) \times 100$
* **Pourcentage des ventes de Détail** : $(\text{ventes\_detail} / \text{total\_ventes}) \times 100$

### Volume vendu en kg (mois courant)

La préoccupation première du superviseur reste opérationnelle avant d'être financière : *cet agent vend-il beaucoup ?* La vue ajoute donc un volume en kg, borné au mois courant (`get_periode_courante()` de `agents.services.superviseur_service` — même convention que le dashboard superviseur), avec le détail par produit :

```python
ventes_mois = Vente.objects.filter(
    agent=agent, date_vente__gte=debut_mois, date_vente__lte=maintenant, est_supprime=False
).select_related("detail_distribution__lot__produit")

for vente in ventes_mois:
    kg = vente.quantite_en_kg   # gère conditionné vs vrac, voir ci-dessous
    ...
```

Le calcul kg **réutilise** la propriété `Vente.quantite_en_kg` (`core/models.py`) plutôt que de redupliquer la règle : un produit **conditionné** (`Produit.poids_unitaire_kg` renseigné — ex. un carton/sac de 10 kg) voit sa quantité vendue multipliée par ce poids unitaire ; un produit **non conditionné** (vendu directement au kg, `poids_unitaire_kg` vide) garde `quantite` telle quelle. Le regroupement par produit est fait en Python (volumes mensuels par agent, faible volumétrie) pour ne pas dupliquer cette règle métier dans une expression ORM.

Contexte exposé au template : `volume_mois_kg` (total) et `volume_par_produit_kg` (liste de tuples `(nom_produit, kg)` triée décroissant).

---

## 5. Hub Logistique : Gestion de Stock & Mise à Disposition

### Dashboard Gestionnaire de Stock (`dashboard_gestionnaire_stock`)

* Centralise l'état physique de l'entrepôt principal en filtrant uniquement les lots actifs (`quantite_restante__gt=0`).
* Calcule deux indicateurs distincts : le stock global restant en entrepôt (`total_stock`) et les volumes spécifiquement réservés pour le traitement ou l'arbitrage du ROT (`total_dispo_rot`).

### Pipeline de Mise à Disposition (`mise_disposition_rot`)

* Permet au gestionnaire de stock d'enregistrer le transfert de responsabilité d'un lot vers le ROT. L'opération consigne un historique immuable dans la table `MiseDispositionRot` à des fins de traçabilité et d'audit ultérieur.

---

## 6. Tunnel d'Enregistrement Rapide Ventes & Recouvrements

Pour fluidifier l'activité quotidienne, deux mécanismes permettent de liquider le reliquat d'une distribution :

### A. Formulaire Guidé Dynamique (`detail_distribution_sup`)

* **Formulaire Contextuel** : La fonction `get_form_class` détermine dynamiquement le formulaire approprié (`VenteTerrainForm`, `VenteAgentGrosForm` ou `VenteFlexForm`) selon la typologie de l'agent concerné.
* **Intégrité Financière** : L'écriture en base est sécurisée sous bloc `transaction.atomic()`. La validation génère simultanément la ligne de `Vente` et son écriture de `Recouvrement` immédiat au comptant, associant le superviseur connecté en tant qu'encaisseur physique des fonds.

### B. Liquidation Instantanée (`vente_distribution_rapide`)

* **Vente Totale Automatique** : Conçu pour solder d'un seul clic l'intégralité du stock restant (`reste = quantite - quantite_vendue`) aux conditions tarifaires par défaut de l'agent (Prix de gros pour un `agent_gros`, prix de détail pour les autres profils). Elle exécute de manière automatique la création couplée Vente + Recouvrement et met à jour le compteur de distribution.
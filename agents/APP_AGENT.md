# 📝 Notes de Conception & Spécifications : Module `app_agents` (DAMS)

---

## 1. Cartographie des Rôles & Périmètres de Sécurité (Dashboards)

Le module `app_agents` structure l'activité et le cloisonnement des données des différents profils opérationnels et décisionnels sur le terrain à l'aide d'architectures de services dédiées :

### A. Le Superviseur (`tableau_de_bord_superviseur`)

* **Périmètre Restreint** : Limite structurellement l'accès aux seules informations du stock physique attribué à l'entrepôt et aux agents directement rattachés à sa hiérarchie.
* **Sécurisation** : Si le profil utilisateur ne valide pas les prérequis de supervision, l'accès est révoqué avec redirection vers la page de connexion.

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
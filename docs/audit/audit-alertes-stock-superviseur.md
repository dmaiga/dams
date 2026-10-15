# Audit — Alertes de stock ancien et stock auto-attribué au superviseur

**Date** : 15/10/2026 · **Statut** : à traiter plus tard (décision mdmaiga : non pertinent pour l'instant)

## Constat

Depuis le 15/10/2026, une affectation du gestionnaire de stock sans agent choisi est attribuée au
superviseur lui-même (`marchandise.AffectationSuperviseurForm.save` : `agent_terrain = superviseur`,
`quantite_restante = 0`, `agent_terrain_direct = superviseur`).

Conséquence sur `surveillance/services/stock_age_service.py` :

| Alerte | Source | Voit ce stock ? |
|---|---|---|
| Stock chez le superviseur (3 j) | `AffectationLotSuperviseur.quantite_restante > 0` | Non — le reste est à 0 |
| Stock retenu par les agents (3 j) | `DetailDistribution` filtré sur `TYPES_AGENT_VENTE = ['terrain', 'agent_gros']` | Non — le superviseur est de type `entrepot` |

Le stock auto-attribué à un superviseur et non vendu n'est donc couvert par aucune alerte de stock
ancien. Il reste visible dans `direction/suivi-distributions/` (table 1 et checklist à investiguer) et
dans le suivi de stock des agents.

## Piste de correction

Étendre `_queryset_stock_retenu_agents` aux détails dont `distribution.agent_terrain` est de type
`entrepot` (auto-distribution), avec un libellé « superviseur » distinct dans l'alerte.

## Autres points relevés

- `marchandise.CorrectionDistributionService._charger_distribution_directe` identifie la distribution
  d'une affectation par (lot, superviseur, agent). Deux affectations du même lot au même superviseur
  sans agent donnent deux distributions identiques : la correction est alors refusée (ambiguïté).
- Le stock en attente antérieur au 15/10/2026 (`agent_terrain_direct` NULL) reste géré par le flux
  d'exception `vente/` ; il disparaît à mesure qu'il est distribué.

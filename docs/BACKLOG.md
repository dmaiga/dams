# BACKLOG.md — Suivi des demandes en cours

**Propriétaire** : Chef de Projet
**But** : vue d'ensemble de toutes les demandes actives, tous chantiers confondus (BI + évolutions app DAMS), pour prioriser sans perdre le fil.
**Mise à jour** : au fil de l'eau, dès qu'une nouvelle demande arrive ou qu'un statut change.

---

## Légende

Priorité :
- 🔴 **Urgent** — à traiter avant tout nouveau sujet
- 🟡 **Normal** — planifié, pas bloquant
- 🟢 **Bas** — quand il y a de la place

Statut : 🆕 nouvelle · 📋 à cadrer · 🟡 en cours · ⏸️ en attente · ✅ terminée

---

## Chantier 1 — Projet BI (dashboards direction)

**Statut** : 🟡 en cours — première revue utilisateur faite le 20/07/2026
**Suivi détaillé** : [docs/docs_bi/owner/02_Backlog.md](docs_bi/owner/02_Backlog.md) (stories du MVP) et [docs/docs_bi/chef_projet/QUESTIONS_OUVERTES.md](docs_bi/chef_projet/QUESTIONS_OUVERTES.md) (retours à chaud Q1–Q3 à trancher avec la Direction).

Ne pas dupliquer le détail ici — ce chantier a déjà son propre backlog produit. Cette ligne existe pour qu'il apparaisse dans la vue d'ensemble et que sa charge soit visible à côté des autres demandes.

---

## Chantier 2 — App `surveillance` : suivi durée de vie du stock + alertes

**Statut** : 🆕 nouvelle demande (22/07/2026) — 📋 à cadrer avant développement
**Priorité** : 🟡 Normal
**Périmètre** : app `surveillance` (lecture seule, cohérent avec son rôle actuel de tour de contrôle/alertes — voir [surveillance/APP_SURVEILLANCE.md](../surveillance/APP_SURVEILLANCE.md)).

### Besoin exprimé

Suivre le temps qu'un produit passe dans l'entrepôt entre sa date d'arrivée et sa date de
sortie. Délai raisonnable fixé à **2 jours**. Deux alertes distinctes à produire :

1. **Produits sans vente depuis plus de 2 jours** (rotation attendue non respectée).
2. **Produits en stock depuis plus de 2 semaines** (stock qui dort — argent gelé).

### Décisions (tranchées le 22/07/2026)

- **Granularité** : par lot, au niveau de la distribution à l'agent — pas par produit agrégé.
  Le modèle pivot est `DetailDistribution` (lot distribué à un agent via `DistributionAgent`),
  pas `LotEntrepot` directement.
- **Alerte 1 — sans vente depuis 2 jours** : concerne un **agent** qui a reçu un lot (via
  `DistributionAgent.date_distribution` / `DetailDistribution`) et n'a enregistré **aucune
  vente** (`Vente.detail_distribution`) depuis plus de 2 jours. Le délai se compte depuis la
  distribution à l'agent (ou depuis la dernière vente s'il y en a eu une, pour capter aussi
  l'agent qui vendait puis s'est arrêté) — pas depuis la réception en entrepôt.
- **Alerte 2 — plus de 2 semaines en stock** : concerne un lot **encore en entrepôt**,
  c'est-à-dire pas (ou pas totalement) distribué, depuis plus de 2 semaines. Compté depuis
  `LotEntrepot.date_reception`.
- **« Date de sortie »** = date de distribution du lot par le gestionnaire de stock
  (`DistributionAgent.date_distribution`), pas la date de vente ni l'épuisement du lot.
- **Emplacement** : dans `DashboardSurveillanceView` existant, à côté des ventes rouges déjà
  affichées — pas de vue dédiée séparée.

### Pistes techniques

- Pas de nouveau modèle : tout existe déjà (`LotEntrepot.date_reception`,
  `DistributionAgent.date_distribution`, `DetailDistribution`, `Vente.detail_distribution`).
- Nouveau service dans `surveillance/services/` (ex. `stock_age_service.py`), sur le modèle de
  `PrixSurveillanceService` :
  - **Alerte 1** : `DetailDistribution` sans `Vente` associée (ou dont la dernière vente date
    de plus de 2 jours), jointe à `DistributionAgent.agent_terrain` pour identifier l'agent en
    cause.
  - **Alerte 2** : `LotEntrepot` avec `quantite_restante > 0` et `date_reception` de plus de
    2 semaines, non (ou partiellement) distribué.
  - Une méthode `count_*` par alerte pour les badges du dashboard, avec `limit` pour éviter de
    charger tout le stock en mémoire (pattern déjà en place sur `ventes_a_perte`).
- Respecter les invariants existants de l'app : `est_supprime=False`, pas de mutation, accès
  restreint via `SurveillanceAccessMixin`.

### Prochaine étape

Rédiger un sprint dans `docs/features/sprint-XX.md` en suivant le pattern habituel
(modèles → services → views → templates) avant de coder.

---

## Comment ajouter une nouvelle demande

Ajouter une section `## Chantier N — <titre>` avec statut, priorité, besoin exprimé tel quel,
puis questions à trancher avant d'écrire le moindre code. Ne pas coder tant que les questions
ne sont pas tranchées (cf. `CLAUDE.md` : ne jamais supposer la structure d'un modèle ou d'une
vue).

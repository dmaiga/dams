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
**Suivi détaillé** : [docs/docs_bi/owner/02_Backlog.md](docs_bi/owner/02_Backlog.md) (stories du MVP) et [docs/docs_bi/chef_projet/QUESTIONS_OUVERTES.md](docs_bi/chef_projet/QUESTIONS_OUVERTES.md) (retours à chaud Q1–Q3 à trancher).

Ne pas dupliquer le détail ici — ce chantier a déjà son propre backlog produit. Cette ligne existe pour qu'il apparaisse dans la vue d'ensemble et que sa charge soit visible à côté des autres demandes.

---

## Chantier 2 — App `surveillance` : suivi durée de vie du stock + alertes + refonte navigation

**Statut** : ✅ terminée — livré via les 4 volets de [docs/sprints/sprint-04.md](sprints/sprint-04.md) (`StockAgeService`, vue `StockRotationView`, nav thématique commune `_nav_themes.html`, breadcrumbs contextuels `?from=`).
**Écart assumé** : les deux alertes sont exposées dans un thème dédié "Stock & Rotation" (`stock_rotation/`), pas dans `DashboardSurveillanceView` comme initialement tranché — voir révision du 22/07/2026 ci-dessous. Seul un résumé chiffré agrégé apparaît sur le dashboard global.
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
- **Emplacement** (révisé le 22/07/2026, à la suite d'une revue UX de l'app) : **vue dédiée**
  `stock_rotation/` (nouveau thème « Stock & Rotation », au même rang que Kg vendus et
  Anomalies prix), pas d'ajout de tableaux dans `DashboardSurveillanceView`. Seul un résumé
  chiffré (compteur agrégé) apparaît sur le dashboard global, sur le modèle de la carte
  "Anomalies prix" actuelle. Motif : la navigation de l'app était devenue dispersée
  (liens inter-pages dupliqués et incohérents d'une vue à l'autre) ; entasser deux tableaux
  de plus dans le dashboard aurait aggravé le problème plutôt que de le corriger. La refonte
  de la navigation (nav thématique commune, breadcrumbs contextuels) est intégrée au même
  sprint — voir [docs/sprints/sprint-04.md](sprints/sprint-04.md).

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

Les 4 volets de [docs/sprints/sprint-04.md](sprints/sprint-04.md) (service d'alertes → vue
dédiée → nav thématique commune → breadcrumbs contextuels) sont livrés. Reste à faire un
parcours manuel complet (Dashboard → Stock & Rotation → détail agent/lot → retour) avant
clôture définitive du sprint.

---

## Chantier 3 — Moteur de surveillance métier (Business Monitoring Engine)

**Statut** : 🟡 en cours — cadré dans [docs/sprints/sprint-05.md](sprints/sprint-05.md), prêt à démarrer le Volet 1
**Priorité** : 🟡 Normal
**Périmètre** : transverse — concerne l'ensemble des modules DAMS (`vente`, `finance`, `stock`, `surveillance`, `direction`).

---

## Vision

**Objectif** : Détecter automatiquement les situations anormales et prévenir le responsable de manière fiable (historisation, anti-spam, diffusion multi-canal).

DAMS produit actuellement des alertes dispersées et non historisées :
- `SurveillancePrixService` → anomalies prix (affichage uniquement)
- `StockAgeService` (Sprint 04, Chantier 2) → rotation lente / stock dormant (affichage uniquement)
- `calculer_solde_superviseur` → booléen alerte (affichage brut)

**Aucune n'est** historisée, dédupliquée, classifiée, ou diffusée au-delà du dashboard.

**Mise à jour du 27/07/2026** : `SoldeAlertService` et le dashboard `monitoring_alertes_dashboard`
(`direction/`) qui l'utilisait ont été supprimés — code mort (aucun lien dans la navigation),
avec un bug de déduplication actif qui laissait s'accumuler des `Alerte` dupliquées à chaque
visite. La table `Alerte` a été vidée en conséquence. Chantier 3 repart donc sur un modèle
`Alerte` propre, sans système concurrent à absorber ou migrer.

Le **Chantier 3** crée le **moteur centralisé** qui unifie et généralise ce processus.

---

## Architecture cible

```
Événements métier
    ├─ Surveillance : rotation lente / stock dormant (Chantier 2)
    ├─ Finance : solde superviseur / baisse activité
    ├─ Vente : variation prix
    └─ [autres]
         │
         ▼
Business Monitoring Engine
    ├─ Règles métier
    ├─ Création alertes
    ├─ Déduplication
    ├─ Historique
    └─ Dispatcher
         │
         ▼
Telegram / Dashboard / Logs
```

**Principe clé** : les modules métier ne connaissent jamais Telegram. Ils publient des événements que le moteur consomme.

---

## Lien avec Chantier 2 (Sprint 04)

Chantier 2 produit les **événements bruts** (ex. "Agent X sans vente 2j", "Lot Y dormant 14j"). Chantier 3 les **consomme**, les classe via ses règles, les déduplique, les historise, et les diffuse via Telegram.

---

## MVP — 4 alertes prioritaires

Pour commencer, fokus sur ces 4 cas uniquement :

1. **Solde superviseur élevé** (finance) — seuil dépassé → CRITICAL
2. **Stock ancien** (surveillance) — lot dormant > 14j → WARNING
3. **Variation prix** (vente) — prix modifié / vendu à perte → CRITICAL
4. **Baisse activité** (surveillance) — agent sans vente > 2j → WARNING

---

## Découpage en volets (simplifié)

### Volet 1 — Événements & Règles (cadrage)
**Livrables** :
- Fiche de chaque alerte MVP : source, condition, gravité, destinataire
- Décision : où/comment chaque alerte est détectée (service, signal, management command ?)

### Volet 2 — Modèle & Historique
**Livrables** :
- Étendre `Alerte` existant (ou créer `BusinessAlert`) avec champs nécessaires
- Migration BD

### Volet 3 — Moteur de déduplication
**Livrables** :
- Service `AlerteDeduplicationService` : pas d'envoi identique < 30 min
- Clôture auto quand condition disparaît

### Volet 4 — TelegramProvider
**Livrables** :
- `TelegramProvider` envoie alerte formatée
- Gestion d'erreur (ne fait pas échouer le flux métier)

### Volet 5 — Intégration Chantier 2
**Livrables** :
- Connecter `StockAgeService` (Sprint 04) au moteur
- Alertes "Stock ancien" et "Baisse activité" opérationnelles

---

## Décisions d'architecture (validées)

- **D1** : Règles métier indépendantes des canaux (Telegram n'est qu'un provider)
- **D2** : Canaux interchangeables (Email, SMS, Webhook possibles demain)
- **D3** : Anti-spam : une alerte ACTIVE ne se renvoie pas avant un délai configurable par règle — affiné en `reenvoi_heures` par type dans `docs/sprints/sprint-05.md` (pas un global 30 min : `None` par défaut, 24h pour le solde, 12h pour la baisse d'activité)
- **D4** : Historique complet : toutes les alertes tracées (création, résolution, ignorée)
- **D5** : Découplage : modules métier ne connaissent pas Telegram

---

## Questions critiques (réponses attendues avant Volet 1)

### Q1 — Réutiliser `Alerte` existant ou créer `BusinessAlert` ?

**Impact** : Structure BD + architecture.

**Candidats** :
- **Option A** : Étendre modèle `Alerte` existant (champs `statut`, `date_creation`, `date_resolution`, `nombre_envois`)
- **Option B** : Créer `BusinessAlert` séparé, découplé de `Alerte`

**Points à trancher explicitement avant la migration (constatés le 27/07/2026)**, quelle que soit
l'option choisie :
- `Alerte.superviseur` et `Alerte.agent` sont des FK vers `User`, pas vers `Agent` — il n'existe
  pas de modèle `Superviseur` dans ce repo (c'est `Agent.type_agent='entrepot'`). Toute évolution
  doit rester cohérente avec ce pattern existant (`superviseur=agent.user`).
- `Alerte` n'a aujourd'hui aucun lien générique vers un objet métier arbitraire (seulement une FK
  `produit`) — à décider : FK dédiées nullables par type d'alerte (lot, distribution) ou
  `GenericForeignKey` (`content_type`/`object_id`, nouveau pattern dans ce repo).

**Réponse retenue (27/07/2026)** : Option A (étendre `Alerte`) + FK dédiées nullables `lot`/`distribution` (pas de `GenericForeignKey`) + FK `superviseur`/`agent` inchangées vers `User`. Détail dans `docs/sprints/sprint-05.md` (Volet 2).

---

### Q2 — Mécanisme de publication d'événements ?

**Impact** : Comment les services déclenchent les alertes.

**Candidats** :
- **Option A** : Django signals (découplage naturel)
- **Option B** : Appels directs dans services (explicite)

**Réponse retenue (27/07/2026)** : Option B, via une **commande de management périodique unique** (`monitoring evaluer_alertes`) plutôt qu'un mélange synchrone/périodique — évite de toucher aux points de mutation sensibles de `finance`/`vente`. Détail dans `docs/sprints/sprint-05.md` (Volet 5).

---

### Q3 — Throttling : une alerte par règle ou global ?

**Impact** : Fréquence de renvoi (spam).

**Candidats** :
- **Option A** : Par défaut "une fois par 30 min", configurable par alerte
- **Option B** : Pas de renvoi si déjà ACTIVE (une seule fois)

**Réponse retenue (27/07/2026)** : mixte, configurable par type (`reenvoi_heures` dans `monitoring/constants.py`) — `None` par défaut (Option B), sauf `solde` (24h) et `activite` (12h). Détail dans `docs/sprints/sprint-05.md` (Volet 3).

---

## Prochaines étapes

1. ✅ **Trancher Q1, Q2, Q3** avec mdmaiga — voir réponses retenues ci-dessus et `docs/sprints/sprint-05.md`
2. **Volet 1** (sprint-05) : confirmer les 4 fiches d'alertes MVP
3. **Volets 2-5** (sprint-05) : modèle, déduplication, TelegramProvider (stub), moteur + commande
4. **Volets 3-5** : Déployer progressivement

---

## Scope futur (pas MVP)

- Routage par destinataire (aujourd'hui : tout → mdmaiga)
- Nouvelles règles (versement retard, dette trop élevée, etc.)
- Nouveaux providers (Email, SMS, Webhook)
- Analyse dashboards (alertes résolues cette semaine, par type, par agent)
- Règles configurables (sans redéploiement)

---

## Comment ajouter une nouvelle demande

Ajouter une section `## Chantier N — <titre>` avec statut, priorité, besoin exprimé tel quel,
puis questions à trancher avant d'écrire le moindre code. Ne pas coder tant que les questions
ne sont pas tranchées (cf. `CLAUDE.md` : ne jamais supposer la structure d'un modèle ou d'une
vue).
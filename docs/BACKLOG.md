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

## Chantier 2 — App `surveillance` : suivi durée de vie du stock + alertes + refonte navigation

**Statut** : 🟡 en cours — cadré et fusionné avec la refonte de navigation dans [docs/sprints/sprint-04.md](sprints/sprint-04.md)
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

Sprint rédigé : [docs/sprints/sprint-04.md](sprints/sprint-04.md), découpé en 4 volets
(service d'alertes → vue dédiée → nav thématique commune → breadcrumbs contextuels),
chacun avec son propre Definition of Done. Prêt à démarrer le Volet 1.

---

## Chantier 3 — Notifications Telegram

**Statut** : 🆕 nouvelle — à cadrer
**Priorité** : 🟡 Normal
**Périmètre pressenti** : transverse — s'appuie sur les événements produits par `surveillance` (Chantier 2), `finance` et le modèle `Alerte` existant (`core`, utilisé aujourd'hui par `direction/services/alertes/`).

### Besoin exprimé

Mettre en place un système de notifications basé sur Telegram afin d'informer les responsables
des événements importants de la plateforme DAMS. Temps réel ou différé — peu importe pour
l'instant, à évaluer au moment venu en fonction de la charge.

### Constat sur l'existant (avant de cadrer)

- Un modèle générique `Alerte` existe déjà dans `core` (`type_alerte`: solde/stock/prix/activite,
  `niveau`: info/warning/critique, `message`, `superviseur`/`agent`/`produit` optionnels,
  `est_vue`, `date_creation`).
- Il n'est alimenté que par `SoldeAlertService.check_superviseur_solde()`
  (`direction/services/alertes/solde.py`) — les fichiers `stock.py`, `activite.py` et `prix.py`
  du même dossier sont **vides**, malgré les choix `TYPES` correspondants sur le modèle.
- Ce service n'est appelé **qu'à la demande**, quand la direction charge
  `monitoring_alertes_dashboard` (`direction/views.py`) — pas de tâche planifiée, pas de signal.
  Le repo n'a **ni Celery ni APScheduler ni cron applicatif** ; seules des management commands
  invoquées manuellement ou par une tâche planifiée OS (`cloturer_mois` par ex.) existent.
- Le sprint-04 (Chantier 2, `surveillance`) vient de cadrer deux nouvelles alertes (rotation
  lente, stock dormant) via `StockAgeService`, mais **sans** passer par le modèle `Alerte` — ce
  sont des requêtes calculées à l'affichage de `StockRotationView`, pas des enregistrements.
- `finance/services.py::calculer_solde_superviseur` calcule déjà un booléen `alerte` (seuil
  100 000 FCFA, `SEUIL_ALERTE_SOLDE`) mais ne crée pas non plus de `Alerte` — c'est affiché tel
  quel dans `dashboard_finance`.
- `requests` est déjà une dépendance du projet (`requirements.txt`) — suffisant pour appeler
  l'API Bot HTTP de Telegram sans nouvelle librairie.

Conséquence : il n'existe aujourd'hui **aucun mécanisme de déclenchement proactif** dans DAMS.
Toutes les "alertes" actuelles sont passives (calculées quand une page est ouverte). Un vrai
"temps réel" demanderait soit un déclenchement synchrone au moment de l'écriture (dans les vues/
services `finance`, `vente`, `surveillance`...), soit un worker dédié. Un mode "différé" peut se
contenter d'une management command lancée périodiquement, cohérent avec le seul pattern de
planification déjà en place dans le repo (tâche OS + `manage.py <commande>`), sans dépendance
nouvelle.

### Questions à trancher avant d'écrire le moindre code

1. **Quels événements notifier en priorité (MVP) ?** Candidats identifiés dans le code existant :
   - Solde superviseur au-dessus du seuil (`finance`, `SEUIL_ALERTE_SOLDE`) / cash détenu sans
     versement depuis 24h-48h (`SoldeAlertService`).
   - Rotation lente / stock dormant (`surveillance`, Chantier 2 / sprint-04).
   - Anomalies prix (ventes "rouges", déjà détectées par `PrixSurveillanceService` mais jamais
     écrites en `Alerte` — type `prix` existe sur le modèle mais orphelin).
   - Autre chose (dette agent, dépense inhabituelle, etc.) ?
2. **Qui reçoit quoi ?** Un seul chat Telegram (direction), ou un routage par destinataire/rôle
   (ex. superviseur concerné vs mdmaiga) ? Le modèle `Alerte` a déjà `superviseur`/`agent` — à
   réutiliser ou pas pour le ciblage.
3. **Mécanisme de déclenchement** : synchrone (appel Telegram directement dans les services qui
   créent l'événement, ex. `SoldeAlertService._create_alert`) vs asynchrone via une management
   command périodique qui balaie les `Alerte` non notifiées. Impacte directement le choix
   temps réel/différé mentionné dans le besoin — à trancher une fois la charge estimée.
4. **Réutiliser `Alerte` ou créer un modèle dédié ?** Option A : étendre `Alerte` (ex. champs
   `notifie_telegram: bool`, `date_notification`) et combler les services vides
   (`stock.py`, `activite.py`, `prix.py`, plus le futur cas `surveillance`/Chantier 2). Option B :
   modèle `NotificationTelegram` séparé, découplé de `Alerte`, qui s'abonne aux mêmes
   événements sans modifier le modèle existant.
5. **Configuration Telegram** : `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` en variable
   d'environnement (cohérent avec le pattern `.env` de `rules/STACK.md`) — un seul chat pour
   commencer, ou un mapping par destinataire dès le MVP ?
6. **Gestion des échecs d'envoi** : Telegram indisponible ou token invalide ne doit pas faire
   échouer le flux métier appelant (ex. création d'un versement) — retry, log silencieux, ou
   file d'attente minimale ?

### Prochaine étape

Trancher les questions ci-dessus avec mdmaiga (en particulier la question 1 — périmètre MVP —
et la question 3, qui conditionne toute l'architecture) avant de rédiger le sprint correspondant
dans `docs/sprints/`.

---

## Comment ajouter une nouvelle demande

Ajouter une section `## Chantier N — <titre>` avec statut, priorité, besoin exprimé tel quel,
puis questions à trancher avant d'écrire le moindre code. Ne pas coder tant que les questions
ne sont pas tranchées (cf. `CLAUDE.md` : ne jamais supposer la structure d'un modèle ou d'une
vue).

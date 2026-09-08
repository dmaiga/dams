# Sprint 12 — Audit du stock dormant (superviseurs + agents) et enrichissement des notifications Telegram

**Statut** : 📋 à faire — demande de mdmaiga (08/09/2026).

Sprint d'**investigation + durcissement**, pas de nouvelle capacité : la détection du stock
dormant existe déjà pour les trois emplacements (entrepôt, superviseur, agent) et les trois
messages Telegram correspondants sont déjà émis. L'objet du sprint est (1) de vérifier que ces
détections sont correctes, (2) de combler les trous identifiés ci-dessous, (3) d'aligner le
format Telegram « stock superviseur » et « stock agent » sur le niveau de détail déjà présent
ailleurs (date de réception + quantité restante + valeur immobilisée), comme demandé.

---

## Contexte

Deux besoins remontés ensemble :

1. **Vérifier** que le « stock dormant » est bien surveillé côté **agents de vente** *et* côté
   **superviseurs** — mdmaiga pense que c'est déjà en place mais veut une confirmation, pas une
   supposition (cf. CLAUDE.md : « Ne jamais supposer… lire le fichier source avant d'y toucher »).
2. **Recevoir sur Telegram**, dans un format lisible et homogène avec le reste des alertes, la
   liste du stock dormant des superviseurs et celle du stock dormant des agents.

---

## Constat 1 — Ce qui existe déjà (vérifié, réutilisable tel quel)

### 1.1 — `surveillance/services/stock_age_service.py::StockAgeService`

`lots_stock_dormant()` produit une liste de lignes typées par `origine` ∈ {`entrepot`,
`superviseur`, `agent`}, chacune avec `produit`, `fournisseur`, `reference_lot`,
`localisation`, `superviseur`, `date_reference`, `quantite_restante`, `valeur_immobilisee`,
`jours_ecoules` (+ `agent` pour l'origine `agent`).

| Origine | Source | Seuil (`surveillance/constants.py`) | Filtre reliquat |
|---------|--------|-------------------------------------|-----------------|
| `entrepot` | `LotEntrepot` encore au dépôt | `DELAI_STOCK_DORMANT_JOURS = 15` j | `quantite_restante > 0` (SQL) |
| `superviseur` | `AffectationLotSuperviseur` pas encore redistribuée | `DELAI_RETENTION_ACTEURS_JOURS = 3` j | `quantite_restante > 0` (SQL) |
| `agent` | `DetailDistribution` détenu par un `terrain`/`agent_gros` | `DELAI_RETENTION_ACTEURS_JOURS = 3` j | `quantite_restante_calculee > 0` (Python, N+1) |

Plancher commun : `DATE_PLANCHER_STOCK = date(2026, 7, 1)` — toute distribution/affectation
antérieure est ignorée.

Méthodes annexes : `count_lots_stock_dormant()`, `valeur_stock_dormant()` (rejouent le calcul
complet, N+1 agent inclus — **ne pas les appeler dans une vue**, cf. Constat 3.4), et le trio
`lots_dormants_entrepot()` / `count_lots_dormants_entrepot()` / `valeur_stock_dormant_entrepot()`
réservé à l'UI (entrepôt seul, SQL pur — introduit après l'incident perf du 13/08/2026).

### 1.2 — Notifications Telegram (`monitoring/services/moteur_alerte.py::AlerteMoteur`)

`evaluer_stock_ancien()` répartit les lignes de `lots_stock_dormant()` par origine et émet
**trois messages distincts** via `AlerteDeduplicationService` + `TelegramProvider` :

| `type_alerte` | Titre du message | Regroupement | Détail par ligne aujourd'hui |
|---------------|------------------|--------------|------------------------------|
| `stock_entrepot` | `⚠️ STOCK DORMANT — ENTREPÔT` | à plat | `{produit}` / `reçu le {date}` / `{jours} jours` |
| `stock_superviseur` | `⚠️ STOCK EN RÉTENTION — SUPERVISEURS` | par superviseur | `{produit} — reçu le {date} — {jours} jours` |
| `stock_agent` | `⚠️ STOCK CHEZ LES AGENTS` | superviseur → agent | `{produit} — {jours} jours` |

`evaluer_alertes` (commande cron, `monitoring/management/commands/evaluer_alertes.py`) appelle
`evaluer_stock_ancien()` à chaque passage.

**Conclusion de la vérification** : oui, la surveillance du stock dormant couvre déjà les agents
*et* les superviseurs, et les deux alertes Telegram existent. Le sprint ne crée donc rien de
neuf sur le principe — il corrige et enrichit.

### 1.3 — Commande `agents_stock_dormant` (référence de format)

`surveillance/management/commands/agents_stock_dormant.py` (+ `StockAgeService.
stock_detenu_agents_par_superviseur(date_debut, date_fin)`) produit déjà, sur une période bornée,
la sortie groupée superviseur → agent → lignes produit avec, par ligne :

```
  - aloco reçu le 22/08/2026 (reste 12.00)
```

C'est **ce niveau de détail** (produit + date de réception + quantité restante) que mdmaiga veut
retrouver dans les messages Telegram « superviseur » et « agent » — « lisible comme pour le
reste ».

### 1.4 — UI dashboard surveillance

`surveillance/views/stock_rotation.py` n'affiche **que** l'origine `entrepot` (méthodes SQL pures
`lots_dormants_entrepot()`), volontairement — la rétention superviseur/agent filtrable est du
ressort de `direction.suivi_distributions` (`direction/views.py`), pas de la surveillance. Ce
choix n'est pas remis en cause par ce sprint.

---

## Constat 2 — Trous et incohérences identifiés (à trancher / corriger)

### 2.1 — Le message Telegram « agent » est trop pauvre

`_envoyer_stock_agents` n'affiche que `{produit} — {jours} jours`. Manquent : la **date de
réception** (présente dans le message superviseur et dans la commande) et la **quantité
restante** (présente dans la commande). Impossible depuis Telegram de savoir *combien* dort et
*depuis exactement quand*.

### 2.2 — Le message Telegram « superviseur » n'affiche pas la quantité ni la valeur

`_envoyer_stock_superviseurs` affiche `{produit} — reçu le {date} — {jours} jours` mais pas
`quantite_restante` ni `valeur_immobilisee`, toutes deux pourtant déjà calculées dans la ligne.

### 2.3 — `AffectationLotSuperviseur` en distribution directe attribuée au superviseur à tort

`_queryset_lots_dormants_superviseur` ne filtre pas `agent_terrain_direct`. Or une affectation
créée par le gestionnaire de stock en **distribution directe à l'agent**
(`AffectationLotSuperviseur.agent_terrain_direct` renseigné, cf.
`rules/ARCHITECTURE.md` § invariants) n'a jamais transité par le superviseur : si son
`quantite_restante` reste > 0 au-delà de 3 jours, elle apparaît aujourd'hui comme « stock en
rétention superviseur » alors que le superviseur ne l'a jamais eue en main. À confirmer sur
données réelles, puis exclure (`agent_terrain_direct__isnull=True`) — ou, si le reliquat d'une
affectation directe est un vrai signal, le rattacher à l'agent destinataire et non au
superviseur.

### 2.4 — Interaction avec la réaffectation de portefeuille (sprint précédent, 08/09/2026)

La fonctionnalité `direction.reaffectation_agents` rebascule les `DistributionAgent` non soldées
d'un agent vers son nouveau superviseur (`DistributionAgent.superviseur` réécrit). L'origine
`agent` de `StockAgeService` regroupe par `agent.superviseur` **courant** (via
`_lignes_stock_retenu_agents`), pas par le superviseur inscrit sur la distribution — donc après
un transfert, le stock dormant de l'agent remonte bien sous le nouveau superviseur. Comportement
cohérent, **à documenter** (test de non-régression) plutôt qu'à modifier.

### 2.5 — `DATE_PLANCHER_STOCK` = 01/07/2026

Fixé il y a deux mois. Vérifier qu'il ne masque pas aujourd'hui des lots réellement dormants
(distribution de fin juin encore non écoulée). Décision attendue de mdmaiga : garder, avancer,
ou supprimer le plancher pour ce thème.

### 2.6 — Déduplication : rafraîchissement du message

`AlerteDeduplicationService.get_ou_creer(type_alerte=..., defaults={"message": ...})` sans clé
d'identification : vérifier que lorsque la **composition** de la liste change (un produit écoulé,
un nouveau qui entre en dormance) mais que l'alerte reste ACTIVE, le `message` stocké est bien
mis à jour et re-poussé sur Telegram — et pas figé à sa première version. (Comportement présumé
correct d'après le commentaire de classe, mais non couvert par un test dédié.)

### 2.7 — Coût N+1 sur `_lignes_stock_retenu_agents`

Accepté à l'écrit (volume attendu faible). `evaluer_stock_ancien` n'appelle `lots_stock_dormant()`
qu'une fois par passage cron, donc pas de multiplication ×3 comme sur l'ancienne page
stock-rotation. À quantifier une fois sur la base réelle (nombre de `DetailDistribution` > 3 j
avec reliquat) pour confirmer que ça reste négligeable ; si le volume a grossi, remplacer la
property par une agrégation SQL des ventes/pertes par `detail_distribution_id` (même approche que
`direction/views.py::_stock_ouvert_par_agent`, écrit le 08/09/2026).

---

## Décisions à acter (mdmaiga) — avant implémentation

1. **Contenu exact des lignes Telegram enrichies.** Proposition (à valider) :
   - superviseur : `• {produit} — reste {quantite} — reçu le {date} — {jours} j — {valeur} FCFA`
   - agent : idem, sous le nom de l'agent, lui-même sous le nom du superviseur.
   Faut-il la **valeur immobilisée** (donnée sensible ?) ou seulement quantité + ancienneté ?
2. **Sous-total par superviseur** (Σ valeur / Σ jours max) en tête de chaque bloc, ou lignes
   seules ?
3. **`agent_terrain_direct`** (Constat 2.3) : exclure de l'origine `superviseur`, ou rattacher à
   l'agent ?
4. **`DATE_PLANCHER_STOCK`** (Constat 2.5) : garder 01/07/2026 / avancer / retirer.
5. **Seuil superviseur** : `DELAI_RETENTION_ACTEURS_JOURS = 3` j est-il toujours le bon seuil
   d'alerte pour un superviseur, ou faut-il un délai propre (`DELAI_RETENTION_SUPERVISEUR_JOURS`) ?

---

## Tâches (ordonnées)

### 1. Investigation (aucune écriture de code)

- Exécuter `agents_stock_dormant --date_debut 2026-07-01 --date_fin <aujourd'hui>` sur la base
  réelle : combien d'agents, combien de superviseurs, quel volume de lignes.
- Requête ad hoc : nombre d'`AffectationLotSuperviseur` avec `agent_terrain_direct` renseigné
  *et* `quantite_restante > 0` *et* `date_affectation` > 3 j → confirmer/infirmer Constat 2.3.
- Compter les `DetailDistribution` entrant dans `_lignes_stock_retenu_agents` → chiffrer le N+1
  (Constat 2.7).
- Vérifier le comportement de rafraîchissement de `AlerteDeduplicationService` sur un changement
  de composition (Constat 2.6), en shell si besoin.
- Consigner les résultats dans une section « Résultats d'investigation » de ce fichier.

### 2. `StockAgeService` — corrections ciblées

- Constat 2.3 : selon décision n°3, ajouter `agent_terrain_direct__isnull=True` à
  `_queryset_lots_dormants_superviseur` (ou re-router la ligne vers l'origine `agent`).
- Constat 2.5 : selon décision n°4, ajuster/retirer `DATE_PLANCHER_STOCK` pour ce thème (attention :
  la constante sert aussi `agents_sans_vente_recente` et l'entrepôt — si le plancher doit changer
  seulement pour la rétention acteurs, introduire une constante dédiée plutôt que déplacer
  l'existante).
- Constat 2.7 : si le volume l'impose, remplacer la boucle sur `quantite_restante_calculee` par
  une agrégation SQL `Sum` des ventes (`est_supprime=False`) et des pertes par
  `detail_distribution_id`, recombinée en Python — **sans** jointure croisée ventes×pertes.
- Ne rien changer aux seuils sans décision explicite (n°5).

### 3. `moteur_alerte.py` — enrichissement du format (cœur de la demande)

- `_envoyer_stock_superviseurs` : ajouter `reste {quantite}` et, selon décision n°1,
  `{valeur} FCFA` (via `core.templatetags.format_fcfa.fcfa`, déjà importé dans le module) sur
  chaque ligne. Optionnel (décision n°2) : ligne de sous-total par superviseur.
- `_envoyer_stock_agents` : passer du format `{produit} — {jours} jours` au même format riche
  que le bloc superviseur (produit + reste + date de réception + jours [+ valeur]), en conservant
  la hiérarchie superviseur → agent → produits déjà en place.
- Factoriser le rendu d'une ligne produit dans un helper commun aux deux fonctions (`_ligne_stock(p)`)
  pour garantir que « superviseur » et « agent » restent identiques dans le temps.
- Ne pas toucher `_envoyer_stock_entrepot` (hors demande) — mais si le helper commun s'y prête
  sans risque, l'y appliquer aussi pour l'homogénéité (à apprécier).
- Respecter la contrainte `TelegramProvider` : `text` simple (pas de `parse_mode`), messages
  potentiellement longs → si un bloc dépasse ~4000 caractères, prévoir un découpage (aujourd'hui
  non géré ; à noter si le volume réel s'en approche, sinon différer).

### 4. Tests (`surveillance/tests.py`, `monitoring/tests.py`)

- `StockAgeService` :
  - affectation en distribution directe (`agent_terrain_direct`) avec reliquat > 3 j → **absente**
    de l'origine `superviseur` (ou présente sous `agent`, selon décision).
  - non-régression Constat 2.4 : après réécriture de `DistributionAgent.superviseur` (réaffectation),
    la ligne `agent` remonte sous le **nouveau** superviseur.
  - le cas échéant, non-régression sur le nouveau plancher/seuil.
- `moteur_alerte` :
  - le message `stock_superviseur` contient la quantité restante (et la valeur si retenue).
  - le message `stock_agent` contient produit + quantité + date + ancienneté, dans la hiérarchie
    superviseur → agent.
  - rafraîchissement : deux évaluations successives avec une composition différente → `Alerte.message`
    mis à jour, `TelegramProvider.send` rappelé (mock).

### 5. Documentation

- `docs/features/app_surveillance.md` : compléter la section stock dormant (3 origines, seuils,
  ce qui va sur Telegram vs l'UI) et ajouter la ligne Sprint 12 au tableau des sprints.
- `surveillance/APP_SURVEILLANCE.md` (si présent) / `monitoring` : refléter le nouveau format des
  messages `stock_superviseur` / `stock_agent`.
- Reporter ici les « Résultats d'investigation » (Tâche 1) et les décisions finales.

---

## Definition of Done

- Section « Résultats d'investigation » remplie : volumes réels, statut du Constat 2.3 (leak
  `agent_terrain_direct`), coût du N+1, comportement de rafraîchissement dedup.
- Les messages Telegram `stock_superviseur` et `stock_agent` affichent, par ligne produit :
  produit + quantité restante + date de réception + ancienneté (+ valeur si décision n°1 la
  retient), dans la hiérarchie superviseur (→ agent), rendu via un helper unique partagé.
- Aucun seuil ni plancher modifié sans décision actée (n°4, n°5) tracée dans ce fichier.
- Si Constat 2.3 est confirmé : l'affectation en distribution directe ne pollue plus l'alerte
  superviseur, avec test dédié.
- Tests verts : `python manage.py test surveillance monitoring`.
- `agents_stock_dormant` (commande) et `evaluer_alertes` (cron) inchangés dans leur interface —
  seule la mise en forme du message évolue.
- Docs à jour (`app_surveillance.md` + note d'app monitoring/surveillance).

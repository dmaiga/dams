# APP_SURVEILLANCE.md — État de l'application après Sprint 01

## Rôle de l'app

Audit et monitoring de l'activité de distribution :
- Volumes de ventes (kg) par semaine / mois
- Anomalies de prix (ventes sous coût d'achat)
- Performance par superviseur et par produit

Lecture seule sur la base `core`. Aucune mutation de données.

---

## Accès et sécurité

**Mixin :** `surveillance.mixins.SurveillanceAccessMixin`

| Profil | Accès |
|--------|-------|
| Superutilisateur Django | Oui |
| Agent `direction` | Oui |
| Tout autre rôle (entrepôt, terrain, rot…) | Non — HTTP 403 |
| Non connecté | Redirection `/login/` |

Toutes les CBV héritent de `SurveillanceAccessMixin` avant `TemplateView`.

---

## Constantes de référence

Fichier : `surveillance/constants.py`

| Constante | Valeur | Usage |
|-----------|--------|-------|
| `DATE_PLANCHER_VENTES` | `date(2026, 1, 1)` | Plancher global sur tous les volumes KG |
| `DATE_PLANCHER_PRIX` | `date(2026, 6, 1)` | Plancher sur les anomalies de prix uniquement |

---

## Utilitaires semaine — `surveillance/week_utils.py`

| Fonction | Rôle |
|----------|------|
| `debut_semaine(d)` | Retourne le lundi de la semaine contenant `d` |
| `fin_semaine(d)` | Retourne le dimanche |
| `semaine_precedente(debut)` | `(lundi, dimanche)` de S-1 |
| `parse_semaine(raw)` | Parse `"2026-W25"` → `date` ; fallback sur semaine courante ; bloque les dates futures |
| `date_to_week_string(d)` | `date` → `"2026-W25"` |

---

## Couche services

### `ComparaisonPeriodeService` (`comparaison_service.py`)

| Méthode | Paramètre | Rôle |
|---------|-----------|------|
| `semaine(debut)` | `date` | `(lundi, dimanche)` de la semaine donnée |
| `semaine_prec(debut)` | `date` | `(lundi, dimanche)` de S-1 |
| `semaine_actuelle()` | — | Semaine courante (alias) |
| `semaine_precedente()` | — | S-1 courante (alias) |
| `mois_actuel()` | — | Mois en cours |
| `mois_precedent()` | — | Mois précédent |

### `VenteSurveillanceService` (`vente_service.py`)

- `kg_vendus(date_debut, date_fin, superviseur=None, produit=None)` → `Decimal`
- Applique automatiquement `max(date_debut, DATE_PLANCHER_VENTES)`

### `ListeKgVenduService` (`liste_kg_service.py`)

- `get_kpis(debut, fin)` → dict KPI globaux
- `get_superviseurs(debut, fin)` → liste triée par kg décroissant
- `get_agents(debut, fin, superviseur=None, produit=None)` → liste triée par kg décroissant
- Tous les filtres appliquent `DATE_PLANCHER_VENTES`

### `SuperviseurSurveillanceService` (`superviseur_service.py`)

- `variations_semaine(debut_semaine=None)` → liste `{superviseur, kg_actuel, kg_prec, variation}`
- Sans `debut_semaine` : utilise la semaine courante

### `ProduitSurveillanceService` (`produit_service.py`)

- `variations_semaine(debut_semaine=None)` → liste `{produit, kg_actuel, kg_prec, variation}`

### `PrixSurveillanceService` (`prix_service.py`)

Détecte les ventes dont `prix_vente_unitaire < prix_achat_unitaire` depuis `DATE_PLANCHER_PRIX`.

| Méthode | Paramètre | Rôle |
|---------|-----------|------|
| `ventes_a_perte(limit=None)` | `limit` int | Liste des lots en anomalie ; `limit` applique un `LIMIT` SQL pour éviter le chargement mémoire |
| `count_anomalies()` | — | Nombre de lots distincts en anomalie (pour badge) — 1 requête COUNT |

**Pattern performance :** le dashboard appelle `ventes_a_perte(limit=10)` → seuls 10 lots sont chargés, quels que soient les volumes.

### `SurveillancePrixService` (`surveillance_prix_service.py`)

- `get_resume(order_by=None)` → `{stats, lignes}` — trie par `date_reception` (ASC/DESC) ou par écart
- `get_detail_lot(lot)` → détail complet d'un lot : ventes, résumé par agent
- Filtre systématique `date_vente__date__gte=DATE_PLANCHER_PRIX`

### `DetailSuperviseurService` / `DetailProduitService`

- `get_data(objet, debut_semaine=None)` → KPIs + variations sur la semaine sélectionnée

---

## Vues

| Vue | URL | Mixin | Filtre semaine |
|-----|-----|-------|---------------|
| `DashboardSurveillanceView` | `/surveillance/` | Oui | Oui |
| `ListeKgVenduView` | `/surveillance/kg/` | Oui | Oui |
| `DetailSuperviseurView` | `/surveillance/superviseur/<pk>/` | Oui | Oui |
| `DetailProduitView` | `/surveillance/produit/<pk>/` | Oui | Oui |
| `SurveillancePrixView` | `/surveillance/prix/` | Oui | Non (continu depuis 01/06/2026) |
| `DetailPrixView` | `/surveillance/prix/<lot_id>/` | Oui | Non |

**Contexte commun injecté dans les vues avec filtre semaine :**
- `semaine_selectionnee` : format `"2026-W25"` (valeur du widget)
- `semaine_max` : semaine courante (bloque les dates futures dans le widget)

---

## Templates

| Template | Rôle |
|----------|------|
| `partials/_filtre_semaine.html` | Widget `<input type="week">` réutilisable ; conserve les autres paramètres GET |
| `dashboard_surveillance.html` | Vue d'ensemble : KG semaine/mois, ventes rouges (top 10), superviseurs, produits |
| `kg_vendu/liste_kg_vendu.html` | Détail KG par superviseur et par agent |
| `superviseur/detail_superviseur.html` | Fiche superviseur avec variation semaine |
| `produits/detail_produit.html` | Fiche produit avec variation semaine |
| `prix/surveillance_prix.html` | Liste lots en anomalie — tri interactif `date_reception` |
| `prix/detail_prix.html` | Détail ventes d'un lot en anomalie |

---

## Invariants

- Les données antérieures au 01/01/2026 n'apparaissent jamais dans les volumes KG.
- Les anomalies de prix antérieures au 01/06/2026 ne sont jamais affichées.
- Le filtre `date_vente` porte sur la date de la vente, **pas** la date de réception du lot.
- `parse_semaine` empêche toute sélection de semaine future (protection côté serveur).
- Toutes les requêtes utilisent `est_supprime=False`.

---

## Stock dormant & alertes Telegram (Sprint 04, enrichi Sprint 12)

Ce document est resté figé à l'état "après Sprint 01" ; cette section comble le trou le plus
consulté (le stock dormant) sans réécrire l'historique complet — voir `surveillance/
APP_SURVEILLANCE.md` (doc technique détaillée, tenue à jour à chaque sprint) et
`monitoring/APP_MONITORING.md` (moteur d'alertes) pour le reste.

`StockAgeService` (`surveillance/services/stock_age_service.py`) détecte un produit qui traîne
trop longtemps sans être vendu, à **trois emplacements distincts**, chacun avec son propre seuil
(`surveillance/constants.py`) :

| Origine | Source | Seuil | Portée |
|---------|--------|-------|--------|
| `entrepot` | `LotEntrepot` non distribué | `DELAI_STOCK_DORMANT_JOURS = 15` j | UI (`/surveillance/stock-rotation/`) **et** Telegram (`stock_entrepot`) |
| `superviseur` | `AffectationLotSuperviseur` pas redistribuée | `DELAI_RETENTION_ACTEURS_JOURS = 3` j | Telegram uniquement (`stock_superviseur`) |
| `agent` | `DetailDistribution` détenu par un agent de vente | `DELAI_RETENTION_ACTEURS_JOURS = 3` j | Telegram uniquement (`stock_agent`) |

Plancher commun : `DATE_PLANCHER_STOCK = date(2026, 7, 1)` — toute distribution/affectation
antérieure est ignorée. Posé volontairement pour faire abstraction d'un passé jugé incertain ;
confirmé (décision mdmaiga, sprint-12, 17/09/2026) après réexamen malgré des cas plus anciens
identifiés en cours de route.

**UI vs Telegram** : l'écran `/surveillance/stock-rotation/` n'affiche que l'origine `entrepot`
(recadrage du 13/08/2026, incident de performance ~2400 requêtes SQL corrigé) — la rétention
superviseur/agent, plus précise et filtrable, vit dans `direction.suivi_distributions`, pas ici.
Les origines `superviseur` et `agent` ne remontent donc **que** par les notifications Telegram du
moteur d'alertes (`monitoring`), pas de doublon d'UI.

**Alertes Telegram** (`monitoring.services.moteur_alerte::AlerteMoteur.evaluer_stock_ancien`,
exécuté chaque matin par la commande cron `evaluer_alertes`) : un message distinct par origine,
`reenvoi_heures=48` pour `stock_superviseur`/`stock_agent` (sprint-12 — corrige un bug où l'alerte
ne se renvoyait plus jamais après son premier envoi), chaque ligne produit au format
`• {produit} — reste {quantité} — reçu le {date} — {jours} j`. Détail complet dans
`monitoring/APP_MONITORING.md`.

---

## Sprints

| Sprint | Périmètre |
|--------|-----------|
| [Sprint 01](sprint-01.md) | Filtres semaine, dates planchers, sécurité (mixin), performance (SQL slicing) |
| [Sprint 12](../sprints/sprint-12.md) | Audit + durcissement du stock dormant (superviseurs/agents) : correction du bug d'absence de renvoi Telegram (`reenvoi_heures`), enrichissement des messages (quantité + date + ancienneté), garde-fou `agent_terrain_direct`, confirmation du plancher `DATE_PLANCHER_STOCK` |

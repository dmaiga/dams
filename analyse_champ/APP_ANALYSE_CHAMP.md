# 📘 App : `analyse_champs` (Pilotage Analytique & Consommation API)

## 📌 Rôle & Vision

L'application `analyse_champs` sert de **noyau décisionnel et analytique déporté**. Contrairement aux applications opérationnelles qui écrivent directement en base de données via l'ORM Django, ce module est conçu pour **consommer une API REST distante** (définie par la variable `API_URL`).

Elle centralise la récupération, le filtrage et la restitution des statistiques globales de la ferme : les flux financiers (revenus et dépenses), le suivi des stocks de produits, les performances analytiques des agents sur le terrain et la traçabilité des rapports journaliers des superviseurs.

---

## ⚙️ Architecture Technique & Client API

Le fichier `services.py` encapsule la logique d'interconnexion HTTP avec l'API Django via la bibliothèque `requests`.

```text
+-----------------------+      Requetes HTTP (GET)      +--------------------+
|  app_analyse_champs   | ----------------------------> |  API REST Distante |
|  (Client Analytique)  | <---------------------------- |    (Source DAMS)   |
+-----------------------+         Reponses JSON         +--------------------+

```

### Protection & Consommation Centrale (`fetch_json`)

Toutes les requêtes sortantes transitent par une fonction utilitaire centrale dotée de dispositifs de résilience :

* **Timeout de sécurité** : Un mécanisme de protection strict de `10 secondes` est configuré sur le protocole HTTP afin d'éviter le blocage indéfini des threads applicatifs en cas de latence réseau.
* **Gestion des erreurs** : L'appel systématique à `response.raise_for_status()` lève une exception immédiate en cas de code erreur serveur ($4xx$ ou $5xx$), sécurisant l'intégrité des structures de données attendues.

---

## 🔍 Moteur de Filtrage Transversal (`build_filters`)

Afin d'uniformiser l'expérience de navigation et d'analyse, l'application intègre un extracteur de paramètres HTTP polymorphe nommé `build_filters(request)`. Ce composant intercepte les variables d'analyse de l'URL pour générer un dictionnaire standardisé destiné aux payloads de l'API :

* `period` : Segmentation rapide (ex: mensuelle, hebdomadaire, journalière).
* `date_from` : Borne chronologique inférieure.
* `date_to` : Borne chronologique supérieure.

---

## 🗂️ Matrice des Endpoints API & Endpoints Vues

### 1. Module Tableau de Bord (`Dashboard`)

Centralise les indicateurs de performance clés (KPI), les agrégats de revenus et les courbes de dépenses de la ferme.

* **Fonction Client** : `get_dashboard(params=None)` ➔ Appelle `GET /api/dashboard/`
* **Contrôleur Vue** : `dashboard_view(request)` ➔ Restitue `finance_champs/dashboard.html`.

### 2. Module Opérations Financières (`Operations`)

Assure l'audit et l'historisation détaillée des flux monétaires et des mouvements de stocks.

* **Fonctions Client** :
* `get_operations(params=None)` ➔ Appelle `GET /api/operations/` (Filtre par type de flux et catégorie).
* `get_operation_detail(pk)` ➔ Appelle `GET /api/operations/{pk}/`
* `get_engagement_detail(engagement_id)` ➔ Appelle `GET /api/engagements/{id}/` — **nouveau
  (06/08/2026)**, authentifié `X-Api-Key` (app `engagements`, voir § Exception au principe
  GET-only ci-dessous).


* **Contrôleurs Vues** :
* `operation_list_view(request)` : Injecte le catalogue complet des catégories récupérées via
  `get_categories()` pour filtrer dynamiquement le listing dans `finance_champs/operations/list.html`.
  **KPIs (06/08/2026)** : appelle aussi `get_dashboard(params)` avec les mêmes filtres de période
  (`period`/`date_from`/`date_to`, sans `type`/`categorie` — non supportés par `/api/dashboard/`)
  pour afficher les totaux Revenus/Dépenses en haut de page, cohérents avec le filtre actif.
  **Filtre de période (06/08/2026)** : réduit à trois options (`today`/`week`/`custom`), `today`
  présélectionné par défaut au premier chargement (y compris côté requête, pas seulement visuel —
  voir le bloc dédié dans la vue). L'option `custom` révèle deux champs `date_from`/`date_to`
  (JS, même pattern que `direction/factures/liste_versements.html`) ; `build_filters` ignore
  volontairement `period=custom` (valeur non reconnue par le `DateFilterMixin` de dams_agro), seuls
  `date_from`/`date_to` filtrent alors.
* `operation_detail_view(request, pk)` ➔ Restitue `finance_champs/operations/detail.html`.
  **Commentaire d'engagement (06/08/2026)** : si l'`Operation` a été générée automatiquement pour
  un engagement superviseur ↔ champ, son `note` (avance) ne contient qu'un message générique
  ("Généré automatiquement depuis l'engagement #N") — jamais le commentaire métier réel, qui
  n'existe que sur `EngagementFinancier.note`/`label` côté dams_agro. La vue repère l'id
  d'engagement dans `note` (cas avance) ou `label` (cas remboursement, `ENGAGEMENT_ID_PATTERN =
  re.compile(r'#(\d+)')`), appelle `get_engagement_detail` et affiche ce commentaire dans une
  carte dédiée mise en avant ("Commentaire de l'engagement") — best-effort, `DamsAgroAPIError` est
  avalée (`engagement = None`) sans casser l'affichage du reste de la page si dams_agro est
  injoignable ou si l'id n'est pas retrouvé.
* **Libellés nettoyés (06/08/2026)** : `operation.label` est passé au filtre `clean_engagement_label`
  (`direction/templatetags/direction_filters.py`, réutilisé tel quel — même pattern que
  `{% load direction_filters %}` déjà en place dans ces templates) dans la liste et le détail —
  retire un id technique parfois accolé en fin de libellé par dams_agro (référence superviseur ou
  pk d'engagement, jamais un besoin business pour la Direction).



### 3. Module Catalogue Produits (`Produits`)

Suivi analytique des productions issues de la ferme.

* **Fonctions Client** :
* `get_products(params=None)` ➔ Appelle `GET /api/produits/`
* `get_product_detail(pk)` ➔ Appelle `GET /api/produits/{pk}/`


* **Contrôleurs Vues** :
* `product_list_view(request)` ➔ Restitue `finance_champs/products/list.html`.
* `product_detail_view(request, pk)` ➔ Restitue `finance_champs/products/detail.html`.



### 4. Module Performance Terrain (`Agents`)

Analyse quantitative des volumes de ventes et des dotations rattachées aux agents.

* **Fonction Client** : `get_agents(params=None)` ➔ Appelle `GET /api/agents/`
* **Contrôleur Vue** : `agent_list_view(request)` ➔ Restitue `finance_champs/agents/list.html`.

### 5. Module Rapports Journaliers (`Rapports`)

Garantit la traçabilité de l'activité des encadrants de la ferme.

* **Fonctions Client** :
  * `get_superviseurs()` ➔ Appelle `GET /api/superviseurs/` — retourne un objet paginé `{count, results}` avec `id`, `first_name`, `last_name`, `phone_number`
  * `get_rapports(params=None)` ➔ Appelle `GET /api/rapports/` — filtre `period`, `date_from`, `date_to`, `superviseur`
  * `get_rapport_detail(pk)` ➔ Appelle `GET /api/rapports/{pk}/`

* **Contrôleurs Vues** :
  * `rapport_list_view(request)` : Alimente le select superviseur via `superviseurs['results']` dans `rapport_journalier/list.html`.
  * `rapport_detail_view(request, pk)` ➔ Restitue `rapport_journalier/detail.html`.

---

### 6. Module Cycles Agricoles (`Cultures`)

Visualisation lecture seule des fiches de culture saisies dans dams_agro.

* **Fonctions Client** :
  * `get_fiches(params=None)` ➔ Appelle `GET /api/cultures/` — filtre `period`, `date_from`, `date_to`, `annee`, `mois`
  * `get_fiche_detail(pk)` ➔ Appelle `GET /api/cultures/{pk}/` — prefetch passages + rapport + participations
  * `get_rapports_culture(params=None)` ➔ Appelle `GET /api/cultures/rapports/` — filtre `culture` (nom, icontains)
  * `get_connaissances()` ➔ Appelle `GET /api/cultures/connaissances/` — agrégat rendements + évaluations agents par culture

* **Contrôleurs Vues** :
  * `fiche_list_view(request)` ➔ `cultures_champs/list.html` — tableau avec badges `culture_nom` par fiche (depuis `fiche.besoins`), filtres année/mois/période. **Pas de filtre technicien** (une seule personne habilitée).
  * `fiche_detail_view(request, pk)` ➔ `cultures_champs/detail.html` — technicien en stat, intrants, rendements, bloc rapport de clôture (bilan + évaluation agents) conditionnel par besoin.
  * `rapports_culture_list_view(request)` ➔ `cultures_champs/rapports.html` — bilans de clôture avec filtre par nom de culture.
  * `connaissances_view(request)` ➔ `cultures_champs/connaissances.html` — moyennes rendements par culture tous cycles récoltés.

* **Ordre URL critique** : `cultures/rapports/` et `cultures/connaissances/` déclarés **avant** `cultures/<int:pk>/`.

---

## 7. Exception au principe GET-only : engagements superviseur ↔ champ

Contrairement à tous les modules ci-dessus, `creer_engagement_dams_agro` fait
un **POST** vers dams_agro (endpoint `/api/engagements/`, authentifié par
header `X-Api-Key` — `DAMS_DISTRIBUTION_API_KEY`, même nom de variable
d'environnement que côté dams_agro, secret partagé). C'est la **seule**
mutation déclenchée depuis ce repo vers dams_agro — toujours consommée par
`finance.services` (jamais appelée directement depuis une vue), qui ne fait
d'écriture locale (`Depense`) qu'après succès confirmé (stratégie
"remote-first"). Voir `finance/APP_FINANCE.md` § Engagements superviseur ↔
champ pour le détail métier.

**`rembourser_engagement_dams_agro` (POST `/api/engagements/{id}/remboursements/`)
a été supprimée le 06/08/2026** : le remboursement ne doit jamais être
initié depuis `dams` (décision mdmaiga — dispersion de responsabilité,
c'est dams_agro qui doit l'indiquer). `dams` ne fait donc plus aucun POST
vers cet endpoint — il reste consommable côté dams_agro (contrat inchangé,
`docs/api/dams_agro_engagements.md`), simplement plus jamais appelé d'ici.

`_post_json` (équivalent en écriture de `fetch_json`) ne laisse **jamais**
d'exception `requests` remonter brute : timeout, erreur réseau et erreur HTTP
sont toutes traduites en `DamsAgroAPIError`, journalisées (`logger.error`),
pour que l'appelant sache explicitement qu'aucune écriture locale ne doit
avoir lieu. Pas de retry automatique (aucune infra Celery/APScheduler dans ce
repo) — un échec doit être ressaisi manuellement par le superviseur.

**`get_engagements_champ_superviseur(reference_superviseur)`** — **nouveau
(sprint-06, Constat 1)** : seul GET de ce module authentifié `X-Api-Key`
(comme les POST ci-dessus) — les endpoints de l'app `engagements` sont
réservés à DAMS Distribution, jamais en session (contrat vérifié le
06/08/2026, `dams_champs/docs/api/api_structure.md`). Utilise `_request_engagements`
(équivalent en lecture de `_post_json`, même traduction d'erreurs vers
`DamsAgroAPIError`). **Ne pagine pas** : `GET /api/engagements/` renvoie une
liste JSON directe, pas `{count, results, next}` — contrairement au principe
général "PageNumberPagination" documenté côté dams_agro, l'app `engagements`
est bâtie sur des `APIView` bruts (`engagements/api_views.py`), pas des
`ListAPIView`. Vérifié sur le code source dams_agro le 06/08/2026 après une
`AttributeError` en usage réel causée par une première implémentation qui
supposait, à tort, la pagination générale. Consommé par
`finance.services.synchroniser_engagements_champ` — voir
`finance/APP_FINANCE.md`.

---

## 🧪 Points de Vigilance pour le Développement

* **`technicien` est un entier** dans `FicheCultureSerializer` (PK Django, pas un objet imbriqué). Ne pas accéder à `.first_name` ni `.last_name` depuis les templates cultures — afficher directement `{{ fiche.technicien }}`.
* **`rapport_culture` peut être `null`** — conditionner son affichage dans les templates (`{% if besoin.rapport_culture %}`).
* **Pagination** : les endpoints des apps `finance`/`rapports`/`cultures` retournent `{"count": N, "results": [...]}`. Utiliser `.results` dans les templates pour itérer. `categories/` et `connaissances/` retournent une liste directe (non paginée) — **tout comme l'app `engagements`** (`get_engagements_champ_superviseur`), bâtie sur des `APIView` bruts, pas des `ListAPIView` : ne pas supposer `{results: [...]}` sur ces endpoints malgré le principe général documenté côté dams_agro.
* **Variable d'environnement** : `API_URL` doit pointer sur la racine de dams_agro (ex : `http://localhost:8000`). Son absence lève une erreur d'URL malformée au démarrage.
* **Toute modification d'endpoint** dans dams_agro doit être répercutée dans `services.py` **et** dans ce fichier dans le même commit.
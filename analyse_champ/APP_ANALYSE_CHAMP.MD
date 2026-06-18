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


* **Contrôleurs Vues** :
* `operation_list_view(request)` : Injecte le catalogue complet des catégories récupérées via `get_categories()` pour filtrer dynamiquement le listing dans `finance_champs/operations/list.html`.
* `operation_detail_view(request, pk)` ➔ Restitue `finance_champs/operations/detail.html`.



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
* `get_superviseurs()` ➔ Appelle `GET /api/superviseurs/`
* `get_rapports(params=None)` ➔ Appelle `GET /api/rapports/`
* `get_rapport_detail(pk)` ➔ Appelle `GET /api/rapports/{pk}/`


* **Contrôleurs Vues** :
* `rapport_list_view(request)` : Récupère la liste des rapports filtrés et extrait la clé `results` du dictionnaire renvoyé par le endpoint des superviseurs pour alimenter les listes de sélection de `rapport_journalier/list.html`.
* `rapport_detail_view(request, pk)` ➔ Restitue `rapport_journalier/detail.html`.



---

## 🧪 Points de Vigilance pour le Développement

* **Variables d'environnement** : Assurez-vous que la variable globale `API_URL` est correctement renseignée dans votre conteneur Docker ou votre fichier `.env` local. Une absence de cette variable lèvera une erreur d'URL malformée dès l'initialisation de `BASE_URL`.
* **Format des Données de Listes** : L'accès aux listes dans l'API REST utilise parfois une structure paginée. C'est le cas du endpoint `superviseurs/` qui nécessite l'extraction explicite du dictionnaire `['results']` au niveau de la vue (contrairement à `categories/` ou `operations/` qui retournent des listes directes). Veillez à respecter cette structure lors d'éventuels changements du format de sérialisation côté serveur.
* **Gestion des exceptions réseau** : Bien que `raise_for_status()` empêche l'application d'afficher des données corrompues en cas de panne de l'API, il est recommandé d'implémenter à l'avenir un bloc `try/except MaxRetryError` ou `Timeout` pour rediriger proprement l'utilisateur vers une page d'erreur maintenable en production.
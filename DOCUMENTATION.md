# Documentation du Projet DAMS

## Introduction

“Un système intégré de gouvernance des flux opérationnels et financiers basé sur la traçabilité des données terrain.”

DAMS est une application modulaire conçue pour orchestrer, tracer et auditer les opérations liées aux agents, aux stocks, aux ventes, aux salaires, et au pilotage de l'activité agricole. Le projet est structuré de manière découplée pour isoler les logiques de saisie opérationnelle, de surveillance réglementaire et de consommation d'APIs tierces.

---

## Structure du Projet

Le projet est organisé en plusieurs applications (modules) principales :

### 1. **agents/**

* Gère le cycle de vie opérationnel, les affectations et le suivi terrain direct des agents.
* **Services** : Gestion des tableaux de bord agents, données d'activité et suivi des stocks attribués.
* **Templates** : Interfaces utilisateur dédiées aux saisies et profils agents.

### 2. **core/**

* Noyau centralisé de l'application contenant les configurations globales et les définitions de modèles partagés (`Produit`, `Agent`, `LotEntrepot`).
* **Migrations** : Gestion de l'historique et des versions de la base de données PostgreSQL.
* **Services** : Moteurs de validation et d'analyse des données structurelles.

### 3. **direction/**

* Dédié à la gouvernance globale, à la consolidation financière et à l'aide à la décision pour le management.
* **Exports** : Moteurs d'édition et de compilation des rapports aux formats PDF et Word.
* **Services** : Analyseurs financiers complexes, tableaux de bord de synthèse et rapports de ventes consolidés.

### 4. **paie/**

* Automatisation et gestion comptable du personnel terrain et administratif.
* **Services** : Algorithmes de calcul des rémunérations, génération, historisation et flux de validation des fiches de paie.
* **Templates** : Interfaces d'édition, de consultation et de validation des bulletins.

### 5. **analyse_champs/** 

* Module analytique découplé agissant en tant que client HTTP pour interroger une API REST distante (définie via la variable d'environnement `API_URL`).
* **Services** : Client de consommation synchrone (`fetch_json` doté d'un timeout de sécurité de 10s) pour centraliser les indicateurs de la ferme (flux financiers, stocks produits, rapports des superviseurs).
* **Templates** : Restitution des données distantes sous forme de grilles et de vues de détail administratives modernes.

### 6. **surveillance/** 

* Tour de contrôle et d'audit réglementaire du SI (Gouvernance des prix et détection d'anomalies).
* **Services** : Moteurs de calcul de variations temporelles (semaines/mois), d'identification des ventes à perte (alertes "ventes rouges"), et d'évaluation de la performance des gestionnaires d'entrepôts.
* **Templates** : Tableaux de bord de contrôle orientés direction, fiches d'audit de lots de stockage et fiches profils analytiques.

### 7. **utils/**, **static/** & **templates/**

* `utils/` : Fonctions d'infrastructure transverses (envoi de mails, formatages, etc.).
* `static/` : Assets CSS (Tailwind / DaisyUI), JavaScript (HTMX) et images.
* `templates/` : Squelettes HTML globaux et composants d'interface partagés (Layouts, modales, barres de navigation).

---

## Fonctionnalités Principales

### 1. Gestion des Agents & Suivi Terrain

* Enrôlement, gestion des profils et affectations structurelles des collaborateurs.
* Traçabilité fine des mouvements et dotations de stocks attribués à chaque agent.

### 2. Gestion des Stocks & Lots

* Suivi en temps réel des stocks au sein des entrepôts centraux et des dépôts secondaires.
* Traçabilité ascendante et descendante des lots (modèle `LotEntrepot`), de leur réception à leur distribution finale.

### 3. Moteur de Vente & Évaluation Commerciale

* Enregistrement continu des ventes terrain.
* Analyse quantitative et qualitative des volumes écoulés par canal et par produit.

### 4. Automatisation de la Paie

* Calcul automatisé des salaires fixes et variables basé sur la performance réelle issue des données terrain.
* Cycle complet de validation administrative des états de salaire.

### 5. Pilotage Analytique Découplé (`analyse_champs`)

* Extraction dynamique des paramètres de filtrage temporel (`period`, `date_from`, `date_to`).
* Synchronisation continue avec l'API de la ferme pour restituer l'état du dashboard financier, du catalogue produits et des rapports journaliers soumis par les superviseurs.

### 6. Audit & Gestion des Risques Commerciales (`surveillance`)

* Système d'alerte précoce sur les transactions anormales (alertes de ventes sous le prix de revient).
* Analyse comparative des performances volumétriques (Calcul des variations de Kg vendus d'une semaine/mois à l'autre).

---

## Technologies Utilisées

* **Langage** : Python 3.10+
* **Framework Backend** : Django & Django REST Framework (DRF)
* **Librairies Clés** : `requests` (Client API), `django-modeltranslation` (Multi-langue)
* **Base de Données** : PostgreSQL (Production) / Moteur conforme SQL
* **Frontend Écosystème** : HTML5, Tailwind CSS / DaisyUI, HTMX (Approche SPA-like sans la complexité de frameworks JS lourds)

---

## Installation et Configuration

### Prérequis

* Python 3.10 ou supérieur
* Base de données PostgreSQL active
* Configuration des variables d'environnement (notamment `API_URL` pour le module `analyse_champs`)

### Étapes d'installation

1. Cloner le dépôt :
```bash
git clone <url-du-repo>
cd DAMS

```


2. Installer les dépendances requises :
```bash
pip install -r requirements.txt

```


3. Configurer l'environnement (Fichier `.env`) :
```env
DEBUG=True
SECRET_KEY=votre_cle_secrete
DATABASE_URL=postgres://user:password@localhost:5432/dams_db
API_URL=https://api.ferme.dams.local

```


4. Appliquer les migrations de structure de base de données :
```bash
python manage.py migrate

```


5. Lancer le serveur de développement local :
```bash
python manage.py runserver

```



---

## Structure des Dossiers Mis à Jour

```
DAMS/
├── agents/             # Gestion opérationnelle des agents
├── analyse_champs/     # Client d'intégration et d'analyse API externe
├── core/               # Modèles de données centraux et configurations
├── direction/          # Rapports financiers haut niveau et exports
├── paie/               # Calcul et validation des rémunérations
├── surveillance/       # Tour de contrôle, audit des prix et KPI périodiques
├── static/             # Fichiers statiques globaux (CSS, JS, media)
├── templates/          # Gabarits HTML partagés
├── utils/              # Fonctions d'aide et utilitaires communs
├── manage.py           # CLI Django
└── requirements.txt    # Dépendances Python du projet

```

---

## Points de Vigilance pour le Développement & la Maintenance

1. **Couplage et Dépendance `core**` : L'application `surveillance` effectue des requêtes directes et des jointures logiques sur les modèles `Agent`, `Produit` et `LotEntrepot` hébergés dans `core/`. Toute modification de schéma sur ces tables doit impérativement faire l'objet de tests de non-régression sur les vues de surveillance.
2. **Gestion des structures paginées de l'API** : Lors de la consommation de endpoints distants dans `analyse_champs`, veillez à analyser la structure du payload JSON. Certains endpoints (comme `superviseurs/`) encapsulent leurs listes dans une clé standard de pagination (`['results']`), contrairement à d'autres flux qui retournent des tableaux bruts.
3. **Consommation Mémoire SQL (Slicing)** : Pour assurer la scalabilité sur PostgreSQL face à un volume important de données terrain, les limitations d'affichage (ex: l'extraction du top 10 des ventes rouges ou le top 5 des superviseurs de `surveillance`) doivent être optimisées au niveau de l'ORM (utilisation de `.only()`, `select_related()` et slicing QuerySet direct) plutôt que par manipulation de listes Python en mémoire native.

---

## Sauvegarde et Restauration

* Les sauvegardes de la base de données de production sont stockées de façon sécurisée dans le dossier `backup/`.
* Pour restaurer un état de base de données lors des phases de tests :
```bash
python manage.py dbrestore <nom-du-fichier-backup>

```



---

## Licence

Ce projet est une propriété interne / Sous licence fermée à usage exclusif (Se référer au fichier `LICENSE` pour les conditions de distribution).
# Documentation du Projet DAMS

## Introduction
“Un système intégré de gouvernance des flux opérationnels et financiers basé sur la traçabilité des données terrain
DAMS est une application conçue pour gérer les opérations liées aux agents, aux stocks, aux ventes, aux salaires et aux rapports analytiques. Ce projet est structuré en plusieurs modules pour répondre aux besoins spécifiques de gestion et d'analyse.

---

## Structure du Projet
Le projet est organisé en plusieurs dossiers principaux :

### 1. **agents/**
- Contient les fonctionnalités liées à la gestion des agents.
- **Services** : Fournit des services pour les tableaux de bord, les données des agents, et les stocks.
- **Templates** : Contient les fichiers HTML pour les interfaces utilisateur des agents.

### 2. **core/**
- Contient les fichiers principaux et les configurations de base du projet.
- **Migrations** : Gère les modifications de la base de données.
- **Services** : Fournit des services pour l'analyse et la gestion des données principales.

### 3. **direction/**
- Gère les fonctionnalités liées à la direction, comme les rapports et les analyses financières.
- **Exports** : Génère des rapports PDF et Word.
- **Services** : Fournit des services pour les analyses financières, les tableaux de bord, et les rapports de ventes.

### 4. **paie/**
- Gère les fonctionnalités liées aux salaires.
- **Services** : Fournit des services pour le calcul, la génération et la validation des salaires.
- **Templates** : Contient les fichiers HTML pour les interfaces utilisateur liées à la paie.

### 5. **utils/**
- Contient des utilitaires communs comme les fonctions d'envoi d'e-mails et de génération de rapports.

### 6. **static/**
- Contient les fichiers statiques comme les fichiers CSS et JavaScript.

### 7. **templates/**
- Contient les fichiers HTML globaux utilisés dans tout le projet.

---

## Fonctionnalités Principales

### 1. Gestion des Agents
- Création, modification et suppression des agents.
- Gestion des affectations et des stocks des agents.

### 2. Gestion des Stocks
- Suivi des stocks dans les entrepôts et les dépôts.
- Distribution des lots aux agents.

### 3. Gestion des Ventes
- Suivi des ventes réalisées par les agents.
- Génération de rapports de ventes.

### 4. Gestion des Salaires
- Calcul automatique des salaires des agents.
- Génération et validation des fiches de paie.

### 5. Rapports et Analyses
- Génération de rapports financiers et opérationnels.
- Analyse des performances des agents et des superviseurs.

---

## Technologies Utilisées
- **Langage** : Python
- **Framework** : Django
- **Base de Données** :  / prod POSTGRESQL
- **Frontend** : HTML, CSS, JavaScript

---

## Installation et Configuration

### Prérequis
- Python 3.10 ou supérieur
- Pip (gestionnaire de paquets Python)

### Étapes d'installation
1. Cloner le dépôt :
   ```bash
   git clone <url-du-repo>
   ```
2. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Appliquer les migrations :
   ```bash
   python manage.py migrate
   ```
4. Lancer le serveur de développement :
   ```bash
   python manage.py runserver
   ```

---

## Structure des Dossiers

### Exemple de Structure
```
DAMS/
├── agents/
├── core/
├── direction/
├── paie/
├── static/
├── templates/
├── utils/
├── manage.py
├── requirements.txt
```

---

## Contribution

### Règles de Contribution
1. Créer une branche pour chaque fonctionnalité ou correction de bug.
2. Soumettre une pull request avec une description claire des modifications.

### Contact
Pour toute question ou suggestion, veuillez contacter l'équipe de développement.

---

## Sauvegarde et Restauration
- Les sauvegardes de la base de données sont stockées dans le dossier `backup/`.
- Pour restaurer une sauvegarde, utiliser la commande suivante :
  ```bash
  python manage.py dbrestore <nom-du-fichier>
  ```

---

## Licence
Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.
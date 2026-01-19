# Documentation du Projet DAMS

## 1. Résumé du Projet
Le projet DAMS est une application web développée avec le framework Django. Elle est conçue pour gérer les stocks, les ventes, les fournisseurs, les agents et les analyses de performance. L'objectif principal est de fournir une solution centralisée pour les opérations commerciales et logistiques.

## 2. Architecture Technique
L'application est construite sur une architecture MVC (Modèle-Vue-Contrôleur) propre à Django. Voici les principaux composants :

- **Modèles (Models)** : Représentent les données et leur logique métier.
- **Vues (Views)** : Contiennent la logique de présentation et les réponses HTTP.
- **Templates** : Fichiers HTML pour le rendu des pages.
- **Services** : Contiennent la logique métier complexe pour des fonctionnalités spécifiques.
- **Commandes de gestion** : Scripts personnalisés pour des tâches administratives.

### Technologies Utilisées
- **Backend** : Django 5.2.6
- **Base de données** : SQLite (par défaut, mais peut être configurée pour PostgreSQL).
- **Frontend** : HTML, CSS, JavaScript.
- **Autres** : Django REST Framework pour les APIs.

## 3. Installation et Configuration

### Prérequis
- Python 3.10 ou supérieur
- Pipenv ou virtualenv pour la gestion des environnements virtuels
- SQLite (installé par défaut avec Python)

### Étapes d'installation
1. Clonez le dépôt :
   ```bash
   git clone <url-du-repo>
   cd dams
   ```
2. Créez un environnement virtuel et activez-le :
   ```bash
   python -m venv env
   source env/bin/activate # Sur Windows : env\Scripts\activate
   ```
3. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
4. Appliquez les migrations :
   ```bash
   python manage.py migrate
   ```
5. Lancez le serveur de développement :
   ```bash
   python manage.py runserver
   ```

## 4. Explication des Dossiers et Fichiers

- **core/** : Contient les fonctionnalités principales de l'application.
  - `models.py` : Définit les modèles de données.
  - `views.py` : Contient les vues pour gérer les requêtes HTTP.
  - `services/` : Logique métier complexe.
  - `templates/` : Fichiers HTML pour le rendu des pages.
- **dams/** : Configuration principale du projet.
  - `settings.py` : Configuration globale de l'application.
  - `urls.py` : Routes principales de l'application.
- **media/** : Stocke les fichiers téléchargés par les utilisateurs.
- **staticfiles/** : Contient les fichiers statiques (CSS, JS, images).

## 5. Description des APIs / Endpoints

### Exemple d'API
- **Endpoint** : `/api/lots-disponibles/`
  - **Méthode** : GET
  - **Description** : Retourne les lots disponibles pour un produit donné.
  - **Paramètres** :
    - `produit_id` : ID du produit (obligatoire).
  - **Réponse** :
    ```json
    {
      "id": 1,
      "reference_lot": "LOT123",
      "quantite_restante": 50
    }
    ```

## 6. Scénarios d’Usage

### Gestion des Stocks
1. Un agent se connecte à l'application.
2. Il consulte les lots disponibles dans l'entrepôt.
3. Il met à jour les quantités après une distribution.

### Analyse des Performances
1. Un superviseur accède au tableau de bord.
2. Il visualise les KPI globaux et les performances des agents.
3. Il génère un rapport pour une période donnée.

## 7. Instructions de Déploiement

1. Configurez une base de données PostgreSQL et mettez à jour `settings.py` :
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql',
           'NAME': 'nom_de_la_base',
           'USER': 'utilisateur',
           'PASSWORD': 'mot_de_passe',
           'HOST': 'localhost',
           'PORT': '5432',
       }
   }
   ```
2. Collectez les fichiers statiques :
   ```bash
   python manage.py collectstatic
   ```
3. Configurez un serveur WSGI (ex. Gunicorn) et un serveur web (ex. Nginx).
4. Démarrez l'application en mode production.

## 8. Bonnes Pratiques ou Limites

### Bonnes Pratiques
- Utilisez des environnements virtuels pour isoler les dépendances.
- Activez le mode DEBUG=False en production.
- Sauvegardez régulièrement la base de données.

### Limites
- L'application utilise SQLite par défaut, ce qui n'est pas adapté pour les environnements de production à grande échelle.
- Certaines fonctionnalités avancées nécessitent une configuration supplémentaire (ex. envoi d'e-mails).

---

Pour toute question ou contribution, veuillez consulter le fichier README ou contacter l'équipe de développement.
# DAMS



## Résumé
DAMS est une application web conçue pour gérer les stocks, les ventes, les fournisseurs, les agents et les analyses de performance. Elle offre une solution centralisée pour les opérations commerciales et logistiques.

## Stack Technique
- **Langage** : Python 3.10+
- **Framework** : Django 5.2.6
- **Base de données** : SQLite (par défaut) ou PostgreSQL
- **Frontend** : HTML, CSS, JavaScript
- **Outils supplémentaires** : Django REST Framework

## Installation

### Prérequis
- Python 3.10 ou supérieur
- Git
- Un environnement virtuel (Pipenv ou virtualenv recommandé)

### Étapes
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

## Configuration

- **Base de données** :
  Par défaut, l'application utilise SQLite. Pour utiliser PostgreSQL, modifiez `settings.py` :
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

- **Fichiers statiques** :
  Collectez les fichiers statiques avant le déploiement :
  ```bash
  python manage.py collectstatic
  ```

## Commandes Importantes

- Lancer le serveur de développement :
  ```bash
  python manage.py runserver
  ```
- Appliquer les migrations :
  ```bash
  python manage.py migrate
  ```
- Créer un superutilisateur :
  ```bash
  python manage.py createsuperuser
  ```

## Exemples d’Utilisation

### Gestion des Stocks
1. Connectez-vous en tant qu'agent.
2. Consultez les lots disponibles dans l'entrepôt.
3. Mettez à jour les quantités après une distribution.

### Analyse des Performances
1. Accédez au tableau de bord.
2. Visualisez les KPI globaux et les performances des agents.
3. Générez un rapport pour une période donnée.

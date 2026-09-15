#!/usr/bin/env bash
# Déploiement production DAMS (web41 / c2679735c).
#
# Reprend les 4 étapes manuelles répétées à chaque déploiement :
#   1. fetch + reset --hard sur origin/main (écrase tout changement local
#      non commité dans le clone de prod — normal pour ce repo, à ne pas
#      lancer si des changements manuels y ont été faits entre-temps) ;
#   2. makemigrations --merge (résout les branches de migration divergentes,
#      --noinput répond "y" automatiquement comme fait manuellement) ;
#   3. migrate ;
#   4. collectstatic (--noinput répond "yes" automatiquement).
#
# Usage : ./scripts/deploy.sh

set -euo pipefail

VENV_ACTIVATE="/home/c2679735c/virtualenv/dams_v4/3.12/bin/activate"
PROJECT_DIR="/home/c2679735c/dams_v4"

echo "==> Activation de l'environnement virtuel"
source "$VENV_ACTIVATE"

echo "==> cd $PROJECT_DIR"
cd "$PROJECT_DIR"

echo "==> git fetch + reset --hard origin/main"
git fetch origin
git reset --hard origin/main

echo "==> makemigrations --merge"
python manage.py makemigrations --merge --noinput

echo "==> migrate"
python manage.py migrate

echo "==> collectstatic"
python manage.py collectstatic --noinput

echo "==> Déploiement terminé ($(git rev-parse --short HEAD))"

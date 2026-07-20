FROM python:3.12-slim

# uv : résolveur/installeur parallélisé, bien plus rapide que pip sur ce réseau.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install uv

# Versions alignées sur celles installées en Sprint 1 (venv local) — pas de dérive
# silencieuse entre l'environnement conteneurisé et l'environnement de référence.
# Cache mount : persiste entre builds (hors image finale) pour éviter de retélécharger
# les wheels à chaque rebuild.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system dbt-core==1.12.* dbt-postgres==1.11.*

WORKDIR /usr/app/dbt
COPY dbt/ .

ENV DBT_PROFILES_DIR=/usr/app/dbt

ENTRYPOINT ["dbt"]

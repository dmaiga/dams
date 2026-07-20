# dbt — DAMS BI

Projet dbt Core ciblant le schéma `bi_` d'une base PostgreSQL contenant une copie de `public.core_*` (DAMS prod).

## Setup avec Docker (recommandé — ADR-008)

Postgres + dbt (+ Metabase, scaffold Sprint 2) tournent en conteneurs. Le dump `input/dams_2026-07-12.dump`
est restauré **une seule fois**, au premier démarrage du volume Postgres (comportement natif de l'image
officielle : les scripts de `docker/postgres/init/` ne s'exécutent que si le volume est vide).

```bash
# Depuis la racine du repo
cp .env.example .env   # renseigner les vraies valeurs
docker compose up -d postgres
docker compose ps      # attendre "healthy"
docker compose run --rm dbt debug
docker compose run --rm dbt deps
docker compose run --rm dbt build
```

Pour relancer un modèle après modification (le dossier `dbt/` est monté en volume, pas besoin de rebuild l'image) :
```bash
docker compose run --rm dbt run --select fct_ventes
```

Pour repartir d'une base vierge (re-déclenche la restauration du dump) :
```bash
docker compose down -v   # supprime le volume pgdata
docker compose up -d postgres
```

> Note (juillet 2026) : Docker Desktop sur Windows s'est montré instable dans cet environnement de
> développement. Le projet a été copié dans WSL2 (Docker natif installé côté Linux) pour contourner
> le problème — voir `chef_projet/RISQUES.md` (R16).
>
> Suite (17/07/2026) : même côté WSL2, le build de l'image `dbt` custom (`uv pip install dbt-core
> dbt-postgres`) s'est bloqué plus d'1h sans converger (probable souci réseau WSL2, pas un problème
> Docker Desktop). En attendant un diagnostic, **Metabase est installé nativement sur Windows**
> (jar OSS + Java local, `java -jar metabase.jar`) et pointé sur le PostgreSQL local (fallback
> "Setup sans Docker" ci-dessous) — ce chemin ne dépend d'aucun conteneur. Le service `dbt` et
> `postgres` en conteneur restent la cible pour un futur déploiement serveur (ADR-008), pas
> abandonnés, juste repoussés.

## Setup sans Docker (fallback local)

1. Créer un venv Python à la racine du repo : `python -m venv .venv`
2. `.venv/Scripts/pip install dbt-core dbt-postgres` (versions figées par `require-dbt-version` dans `dbt_project.yml`)
3. Copier `.env.example` → `.env` à la racine du repo, renseigner les vraies valeurs (jamais commitées)
4. Restaurer une copie de la base source dans PostgreSQL local :
   ```bash
   createdb dams_dev
   pg_restore --no-owner -d dams_dev input/dams_2026-07-12.dump
   ```
5. Depuis la racine du repo, charger les variables d'env, pointer `dbt` vers le profil local au repo, puis valider :
   ```bash
   set -a && source .env && set +a
   export DBT_PROFILES_DIR="$(pwd)/dbt"
   cd dbt
   dbt debug
   dbt deps
   dbt build
   ```

`dbt/profiles.yml` est versionné dans le repo (pas de credentials en dur, tout via `env_var()`) — un seul
fichier de profil pour le chemin Docker et le chemin local, plus besoin de toucher `~/.dbt/profiles.yml`.

## Commandes courantes

```bash
dbt build                 # run + test complet
dbt run --select staging  # uniquement les modèles staging
dbt test                  # uniquement les tests
dbt docs generate && dbt docs serve
```
(Préfixer de `docker compose run --rm` si vous êtes sur le chemin Docker.)

## Conventions

- **Staging** (`models/staging/`) : 1:1 avec la source, cast uniquement, pas de logique métier. Filtre `est_supprime = false` où la colonne existe.
- **Marts** (`models/marts/`) : dimensions (`dim_*`) et faits (`fct_*`). Toute jointure multi-hop ou dérivation métier vit ici, jamais en staging.
- **Schéma unique `bi_`** pour tout (staging + marts) — voir `macros/generate_schema_name.sql`.
- Écarts connus entre le modèle documenté et le comportement réel de DAMS : voir `../architecte/REFERENCE_TECHNIQUE_BI.md` et `../chef_projet/RISQUES.md` (R9–R14).

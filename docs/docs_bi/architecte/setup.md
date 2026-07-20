# Setup — Accès base et rôles PostgreSQL (app `bi`)

**Date** : 20 juillet 2026
**Contexte** : PostgreSQL unique (pas de réplica), schéma analytique `bi_` isolé du schéma
applicatif `public` (ADR-005). L'app Django `bi` lit les vues `bi_.vw_*` (managed=False) ET
écrit une table applicative, `bi_ajustementprixachat` (managed=True, schéma `public`, comme
toutes les autres tables Django du projet) — voir `bi/models.py`.

---

## 1. Pourquoi pas de router Django (`bi_reader`)

`DATABASES` reste une connexion unique `'default'` (`dams/settings.py`), partagée par toutes
les apps du projet, y compris `bi`. Un router aurait imposé une deuxième connexion (second
jeu de credentials, second pool) pour un seul modèle managé (`AjustementPrixAchat`) — sans
second serveur PostgreSQL réel derrière (une seule instance, cf. `CLAUDE.md`). Le rôle
`bi_reader` défini ci-dessous existe **côté PostgreSQL**, pas côté Django : il est prévu pour
un usage externe futur (client SQL ad hoc, analyste, futur outil de reporting) qui n'a besoin
que de lire `bi_`, jamais pour la connexion Django elle-même.

## 2. Rôles PostgreSQL

### `dbt_user` — exécute `dbt run`/`dbt build`

Doit pouvoir **lire** toutes les tables sources `core_*` (schéma `public`) et la table
`bi_ajustementprixachat` (nouvelle source dbt-2, schéma `public`), et avoir **plein contrôle**
sur le schéma `bi_` (créer/remplacer les vues à chaque run).

```sql
-- Lecture des tables sources DAMS (schéma public, core_*) + table ajustements (app bi)
GRANT USAGE ON SCHEMA public TO dbt_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO dbt_user;

-- Plein contrôle sur le schéma bi_ (créer/remplacer vues, tests dbt)
GRANT ALL ON SCHEMA bi_ TO dbt_user;
GRANT ALL ON ALL TABLES IN SCHEMA bi_ TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA bi_ GRANT ALL ON TABLES TO dbt_user;
```

### `bi_reader` — lecture seule externe du schéma `bi_`

Aucun accès à `public` (donc aucun accès aux données brutes DAMS, ni à la table
`bi_ajustementprixachat` en écriture). Réservé à une consultation SQL directe hors app Django
(pas utilisé par le code de ce sprint, provisionné pour un besoin futur).

```sql
CREATE ROLE bi_reader LOGIN PASSWORD '<à définir>';
GRANT USAGE ON SCHEMA bi_ TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA bi_ TO bi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA bi_ GRANT SELECT ON TABLES TO bi_reader;
```

### `DB_USER` (rôle applicatif Django existant, `dams/settings.py` → `DATABASES['default']`)

Déjà propriétaire/lecteur-écrivain de `public` (toutes les apps DAMS, y compris la nouvelle
table `bi_ajustementprixachat` créée par la migration `bi.0001_initial`). Ajout nécessaire
pour que l'app `bi` puisse lire les vues :

```sql
GRANT USAGE ON SCHEMA bi_ TO "<DB_USER>";
GRANT SELECT ON ALL TABLES IN SCHEMA bi_ TO "<DB_USER>";
ALTER DEFAULT PRIVILEGES IN SCHEMA bi_ GRANT SELECT ON TABLES TO "<DB_USER>";
```

## 3. Ordre de mise en route

1. **Rôles** — exécuter les `GRANT` ci-dessus (schéma `bi_` déjà créé par le premier
   `dbt run`, cf. ADR-005 ; si c'est la toute première mise en route, créer le schéma
   d'abord : `CREATE SCHEMA IF NOT EXISTS bi_;`).
2. **Migrations Django** — `python manage.py migrate bi` : crée `bi_ajustementprixachat`
   dans `public` (seule migration de l'app, cf. `bi/migrations/0001_initial.py`). Doit
   précéder l'étape 3 car `stg_ajustements_prix_achat` (dbt) déclare cette table comme
   source et échoue si elle n'existe pas encore.
3. **`dbt run`** (ou `dbt build`) — matérialise/rafraîchit les vues `bi_.vw_*`, y compris
   `vw_marge_fournisseur` qui dépend de `bi_ajustementprixachat` (étape 2).
4. **App Django (`bi`)** — les vues `managed=False` (`bi/models.py`) sont maintenant
   lisibles ; les dashboards peuvent être consultés.

Reproduire cet ordre à chaque changement de schéma (nouvel environnement, restauration d'un
dump) — l'inverser (dbt avant les migrations) fait échouer `dbt run` sur la source manquante.

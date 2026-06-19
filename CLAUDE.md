# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DAMS**  is a Django 4.2 web application for managing agricultural distribution operations — inventory reception, agent distribution, field sales, debt collection, supplier payments, and payroll. All interfaces are in French.

## Common Commands

```bash
# Development server
python manage.py runserver

# Database
python manage.py migrate
python manage.py makemigrations

# Create superuser
python manage.py createsuperuser

# Collect static files (production)
python manage.py collectstatic

# Run tests
python manage.py test [app_name]
```

### Key Custom Management Commands

```bash
# Core
python manage.py calculer_bonus
python manage.py normalize_lots_to_kg
python manage.py desactiver_stagiaires_expires

# Direction
python manage.py cloturer_mois
python manage.py rapport_vente
python manage.py init_regles_remuneration
python manage.py reset_dev_data
```

## Architecture

### Django Apps

| App | Role |
|-----|------|
| **core** | Central models, authentication, stock reception, sales, debt, collections, payments |
| **agents** | Dashboards for supervisors, field agents (mamies), ROT, trainees |
| **direction** | Executive dashboards, financial analysis, monthly closing, payroll |
| **paie** | Payroll generation, salary rules, Excel export |
| **surveillance** | Audit/monitoring: price anomalies, volume tracking, supervisor performance |
| **analyse_champ** | HTTP client consuming an external farm analytics API (`API_URL` env var) |
| **mobile** | Minimal mobile URL routing |
| **utils** | Shared helpers (email, formatting) |

### URL Structure

- `/` → core (login, all operational workflows)
- `/direction/` → direction app
- `/agents/` → agents app
- `/paie/` → paie app
- `/champs/` → analyse_champ (external API proxy)
- `/surveillance/` → surveillance app
- `/app/` → mobile app

### Frontend Stack

- **Tailwind CSS + DaisyUI** for UI components
- **HTMX** for dynamic interactions without a JS framework
- **Django Templates** as the rendering engine
- **TinyMCE** for HTML-rich fields (descriptions, notes)

### Authentication

Two backends configured in `AUTHENTICATION_BACKENDS`:
1. Standard Django (`ModelBackend`) — username/password
2. Custom `TelephoneBackend` (in `core/backends.py`) — phone number login used by field agents

`LOGIN_URL`, `LOGIN_REDIRECT_URL`, and `LOGOUT_REDIRECT_URL` all point to `'login'`.

## Key Models & Data Flow

Stock flows top-down through these models:

```
Fournisseur → LotEntrepot → AffectationLotSuperviseur
  → DistributionAgent / DetailDistribution
    → Vente → Dette (if credit)
      → Recouvrement → RecouvrementSuperviseur
        → VersementBancaire + Depense
          → ClotureMensuelle
```

### Agent Roles (`Agent.type_agent`)

`direction` | `rot` | `entrepot` (supervisor) | `terrain` (field/mami) | `agent_gros` (wholesale) | `agent_polivalent` | `stagiaire` (auto-expires 14 days) | `gestionnaire_stock`

### Critical Model Behaviors

- **Soft deletes**: `Vente`, `PaiementFournisseur`, `DistributionAgent` use `est_supprime=True` — never hard-delete these.
- **Stagiaire expiry**: Checked by `desactiver_stagiaires_expires` management command.
- **Distribution atomicity**: `distribution_superviseur` views use `transaction.atomic()`.
- **`LotEntrepot.valeur_stock_initiale`**: Calculated and persisted on save; `quantite_restante` must not exceed `quantite_initiale`.
- **`PaiementFournisseur`**: Field `superviseur` is deprecated — use `effectue_par` (ROT actor).
- **Monthly closing (`ClotureMensuelle`)**: Unique per `(superviseur, annee, mois)`; triggers `AjustementSolde` if balances are adjusted.

## Environment Variables

Required in `.env`:

```
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=5432
DEBUG=True
SECRET_KEY=
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
EMAIL_HOST_PASSWORD=
API_URL=http://127.0.0.1:8000   # External farm analytics API
```

## Configuration Notes

- **Database**: PostgreSQL in all environments (no SQLite fallback).
- **Language**: `LANGUAGE_CODE = 'fr-fr'`, `TIME_ZONE = 'UTC'`.
- **Context processor**: `core.context_processors.agent_context` injects agent info into all templates.
- **`DATE_DEBUT_ROT`**: `date(2026, 1, 1)` — controls ROT operational start date in business logic.
- **Debug toolbar**: Active when `DEBUG=True`; mounted at `__debug__/`.

## Export Libraries

- **Excel**: `openpyxl`
- **PDF**: `reportlab`
- **Word**: `python-docx`

Reports and exports live in `direction/` and `paie/` views.
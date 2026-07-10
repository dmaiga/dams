# Sprint 03 — App `finance` : solde superviseur, versements, dépenses

## Contexte

Le calcul du solde d'un superviseur (combien il détient réellement en cash à un instant donné) est aujourd'hui **dispersé** sur au moins quatre endroits, avec des formules incohérentes entre elles :

| Endroit | Formule | Problème |
|---|---|---|
| `Agent.solde_reel_superviseur` | `recouvre_agents + anciennes_ventes - depenses - versements + ajustement` | `total_depenses_superviseur` (utilisé ici) filtre `Depense.versement__superviseur=self` — lien déprécié, une dépense non liée à un versement est invisible |
| `Agent.solde_operationnel_superviseur` | `recouvre_agents + ventes_perso - versements_vente + ajustement` | Ne soustrait pas les dépenses du tout |
| `Agent.cash_disponible_superviseur` | `cash_agents + ventes_perso` | Ne soustrait ni versements ni dépenses (commentaire : "ON NE SOUSTRAIT PAS LES REMISES ICI") |
| `direction/services/cloture_service.calculer_solde_periode` | `solde_ouverture + ventes + recouvrements - depenses - versements` | Additionne `Vente(agent=superviseur)` **et** `Recouvrement(superviseur=superviseur)` sans exclure `agent=superviseur` de ce second total → double comptage des ventes personnelles. Dépenses toujours filtrées via `versement__superviseur` (déprécié). |
| `agents/services/rot_dashboard_service.get_kpis` | `recouvre - versements - depenses + ajustement` (côté ROT) | Correct et à jour, mais scope différent (ROT, pas superviseur) |

Cette dispersion n'a jamais été documentée comme décision — elle s'est installée au fil de correctifs locaux. L'app `finance` doit devenir la **source unique de vérité** pour ce calcul, réutilisable par les dashboards (`agents/`) et la clôture (`direction/`), sans pour autant les migrer tout de suite (voir Décisions).

### Contexte métier (rappel)

Un superviseur récupère de l'argent auprès de ses agents (`Vente` → `Recouvrement` automatique depuis `vente/`, toutes les ventes étant comptant). Il détient ce cash. En fin de journée, il communique sa recette. Le lendemain, **mdmaiga** (Direction, pas le ROT) effectue le versement bancaire réel et en reçoit le reçu. mdmaiga doit pouvoir, depuis une seule app :

1. Recouvrer la recette de la veille d'un superviseur (`RecouvrementSuperviseur`).
2. Enregistrer le versement bancaire correspondant (`VersementBancaire`), avec son reçu.
3. Suivre le cash flow (solde) de chaque superviseur.
4. Repérer si un montant manque (alerte / relance téléphonique).

---

## Décisions confirmées

1. **Identité de l'acteur "admin" dans les modèles** — `RecouvrementSuperviseur.rot` et `VersementBancaire.effectue_par` sont aujourd'hui restreints à `type_agent='rot'`. mdmaiga a déjà un `Agent` avec `type_agent='direction'`. On étend `limit_choices_to` de ces deux champs à `type_agent__in=['rot', 'direction']` (migration `AlterField`, non destructive — `limit_choices_to` ne contraint que les formulaires/admin, pas la base). Un groupe Django (`auth.Group`) pourra être ajouté plus tard si l'accès doit s'ouvrir à plusieurs personnes ; pas nécessaire pour ce sprint (un seul utilisateur : mdmaiga).
2. **Granularité du solde : calcul à la demande, pas de grand livre persistant.** Une seule fonction de service agrège `Recouvrement`/`Depense`/`VersementBancaire` sur une période donnée. Pas de nouveau modèle "solde du jour" pour ce sprint — on garde la possibilité de le faire plus tard si le besoin d'historiser une formule figée apparaît.
3. **Pas de nettoyage des 5 propriétés `Agent.solde_*` existantes dans ce sprint.** `finance/` introduit sa propre fonction de calcul, correcte, à côté de l'existant. La dépréciation/suppression des anciennes propriétés est une tâche future séparée (elles sont peut-être encore utilisées ailleurs — à auditer avant d'y toucher).
4. **`montant_hors_vente` exclu du solde.** Il reste stocké sur `VersementBancaire` pour traçabilité (c'est un flux d'une autre activité que mdmaiga doit quand même enregistrer), mais n'entre jamais dans le calcul du solde superviseur.
5. **Les dépenses sont indépendantes des versements** (décision déjà actée dans les faits par `rot_dashboard_service.get_kpis`, jamais documentée) : une `Depense` réduit le solde dès sa date d'effet (`date_depense`), qu'elle soit ou non liée plus tard à un `VersementBancaire`. `finance/` ne doit **jamais** filtrer les dépenses via `Depense.versement__superviseur` (ce lien reste optionnel, pour rattachement a posteriori uniquement, pas pour le calcul).
6. **`VersementBancaire.superviseur`** — marqué "⛔ à déprécier" dans le modèle, mais c'est en réalité le **seul champ qui indique de quel superviseur provient la recette versée** (`effectue_par` indique qui a physiquement fait le virement — mdmaiga désormais). `finance/` continue de s'appuyer dessus pour l'attribution par superviseur ; le renommer/clarifier est hors périmètre de ce sprint (juste ne pas le supprimer).
7. **`peut_faire_depense`** : nouveau champ booléen sur `Agent` (pas dérivé du rôle), pour permettre plus tard à un superviseur de saisir ses propres dépenses. `Depense.effectue_par` n'a déjà aucune restriction de `type_agent` au niveau modèle — seule la vue doit vérifier ce flag.

---

## Formule officielle (`finance/services.py`)

```python
def calculer_solde_superviseur(superviseur, date_debut, date_fin, solde_ouverture=Decimal("0.00")):
    encaissements = Recouvrement.objects.filter(
        superviseur=superviseur,
        date_recouvrement__gte=date_debut, date_recouvrement__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant_recouvre"), Decimal("0.00")))["total"]
    # ⚠️ Un seul flux d'encaissement : Recouvrement couvre déjà les ventes des
    # agents ET les ventes personnelles du superviseur (auto-distribution),
    # chaque Vente créant un Recouvrement depuis vente/. Ne PAS additionner
    # Vente(agent=superviseur) en plus — c'est la source du double comptage
    # actuel dans direction/services/cloture_service.py.

    depenses = Depense.objects.filter(
        effectue_par=superviseur,
        date_depense__gte=date_debut, date_depense__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]
    # Indépendant de tout VersementBancaire (décision n°5).

    versements = VersementBancaire.objects.filter(
        superviseur=superviseur,
        date_versement_reelle__gte=date_debut, date_versement_reelle__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant_vente"), Decimal("0.00")))["total"]
    # montant_hors_vente volontairement exclu (décision n°4).

    solde_fin = solde_ouverture + encaissements - depenses - versements

    return {
        "solde_ouverture": solde_ouverture,
        "encaissements": encaissements,
        "depenses": depenses,
        "versements": versements,
        "solde_fin": solde_fin,
    }
```

`solde_ouverture` par défaut = solde de clôture de la dernière `ClotureMensuelle` validée (même logique que `direction/management/commands/cloturer_mois.py::_get_solde_ouverture`), sinon `0`.

---

## User stories

**US-01 — Vue d'ensemble des soldes**
En tant que mdmaiga, je veux voir en un coup d'œil le solde actuel de chaque superviseur (recette non encore versée), pour savoir qui doit encore remettre de l'argent.

**US-02 — Recouvrer la recette d'un superviseur**
En tant que mdmaiga, je veux enregistrer que tel superviseur m'a remis sa recette de la veille (`RecouvrementSuperviseur`), pour tracer la remise avant le versement bancaire réel.

**US-03 — Enregistrer un versement bancaire**
En tant que mdmaiga, je veux enregistrer le versement réel (montant vente + montant hors-vente séparément, reçu à l'appui), pour que le solde du superviseur concerné diminue du montant vente uniquement.

**US-04 — Enregistrer une dépense**
En tant que mdmaiga (ou un superviseur avec `peut_faire_depense`), je veux enregistrer une dépense datée, indépendamment de tout versement, pour qu'elle réduise immédiatement le solde disponible.

**US-05 — Historique / détail par superviseur**
En tant que mdmaiga, je veux voir le détail des mouvements (encaissements, dépenses, versements) d'un superviseur sur une période, pour comprendre comment son solde a été obtenu.

**US-06 — Alerte montant manquant**
En tant que mdmaiga, je veux voir signalés les superviseurs dont le solde dépasse un seuil sans versement récent, pour savoir qui appeler.

---

## Périmètre de l'app `finance/`

| Vue | URL | Acteur | Description |
|-----|-----|--------|-------------|
| `dashboard_finance` | `/finance/` | direction (mdmaiga) | Liste des superviseurs avec solde courant, badge alerte si seuil dépassé |
| `detail_solde_superviseur` | `/finance/superviseur/<pk>/` | direction | Détail des mouvements (encaissements/dépenses/versements) sur la période |
| `recouvrer_superviseur` | `/finance/recouvrer/<pk>/` | direction | Formulaire `RecouvrementSuperviseur` |
| `creer_versement` | `/finance/versement/nouveau/` | direction | Formulaire `VersementBancaire` (+ upload reçu `RecuVersement`) |
| `creer_depense` | `/finance/depense/nouvelle/` | direction, ou agent avec `peut_faire_depense` | Formulaire `Depense` |
| `historique_versements` | `/finance/versements/` | direction | Liste paginée |
| `historique_depenses` | `/finance/depenses/` | direction | Liste paginée |

Guard : `_acces_finance(agent) = agent.est_direction` — capacité, pas nom en dur, mais dans le template le menu reste conditionné comme le reste du backoffice (cohérent avec le pattern déjà en place dans `base_admin.html` pour "Surveillance").

**Ce que l'app ne fait PAS (pour ce sprint) :**
- Ne touche pas aux 5 propriétés `Agent.solde_*` existantes (décision n°3).
- Ne migre pas `agents/services/rot_dashboard_service.py`, `agents/services/superviseur_service.py` ni `direction/services/cloture_service.py` vers la nouvelle fonction — ils continuent de fonctionner tels quels. La migration progressive est un sprint futur.
- Ne construit pas de grand livre journalier persistant (décision n°2).
- Ne gère pas encore l'ouverture de `peut_faire_depense` aux superviseurs dans l'UI de `vente/` — le champ est ajouté sur `Agent` mais son exploitation côté superviseur (accès à une page dépense) est un sprint futur ; ce sprint-ci l'utilise seulement pour ne pas bloquer `Depense.effectue_par` à `type_agent='rot'`.

---

## Tâches

### 1. Modèle — extension des permissions

**Fichier : `core/models.py`**

```python
# RecouvrementSuperviseur.rot
rot = models.ForeignKey(
    Agent, on_delete=models.CASCADE,
    limit_choices_to={'type_agent__in': ['rot', 'direction']},
    related_name='recouvrements_superviseurs'
)

# VersementBancaire.effectue_par
effectue_par = models.ForeignKey(
    Agent, on_delete=models.SET_NULL, null=True, blank=True,
    related_name="versements_effectues",
    limit_choices_to={'type_agent__in': ['rot', 'direction']},
    help_text="ROT ou Direction ayant réellement effectué le versement"
)

# Nouveau champ sur Agent
peut_faire_depense = models.BooleanField(
    default=False,
    verbose_name="Peut effectuer des dépenses",
    help_text="Autorise la saisie de dépenses indépendamment du rôle (ROT ou superviseur)."
)
```

```bash
python manage.py makemigrations core -n "extend_finance_permissions_and_peut_faire_depense"
python manage.py migrate
```

### 2. Création de l'app `finance/`

```bash
python manage.py startapp finance
```

`INSTALLED_APPS` (`dams/settings.py`) : ajouter `'finance'`.

`dams/urls.py` :
```python
path('finance/', include(('finance.urls', 'finance'), namespace='finance')),
```

### 3. `finance/services.py`

Contient `calculer_solde_superviseur(...)` (voir formule ci-dessus) + une fonction `lister_soldes_superviseurs(date_debut, date_fin)` qui l'applique à tous les superviseurs actifs pour alimenter le dashboard.

### 4. `finance/forms.py`

- `RecouvrementSuperviseurForm` : superviseur, montant, commentaire, date.
- `VersementBancaireForm` : superviseur, montant_vente, montant_hors_vente (séparés, avec aide contextuelle rappelant que hors_vente n'impacte pas le solde recette), description, date, upload reçu (`RecuVersement`, `inlineformset` ou champ `FileField` direct sur la vue).
- `DepenseForm` : montant, catégorie, note, date. `effectue_par` déduit de l'utilisateur connecté (ou choisi si mdmaiga saisit pour un superviseur).

### 5. `finance/views.py`

Guard `_acces_finance(agent) = agent.est_direction`. Vue `creer_depense` élargie : `agent.est_direction or agent.peut_faire_depense`.

### 6. Templates

Héritent de **`base_admin.html`** (et non `base.html`) — c'est l'espace de mdmaiga. Ajouter l'entrée dans le menu FINANCE existant de `base_admin.html`, à côté de "Versements"/"Dépenses" déjà présents (vérifier s'ils doivent être remplacés ou complétés — ce sont aujourd'hui des vues `direction_*`, à ne pas casser).

---

## Invariants

- `montant_hors_vente` n'entre jamais dans `calculer_solde_superviseur`.
- Une `Depense` impacte le solde dès sa `date_depense`, indépendamment de tout lien à un `VersementBancaire`.
- Un seul flux d'encaissement (`Recouvrement`), jamais additionné avec `Vente(agent=superviseur)` en parallèle (source du bug actuel dans `cloture_service.py`).
- `solde_ouverture` d'une période = `solde_cloture` de la dernière `ClotureMensuelle` validée du superviseur, sinon `0`.

---

## Critères de validation (Definition of Done)

- [ ] `manage.py check` propre après migration des `limit_choices_to` et ajout de `peut_faire_depense`.
- [ ] mdmaiga peut recouvrer un superviseur, enregistrer un versement (vente + hors-vente séparés) avec reçu, et une dépense, sans passer par le compte `rot` d'Abdoulaye.
- [ ] Le dashboard `finance` affiche un solde par superviseur cohérent avec la formule officielle (pas de double comptage des ventes personnelles).
- [ ] Une dépense enregistrée sans versement associé réduit immédiatement le solde affiché.
- [ ] `montant_hors_vente` est visible dans le détail du versement mais absent du calcul de solde.
- [ ] Aucune régression sur `agents/services/*`, `direction/services/cloture_service.py` ni les propriétés `Agent.solde_*` (non touchés par ce sprint).
- [ ] Accès à `finance/` refusé à tout agent qui n'est pas `est_direction`.

---

## Fichiers à créer / modifier

| Fichier | Action |
|---------|--------|
| `core/models.py` | Modifier — `limit_choices_to` sur `RecouvrementSuperviseur.rot` et `VersementBancaire.effectue_par` ; ajout `Agent.peut_faire_depense` |
| `core/migrations/XXXX_extend_finance_permissions.py` | Créer via `makemigrations` |
| `dams/settings.py` | Modifier — ajouter `'finance'` |
| `dams/urls.py` | Modifier — `path('finance/', ...)` |
| `finance/__init__.py`, `apps.py`, `urls.py`, `views.py`, `forms.py`, `services.py` | Créer |
| `finance/templates/finance/*.html` | Créer (héritent de `base_admin.html`) |
| `direction/templates/base_admin.html` | Modifier — liens vers les nouvelles vues `finance:*` |

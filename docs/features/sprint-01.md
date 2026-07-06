# Sprint 01 — Filtres et dates de référence dans l'app `surveillance`

## Contexte

L'app `surveillance` compare les ventes de la semaine courante (S) contre la semaine précédente (S-1).
Ce calcul devient trompeur dès le lundi matin : S n'a aucune vente encore enregistrée, la variation affiche -100 %, les alertes sont factices.

Par ailleurs, des données antérieures à 2026 polluent les analyses (anciens lots, anomalies historiques sans rapport avec l'activité actuelle).

Ce sprint résout ces deux problèmes et ajoute la sélection manuelle de semaine sur chaque page.

---

## Dates de référence

| Constante | Valeur | Usage |
|-----------|--------|-------|
| `DATE_PLANCHER_VENTES` | `date(2026, 1, 1)` | Plancher global — toutes les vues surveillance |
| `DATE_PLANCHER_PRIX` | `date(2026, 6, 1)` | Plancher anomalies prix uniquement |

Ces constantes sont à définir dans `surveillance/constants.py` (créer le fichier).
`DATE_DEBUT_ROT = date(2026, 1, 1)` existe déjà dans `core/` — réutiliser si possible plutôt que de dupliquer.

---

## User stories

**US-01 — Semaine sélectionnable**
En tant que directeur, je veux choisir n'importe quelle semaine passée pour voir les kg vendus de cette semaine comparés à la semaine qui la précède, sans être contraint à "semaine courante vs S-1".

**US-02 — Exclusion des données pre-2026**
En tant que directeur, je veux que toutes les ventes antérieures au 01/01/2026 soient invisibles dans la surveillance, pour ne pas fausser les comparaisons.

**US-03 — Anomalies prix datées à partir du 01/06/2026**
En tant que directeur, je veux que la surveillance des prix n'affiche que les ventes réalisées à partir du 01/06/2026 afin d'analyser uniquement les anomalies de prix de la période active de surveillance.

**US-04 — Tri par date de réception**
En tant que directeur, je veux pouvoir trier la liste des lots en anomalie par date de réception (du plus récent au plus ancien), pour lire les alertes actives en premier.

**US-05 — Filtres cohérents sur toutes les pages**
En tant que directeur, je veux retrouver le même sélecteur de semaine sur le dashboard, la liste KG, le détail superviseur et le détail produit — pour ne pas perdre le contexte en naviguant.

---

## Périmètre des pages

| Page | Filtre semaine | Plancher date | Tri |
|------|---------------|---------------|-----|
| `dashboard_surveillance` | Oui (semaine sélectionnable) | 01/01/2026 | — |
| `liste_kg_vendu` | Oui (remplace le select semaine/mois) | 01/01/2026 | — |
| `detail_superviseur` | Oui (hérite de la semaine sélectionnée) | 01/01/2026 | — |
| `detail_produit` | Oui (hérite de la semaine sélectionnée) | 01/01/2026 | — |
| `surveillance_prix` | Non (affiche depuis 01/06/2026 en continu) | `date_vente >= 01/06/2026` | Lots triés par `date_reception` DESC |
| `detail_prix` | Non | `date_vente >= 01/06/2026` | Par date de vente |

---

## Tâches

### 1. Constantes et helpers

**Créer `surveillance/constants.py`**

```python
from datetime import date

DATE_PLANCHER_VENTES = date(2026, 1, 1)
DATE_PLANCHER_PRIX   = date(2026, 6, 1)
```

**Créer `surveillance/week_utils.py`** (helpers semaine)

```python
from datetime import date, timedelta

def debut_semaine(d: date) -> date:
    """Retourne le lundi de la semaine contenant d."""
    return d - timedelta(days=d.weekday())

def fin_semaine(d: date) -> date:
    return debut_semaine(d) + timedelta(days=6)

def semaine_precedente(debut: date) -> tuple[date, date]:
    prec = debut - timedelta(weeks=1)
    return prec, prec + timedelta(days=6)

def parse_semaine(raw: str | None) -> date:
    """
    Reçoit la valeur du <input type="week"> (ex: "2026-W25").
    Retourne le lundi correspondant.
    Retourne le lundi de la semaine courante si raw est absent ou invalide.
    """
    if raw:
        try:
            return date.fromisoformat(raw + "-1")   # ISO week format
        except ValueError:
            pass
    today = date.today()
    return today - timedelta(days=today.weekday())
```

> `<input type="week">` soumet la valeur au format `"2026-W25"`. `date.fromisoformat("2026-W25-1")` retourne le lundi ISO de cette semaine.

---

### 2. Refactoring `ComparaisonPeriodeService`

Dans `surveillance/services/comparaison_service.py`, remplacer les méthodes `semaine_actuelle()` et `semaine_precedente()` par des méthodes acceptant une date de référence :

```python
@staticmethod
def semaine(debut: date) -> tuple[date, date]:
    return debut, debut + timedelta(days=6)

@staticmethod
def semaine_prec(debut: date) -> tuple[date, date]:
    prec = debut - timedelta(weeks=1)
    return prec, prec + timedelta(days=6)
```

Garder les anciennes méthodes en alias le temps de migrer les vues.

---

### 3. Plancher date dans les services

Dans chaque service qui filtre sur `date_vente`, appliquer le plancher :

**`surveillance/services/vente_service.py`** et **`surveillance/services/liste_kg_service.py`**

```python
from surveillance.constants import DATE_PLANCHER_VENTES

qs = Vente.objects.filter(
    date_vente__date__gte=max(date_debut, DATE_PLANCHER_VENTES),
    date_vente__date__lte=date_fin,
    est_supprime=False,
)
```

**`surveillance/services/prix_service.py`** (ou équivalent)

```python
from surveillance.constants import DATE_PLANCHER_PRIX

qs = Vente.objects.filter(
    date_vente__date__gte=DATE_PLANCHER_PRIX,
    est_supprime=False,
)
```

> Le filtre porte sur `date_vente`, pas sur `date_reception` du lot. Un lot reçu avant le 01/06/2026 peut générer une anomalie si la vente a eu lieu après cette date. Inversement, une vente du 30/05/2026 sur un lot récent reste exclue.

---

### 4. Vues — ajout du paramètre `semaine`

Chaque vue concernée lit `?semaine=2026-W25` depuis `request.GET` :

```python
from surveillance.week_utils import parse_semaine, debut_semaine, fin_semaine, semaine_precedente

class DashboardSurveillanceView(LoginRequiredMixin, View):
    def get(self, request):
        debut = parse_semaine(request.GET.get("semaine"))
        fin   = fin_semaine(debut)
        debut_prec, fin_prec = semaine_precedente(debut)

        # Passer debut/fin aux services au lieu des méthodes semaine_actuelle()
        ...
```

Même pattern pour `ListeKgVenduView`, `DetailSuperviseurView`, `DetailProduitView`.

**`DetailSuperviseurView` et `DetailProduitView`** — la semaine sélectionnée doit pouvoir être transmise depuis la page qui y lie (via `?semaine=` dans le href).

---

### 5. Surveillance prix — tri par date_reception

Dans la vue `SurveillancePrixView`, le queryset des lots doit être ordonné :

```python
lots = LotEntrepot.objects.filter(
    date_reception__date__gte=DATE_PLANCHER_PRIX,
    ...
).order_by("-date_reception")
```

Ajouter dans le template `surveillance_prix.html` un lien de tri cliquable sur l'en-tête de colonne `Date réception` (`?order=date_reception` ou `-date_reception`).

---

### 6. Templates

#### Widget semaine partagé

Créer un partial `surveillance/_filtre_semaine.html` :

```html
<form method="get" class="flex items-center gap-2">
    <label class="label-text text-sm">Semaine :</label>
    <input
        type="week"
        name="semaine"
        value="{{ semaine_selectionnee }}"
        max="{{ semaine_max }}"
        class="input input-bordered input-sm"
    >
    <button type="submit" class="btn btn-primary btn-sm">Appliquer</button>
    {% if request.GET.semaine %}
    <a href="?" class="btn btn-ghost btn-sm">Semaine courante</a>
    {% endif %}
</form>
```

`semaine_selectionnee` → format `"2026-W25"` calculé depuis `debut` dans la vue.  
`semaine_max` → semaine courante (empêche la sélection de semaines futures).

#### Pages à mettre à jour

- `dashboard_surveillance.html` — inclure `_filtre_semaine.html` dans l'en-tête
- `liste_kg_vendu.html` — remplacer le select `semaine/mois` par `_filtre_semaine.html`
- `detail_superviseur.html` — inclure `_filtre_semaine.html`
- `detail_produit.html` — inclure `_filtre_semaine.html`
- `surveillance_prix.html` — en-tête `Date réception` cliquable + badge info "données depuis le 01/06/2026"

---

## Sécurité (hors-sprint intégré)

### Contrôle d'accès — `SurveillanceAccessMixin`

Créer `surveillance/mixins.py` :

```python
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class SurveillanceAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return (
            hasattr(user, "agent") and
            user.agent.est_direction
        )
```

**Règle d'accès :** superutilisateurs Django + agents `direction` uniquement.  
Les superviseurs (`type_agent='entrepot'`) sont exclus — ils accèdent à leurs propres dashboards via l'app `agents`.

Toutes les CBV de l'app héritent de `SurveillanceAccessMixin` **avant** `TemplateView` :

```python
class DashboardSurveillanceView(SurveillanceAccessMixin, TemplateView):
    ...
```

---

## Performance (hors-sprint intégré)

### Slicing SQL dans `PrixSurveillanceService.ventes_a_perte`

Ajouter un paramètre `limit=None` pour pousser la clause `LIMIT` directement en base :

```python
@staticmethod
def ventes_a_perte(limit=None):
    lot_stats = (
        Vente.objects.filter(...).values(...).annotate(...).order_by('ecart')
    )
    if limit:
        lot_stats = lot_stats[:limit]   # LIMIT SQL — pas de chargement mémoire
    lot_ids = [r['detail_distribution__lot'] for r in lot_stats]
    ...
```

Le dashboard passe `limit=10` : seuls 10 lots sont hydratés, quel que soit le volume d'anomalies en base.

### Compteur de badge — `PrixSurveillanceService.count_anomalies`

Méthode dédiée pour afficher le badge "N lots en anomalie" sans charger les enregistrements :

```python
@staticmethod
def count_anomalies():
    return (
        Vente.objects
        .filter(
            est_supprime=False,
            date_vente__date__gte=DATE_PLANCHER_PRIX,
            prix_vente_unitaire__lt=F('detail_distribution__lot__prix_achat_unitaire'),
        )
        .values('detail_distribution__lot')
        .distinct()
        .count()
    )
```

---

## Critères de validation (Definition of Done)

- [ ] Lundi matin : choisir la semaine S-1 affiche les vraies données de la semaine dernière sans alerte fantôme.
- [ ] Une vente avec `date_vente = 2025-12-15` n'apparaît dans aucune vue surveillance.
- [ ] Une vente avec `date_vente = 2026-05-30` n'apparaît pas dans `surveillance_prix`.
- [ ] Une vente avec `date_vente = 2026-06-20` apparaît dans `surveillance_prix` même si le lot a été reçu avant le 01/06/2026.
- [ ] Une vente avec `date_vente = 2026-06-20` sur un lot reçu le 05/05/2026 est bien prise en compte dans les anomalies.
- [ ] La liste des lots en anomalie est triée par `date_reception` décroissant par défaut.
- [ ] Le lien vers `detail_superviseur` depuis le dashboard conserve la semaine sélectionnée (`?semaine=`).
- [ ] `<input type="week">` ne permet pas de sélectionner une semaine future.
- [ ] Aucune régression sur les pages qui n'ont pas de filtre semaine (`surveillance_prix`, `detail_prix`).
- [ ] Un utilisateur non connecté accédant à `/surveillance/` est redirigé vers `/login/`.
- [ ] Un agent terrain ou superviseur entrepôt connecté reçoit HTTP 403.
- [ ] Un superutilisateur ou agent direction accède librement aux dashboards.
- [ ] Le dashboard affiche le badge avec le nombre total de lots en anomalie (via `count_anomalies()`).
- [ ] Le tableau des ventes rouges sur le dashboard se limite à 10 lignes maximum (slicing SQL).

---

## Fichiers à créer / modifier

| Fichier | Action |
|---------|--------|
| `surveillance/constants.py` | Créer |
| `surveillance/week_utils.py` | Créer |
| `surveillance/mixins.py` | Créer *(sécurité)* |
| `surveillance/services/comparaison_service.py` | Modifier |
| `surveillance/services/vente_service.py` | Modifier |
| `surveillance/services/liste_kg_service.py` | Modifier |
| `surveillance/services/prix_service.py` | Modifier *(limit + count_anomalies)* |
| `surveillance/services/surveillance_prix_service.py` | Modifier |
| `surveillance/services/detail_produit_service.py` | Modifier |
| `surveillance/services/detail_superviseur_service.py` | Modifier |
| `surveillance/views/dashboard.py` | Modifier |
| `surveillance/views/kg_vendu.py` | Modifier |
| `surveillance/views/superviseur.py` | Modifier |
| `surveillance/views/produits.py` | Modifier |
| `surveillance/views/prix.py` | Modifier |
| `surveillance/templates/surveillance/partials/_filtre_semaine.html` | Créer |
| `surveillance/templates/surveillance/dashboard_surveillance.html` | Modifier |
| `surveillance/templates/surveillance/kg_vendu/liste_kg_vendu.html` | Modifier |
| `surveillance/templates/surveillance/superviseur/detail_superviseur.html` | Modifier |
| `surveillance/templates/surveillance/produits/detail_produit.html` | Modifier |
| `surveillance/templates/surveillance/prix/surveillance_prix.html` | Modifier |

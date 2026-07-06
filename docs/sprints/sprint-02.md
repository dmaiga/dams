# Sprint 02 — App `vente` : distribution superviseur, enregistrement ventes, recouvrement auto

## Contexte

Après le sprint `marchandise` (Jean reçoit les lots et les affecte aux superviseurs), c'est au tour du superviseur d'agir.
Le superviseur a reçu ses lots via `AffectationLotSuperviseur`. Il doit :

1. **Distribuer** ces produits à ses agents (terrain/mamies et agents gros).
2. **Enregistrer les ventes** que ses agents ont réalisées en précisant la quantité, la date et le type de vente.
3. **Recouvrer automatiquement** le montant lors de l'enregistrement d'une vente comptant — supprimant ainsi une saisie doublon.

### Problème actuel

- La distribution existe déjà dans `agents/` mais elle est construite autour de rôles et pas de flux.
- Le superviseur n'a pas de moyen d'indiquer **quel type de vente** il demande à un agent spécifique.
- L'enregistrement de la vente et du recouvrement sont deux opérations séparées → friction et risque d'oubli.

### Décision de découpage

Nouvelle app `vente/` — business capability "Distribution et ventes terrain".

Elle ne déplace aucun modèle de `core`. Elle importe `DistributionAgent`, `DetailDistribution`, `Vente`, `Recouvrement`, `AffectationLotSuperviseur`.

---

## Modèles concernés (dans `core`)

### Modèle existant : `DetailDistribution`

Ajouter le champ `type_vente_demande` :

```python
class DetailDistribution(models.Model):
    ...
    TYPE_VENTE_CHOICES = (
        ('gros', 'Vente en gros'),
        ('detail', 'Vente au détail'),
    )
    type_vente_demande = models.CharField(
        max_length=10,
        choices=TYPE_VENTE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Type de vente demandé",
        help_text="Type de vente que le superviseur demande à l'agent pour ce lot."
    )
```

**Règle de résolution du type de vente** au moment d'enregistrer une vente :

```
type_vente effectif
  = type_vente_demande (si renseigné sur DetailDistribution)
  OU agent.type_vente_par_defaut() (terrain → detail, agent_gros → gros)
```

Le superviseur peut le remplacer à la saisie de la vente (override ponctuel).

**Migration** : `python manage.py makemigrations core` puis `migrate`.

---

## User stories

**US-01 — Distribution par lot**
En tant que superviseur, je veux sélectionner un lot que j'ai reçu du stock central, choisir un agent, une quantité et le type de vente demandé, pour tracer la sortie de marchandise de mon entrepôt.

**US-02 — Type de vente par défaut intelligent**
En tant que superviseur, je veux que le formulaire pré-remplisse automatiquement le type de vente selon le profil de l'agent (mami → détail, agent gros → gros), mais je veux pouvoir le modifier si l'agent doit vendre différemment pour ce lot.

**US-03 — Enregistrement de la vente**
En tant que superviseur, je veux saisir une vente pour un de mes agents (distribution choisie, quantité, date, type de vente), pour que le système en garde une trace.

**US-04 — Override prix exceptionnel**
En tant que superviseur, je veux pouvoir corriger le prix unitaire lors de la saisie d'une vente si le prix standard n'a pas été appliqué, pour coller à la réalité du terrain.

**US-05 — Recouvrement automatique vente comptant**
En tant que superviseur, quand j'enregistre une vente comptant, je veux que le recouvrement soit automatiquement créé sans saisie supplémentaire, pour éviter les doublons et les oublis.

**US-06 — Historique des ventes**
En tant que superviseur, je veux voir la liste paginée de toutes les ventes enregistrées pour mes agents, avec le montant total et le statut du recouvrement.

---

## Périmètre de l'app `vente/`

| Vue | URL | Acteur | Description |
|-----|-----|--------|-------------|
| `liste_affectations` | `/vente/` | superviseur | Lots affectés par Jean, avec quantité restante |
| `creer_distribution` | `/vente/distribuer/` | superviseur | Créer une distribution vers un agent |
| `detail_distribution_superviseur` | `/vente/distribution/<pk>/` | superviseur | Détail d'une distribution : ventes par agent |
| `enregistrer_vente` | `/vente/vente/nouvelle/` | superviseur | Enregistrer une vente + recouvrement auto |
| `historique_ventes` | `/vente/ventes/` | superviseur | Liste paginée des ventes |

**Ce que l'app ne fait PAS :**
- Pas de gestion des dettes clients (c'est une future capacité `finance/`).
- Pas de versement bancaire ni de récupération par le ROT.
- Pas de modification / suppression de ventes existantes (fonctionnalités déjà dans `agents/`).

---

## Tâches

### 1. Migration — ajout `type_vente_demande`

**Fichier : `core/models.py`** — classe `DetailDistribution`

Ajouter le champ `type_vente_demande` décrit ci-dessus.

```bash
python manage.py makemigrations core -n "add_type_vente_demande_to_detail_distribution"
python manage.py migrate
```

---

### 2. Création de l'app `vente/`

```bash
python manage.py startapp vente
```

Ajouter `'vente'` dans `INSTALLED_APPS` (`dams/settings.py`).

Ajouter dans `dams/urls.py` :
```python
path('vente/', include('vente.urls', namespace='vente')),
```

---

### 3. `vente/urls.py`

```python
from django.urls import path
from . import views

app_name = 'vente'

urlpatterns = [
    path('', views.liste_affectations, name='liste_affectations'),
    path('distribuer/', views.creer_distribution, name='creer_distribution'),
    path('distribution/<int:pk>/', views.detail_distribution_superviseur, name='detail_distribution'),
    path('vente/nouvelle/', views.enregistrer_vente, name='enregistrer_vente'),
    path('ventes/', views.historique_ventes, name='historique_ventes'),
]
```

---

### 4. `vente/views.py`

#### Guard d'accès

```python
def _acces_superviseur(agent):
    return agent.est_superviseur
```

#### `liste_affectations`

Affiche les `AffectationLotSuperviseur` du superviseur connecté avec quantité restante.

```python
@login_required
def liste_affectations(request):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    affectations = (
        AffectationLotSuperviseur.objects
        .filter(superviseur=agent, quantite_restante__gt=0)
        .select_related('lot__produit', 'lot__fournisseur')
        .order_by('-date_affectation')
    )
    return render(request, 'vente/liste_affectations.html', {'affectations': affectations})
```

#### `creer_distribution`

- GET : formulaire `DistributionForm` avec agent, affectation (lot), quantité, type_vente_demande.
- POST valide : crée `DistributionAgent` + `DetailDistribution` + décrémente `AffectationLotSuperviseur.quantite_restante` dans un `transaction.atomic()`.

```python
@login_required
def creer_distribution(request):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    if request.method == 'POST':
        form = DistributionForm(request.POST, superviseur=agent)
        if form.is_valid():
            try:
                distribution = form.save(superviseur=agent)
                messages.success(request, "Distribution enregistrée.")
                return redirect('vente:detail_distribution', pk=distribution.pk)
            except Exception as e:
                messages.error(request, f"Erreur : {e}")
    else:
        form = DistributionForm(superviseur=agent)

    return render(request, 'vente/creer_distribution.html', {'form': form})
```

#### `detail_distribution_superviseur`

Affiche `DetailDistribution` (produit, quantité distribuée, quantité restante, ventes enregistrées).

#### `enregistrer_vente`

- GET : formulaire `VenteForm(superviseur=agent)` — filtre les distributions sur les agents du superviseur.
- POST valide : crée `Vente`. Si `mode_paiement == 'comptant'` → crée `Recouvrement` dans le même `transaction.atomic()`.

```python
@login_required
def enregistrer_vente(request):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    if request.method == 'POST':
        form = VenteForm(request.POST, superviseur=agent)
        if form.is_valid():
            try:
                with transaction.atomic():
                    vente = form.save()
                    if vente.mode_paiement == 'comptant':
                        Recouvrement.objects.create(
                            agent=vente.agent,
                            superviseur=agent,
                            vente=vente,
                            montant_recouvre=vente.total_vente,
                            date_recouvrement=vente.date_vente,
                        )
                messages.success(
                    request,
                    f"Vente de {vente.quantite} enregistrée"
                    + (" — recouvrement créé automatiquement." if vente.mode_paiement == 'comptant' else " — paiement à crédit.")
                )
                return redirect('vente:historique_ventes')
            except Exception as e:
                messages.error(request, f"Erreur : {e}")
    else:
        form = VenteForm(superviseur=agent)

    return render(request, 'vente/enregistrer_vente.html', {'form': form})
```

#### `historique_ventes`

Liste paginée (30/page) des `Vente` dont `detail_distribution__distribution__superviseur == agent`.

---

### 5. `vente/forms.py`

#### `DistributionForm`

Champs : `agent_terrain` (agents du superviseur), `affectation` (lots affectés au superviseur avec `quantite_restante > 0`), `quantite`, `type_vente_demande`.

`save(superviseur)` :
1. Crée `DistributionAgent(superviseur=superviseur, agent_terrain=agent_terrain)`.
2. Crée `DetailDistribution(distribution=dist, lot=affectation.lot, quantite=quantite, prix_gros=affectation.prix_gros, prix_detail=affectation.prix_detail, type_vente_demande=type_vente_demande)`.
3. Décrémente `affectation.quantite_restante -= quantite` et sauvegarde dans `transaction.atomic()`.

Validation : `quantite <= affectation.quantite_restante`.

#### `VenteForm`

Champs : `agent_terrain` (agents du superviseur), `detail_distribution` (distributions actives de cet agent — filtrées par AJAX), `quantite`, `type_vente`, `prix_vente_unitaire` (optionnel — override), `mode_paiement`, `date_vente`.

`__init__(superviseur)` :
- `agent_terrain` : queryset filtré sur `superviseur.agents_geres.filter(est_actif=True)`.
- `detail_distribution` : `none()` en GET, filtré par `agent_terrain` en POST.
- `type_vente` : valeur initiale dérivée de `detail_distribution.type_vente_demande` ou `agent.type_vente_par_defaut()`.
- `prix_vente_unitaire` : valeur initiale dérivée de `type_vente` (gros → `detail_distribution.prix_gros`, detail → `detail_distribution.prix_detail`).

Le champ `prix_vente_unitaire` est visible uniquement si le superviseur a `peut_override_prix == True` (toujours vrai pour `entrepot`).

Validation `clean_quantite` : `quantite <= detail_distribution.quantite_restante_calculee`.

---

### 6. Templates

#### Convention commune

Tous les templates héritent de `base.html`. Double layout Bootstrap : table desktop (`d-none d-md-block`) + cartes mobile (`d-md-none`). Pagination via `paginator.get_page()`.

#### `vente/liste_affectations.html`

- En-tête : titre "Mes lots" + bouton "Distribuer" (`btn-primary`).
- Tableau : Produit | Fournisseur | Qté affectée | Qté restante | Date affectation | Actions.
- Actions : "Distribuer" (btn-success, masqué si `quantite_restante == 0`).
- Carte mobile : produit, fournisseur, badge quantité restante, bouton distribuer.

#### `vente/creer_distribution.html`

- Section "Agent & lot" : sélecteur agent (dropdown), sélecteur affectation (cartes AJAX après sélection agent — même pattern que `marchandise/affecter_superviseur.html`).
- Section "Quantité & type de vente" : quantité, type_vente_demande (radio : Détail / Gros, pré-coché selon `agent.type_vente_par_defaut()`).
- JS : changement d'agent → AJAX pour charger les affectations disponibles (endpoint à créer dans `vente/`).

Endpoint AJAX à ajouter dans `vente/urls.py` :
```python
path('ajax/affectations-par-agent/', views.ajax_affectations_par_agent, name='ajax_affectations_par_agent'),
```

Vue AJAX :
```python
@login_required
def ajax_affectations_par_agent(request):
    agent_id = request.GET.get('agent_id')
    superviseur = request.user.agent
    aff = AffectationLotSuperviseur.objects.filter(
        superviseur=superviseur,
        quantite_restante__gt=0
    ).select_related('lot__produit', 'lot__fournisseur')
    data = [
        {
            'id': a.id,
            'label': f"{a.lot.produit.nom} | {a.lot.fournisseur.nom if a.lot.fournisseur else '—'} | Reçu {a.date_affectation} | STOCK: {a.quantite_restante}",
            'prix_gros': str(a.prix_gros or ''),
            'prix_detail': str(a.prix_detail or ''),
        }
        for a in aff
    ]
    return JsonResponse(data, safe=False)
```

#### `vente/detail_distribution_superviseur.html`

- 4 cartes résumé : agent, produit, quantité distribuée, quantité restante.
- Section "Ventes" : desktop table (date, quantité, type, prix, montant, recouvrement) + cartes mobile.
- Bouton "Enregistrer une vente" → `vente:enregistrer_vente?distribution=<pk>`.

#### `vente/enregistrer_vente.html`

- Section "Agent & distribution" :
  - Sélecteur agent (`superviseur.agents_geres`).
  - Distribution : cartes AJAX chargées après sélection agent.
    - Chaque carte affiche : produit, date distribution, quantité restante, prix gros / prix détail.
    - Carte sélectionnée → pré-remplit `type_vente` et `prix_vente_unitaire`.
- Section "Détail de la vente" :
  - Quantité.
  - Type de vente : radio (Détail / Gros). Pré-coché selon `type_vente_demande` de la distribution.
  - Prix unitaire : champ numérique, pré-rempli selon type de vente. Libellé "Prix (override éventuel)".
  - Mode de paiement : radio (Comptant / Crédit).
  - Date de vente : date field, défaut aujourd'hui.
- Bandeau informatif si `mode_paiement == 'comptant'` :
  ```
  ℹ️ Le recouvrement sera créé automatiquement.
  ```
  (affiché / masqué par JS sur changement du radio mode_paiement)

#### `vente/historique_ventes.html`

- En-tête : "Ventes" + bouton "Nouvelle vente".
- Desktop : Agent | Produit | Qté | Type | Prix | Montant | Mode pmt | Recouvrement | Date.
  - Colonne "Recouvrement" : badge vert "Auto" si `vente.mode_paiement == 'comptant'`, badge orange "À recouvrer" sinon.
- Mobile : carte avec agent + produit + montant + badge recouvrement.
- Pagination 30/page.

---

### 7. Mise à jour `base.html` — menu superviseur

Dans le bloc menu `{% elif request.user.agent.est_superviseur %}`, ajouter :

```html
<a href="{% url 'vente:liste_affectations' %}">
  <i class="fas fa-boxes me-1"></i>Mes lots
</a>
<a href="{% url 'vente:creer_distribution' %}">
  <i class="fas fa-share me-1"></i>Distribuer
</a>
<a href="{% url 'vente:enregistrer_vente' %}">
  <i class="fas fa-cash-register me-1"></i>Vente
</a>
<a href="{% url 'vente:historique_ventes' %}">
  <i class="fas fa-list me-1"></i>Historique
</a>
```

---

## Invariants métier

| Règle | Où l'appliquer |
|-------|---------------|
| `quantite <= affectation.quantite_restante` | `DistributionForm.clean_quantite()` |
| `quantite <= detail_distribution.quantite_restante_calculee` | `VenteForm.clean_quantite()` |
| Décrémentation `AffectationLotSuperviseur.quantite_restante` atomique | `DistributionForm.save()` dans `transaction.atomic()` |
| Création `Recouvrement` atomique avec `Vente` | `enregistrer_vente` view dans `transaction.atomic()` |
| `prix_vente_unitaire` défaut = `prix_gros` si type gros, `prix_detail` si type détail | `VenteForm.__init__` + JS côté client |
| `type_vente_demande` pré-coché selon profil agent | `DistributionForm.__init__` + template JS |
| Recouvrement auto **uniquement** si `mode_paiement == 'comptant'` | `enregistrer_vente` view |
| Pas de recouvrement auto si `mode_paiement == 'credit'` → `Dette` créée par `Vente.save()` | `Vente.save()` existant (ne pas toucher) |

---

## Flux complet résultant

```
Jean (gestionnaire_stock)
  → AffectationLotSuperviseur  [app marchandise — Sprint 01]
      ↓
Superviseur
  → DistributionAgent + DetailDistribution  [app vente — ce sprint]
      ↓
Superviseur enregistre Vente (pour son agent)
  → Recouvrement (auto si comptant)  [app vente — ce sprint]
  → Dette (auto si crédit)  [Vente.save() — existant]
```

---

## Critères de validation (Definition of Done)

- [ ] Jean distribue un lot depuis `marchandise/` → il apparaît dans `vente/liste_affectations` du superviseur.
- [ ] Le superviseur crée une distribution pour un agent mami : `type_vente_demande` est pré-coché "détail".
- [ ] Le superviseur crée une distribution pour un agent gros : `type_vente_demande` est pré-coché "gros".
- [ ] Le superviseur peut changer le type de vente lors de la distribution.
- [ ] La distribution décrémente `AffectationLotSuperviseur.quantite_restante`.
- [ ] Enregistrement d'une vente comptant → `Recouvrement` créé automatiquement avec `montant_recouvre = vente.total_vente`.
- [ ] Enregistrement d'une vente à crédit → pas de `Recouvrement` auto, mais `Dette` créée.
- [ ] Le champ prix est pré-rempli selon le type de vente sélectionné.
- [ ] Le superviseur peut modifier le prix (override).
- [ ] La quantité de la vente est refusée si elle dépasse `detail_distribution.quantite_restante_calculee`.
- [ ] Toutes les pages sont lisibles sur mobile (double layout Bootstrap).
- [ ] `historique_ventes` est paginé (30/page).
- [ ] Le menu superviseur contient les 4 nouveaux liens.
- [ ] Aucune régression sur les vues existantes dans `agents/`.

---

## Fichiers à créer / modifier

| Fichier | Action |
|---------|--------|
| `core/models.py` | Modifier — ajouter `type_vente_demande` à `DetailDistribution` |
| `core/migrations/XXXX_add_type_vente_demande.py` | Créer via `makemigrations` |
| `dams/settings.py` | Modifier — ajouter `'vente'` |
| `dams/urls.py` | Modifier — `path('vente/', ...)` |
| `vente/__init__.py` | Créer |
| `vente/apps.py` | Créer |
| `vente/urls.py` | Créer |
| `vente/views.py` | Créer |
| `vente/forms.py` | Créer |
| `vente/templates/vente/liste_affectations.html` | Créer |
| `vente/templates/vente/creer_distribution.html` | Créer |
| `vente/templates/vente/detail_distribution_superviseur.html` | Créer |
| `vente/templates/vente/enregistrer_vente.html` | Créer |
| `vente/templates/vente/historique_ventes.html` | Créer |
| `core/templates/base.html` | Modifier — menu superviseur |

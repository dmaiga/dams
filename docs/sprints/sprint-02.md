# Sprint 02 — App `vente` : ventes terrain et recouvrement auto

## Contexte

Le sprint `marchandise` a changé la donne : dans le cas courant, Jean (gestionnaire de stock) distribue désormais **directement à l'agent** sous la supervision du superviseur (champ `agent_terrain` sur `AffectationSuperviseurForm` — voir `marchandise/APP_MARCHANDISE.md`). L'étape manuelle "le superviseur reçoit puis redistribue à son agent" n'est plus le chemin normal.

Autre décision structurante : **aucun prix n'est plus fixé en amont**. `AffectationLotSuperviseur.prix_gros/prix_detail` (et donc `DetailDistribution.prix_gros/prix_detail` qui en hérite) sont désormais systématiquement `None`. Le prix dépend du type de vente de l'agent (mami → détail, agent gros → gros, polyvalent/stagiaire → libre) et n'est connu qu'au moment de la vente réelle sur le terrain.

**Ce qui reste au superviseur à faire :**

1. **Enregistrer les ventes** de ses agents : quantité, prix, type de vente et date — tout est saisi au moment de la vente, il n'y a plus de valeur pré-remplie à hériter d'une distribution.
2. **Recouvrer automatiquement** le montant lors d'une vente comptant — supprime une saisie doublon.
3. *(Exception)* **Distribuer/redistribuer manuellement** dans deux cas seulement :
   - Jean lui a affecté un lot **sans** choisir d'agent (le superviseur garde le stock, à répartir lui-même plus tard).
   - **Auto-distribution** : le superviseur se distribue à lui-même pour enregistrer une vente personnelle sous son propre nom.

### Ce qui change par rapport à la version initiale de ce sprint

| Avant (version initiale) | Maintenant |
|---|---|
| Ajout de `type_vente_demande` sur `DetailDistribution`, pré-coché à la distribution | **Abandonné.** Le type de vente n'est plus décidé à la distribution — le superviseur le choisit à chaque vente. Pas de migration nécessaire pour ce sprint. |
| `DetailDistribution.prix_gros/prix_detail` hérités de l'affectation (snapshot) | Toujours `None` en sortie de `marchandise`. Le prix est **saisi obligatoirement** à la vente, ce n'est plus un override optionnel. |
| `creer_distribution` = flux principal du superviseur | Devient un flux **d'exception** (stock non redirigé directement à un agent, ou auto-distribution). Le flux principal se joue déjà dans `marchandise`. |
| Dashboard superviseur : table "Stock sous votre responsabilité" + compteur "Activité récente" | Ne reflètent plus l'activité réelle (la marchandise ne transite plus forcément par le superviseur). À remplacer par une vue **"Produits en circulation"** — voir tâche dédiée plus bas. Les KPI financiers du haut de page (`finances_superviseur`) ne sont **pas touchés**. |

### Décision de découpage (inchangée)

Nouvelle app `vente/` — business capability "Ventes terrain et recouvrement".

Elle ne déplace aucun modèle de `core`. Elle importe `DistributionAgent`, `DetailDistribution`, `Vente`, `Recouvrement`, `AffectationLotSuperviseur`.

---

## Modèles concernés

**Aucune migration `core` n'est nécessaire pour ce sprint.** Les modèles (`DistributionAgent`, `DetailDistribution`, `Vente`, `Recouvrement`) existent déjà avec les champs requis ; le champ `agent_terrain_direct` ajouté sur `AffectationLotSuperviseur` (sprint `marchandise`) est suffisant pour savoir si une affectation a déjà été routée directement à un agent.

---

## User stories

**US-01 — Distribution exceptionnelle**
En tant que superviseur, quand je détiens encore du stock non redirigé vers un agent (ou pour une vente personnelle), je veux pouvoir le distribuer à un agent — ou me l'auto-distribuer — pour continuer à en tracer la sortie.

**US-02 — Enregistrement de la vente**
En tant que superviseur, je veux saisir une vente pour un de mes agents en indiquant la quantité, le prix, le type de vente (détail/gros) et la date, pour que le système en garde une trace complète — le prix et le type de vente ne sont plus pré-remplis, je les fixe à chaque vente.

**US-03 — Suggestion intelligente du type de vente**
En tant que superviseur, je veux que le formulaire de vente suggère un type de vente par défaut selon le profil de l'agent (`Agent.type_vente_par_defaut()` : mami → détail, agent gros → gros), tout en pouvant le changer librement — ce n'est qu'une suggestion, plus une règle imposée à la distribution.

**US-04 — Recouvrement automatique vente comptant**
En tant que superviseur, quand j'enregistre une vente comptant, je veux que le recouvrement soit automatiquement créé sans saisie supplémentaire, pour éviter les doublons et les oublis.

**US-05 — Historique des ventes**
En tant que superviseur, je veux voir la liste paginée de toutes les ventes enregistrées pour mes agents, avec le montant total et le statut du recouvrement.

**US-06 — Produits en circulation (tableau de bord)**
En tant que superviseur, je veux voir sur mon tableau de bord ce qui a été distribué à chacun de mes agents et n'est pas encore vendu, pour savoir ce qui circule réellement sur le terrain — plutôt qu'un stock "sous ma responsabilité" qui ne bouge plus puisque la marchandise part directement chez l'agent.

---

## Périmètre de l'app `vente/`

| Vue | URL | Acteur | Description |
|-----|-----|--------|-------------|
| `liste_affectations` | `/vente/` | superviseur | Stock qu'il détient encore (cas d'exception seulement — la majorité des affectations ont déjà `agent_terrain_direct` renseigné et n'apparaissent pas ici) |
| `creer_distribution` | `/vente/distribuer/` | superviseur | Distribution exceptionnelle vers un agent, ou auto-distribution |
| `detail_distribution_superviseur` | `/vente/distribution/<pk>/` | superviseur | Détail d'une distribution : ventes déjà enregistrées dessus |
| `enregistrer_vente` | `/vente/vente/nouvelle/` | superviseur | Enregistrer une vente (quantité, prix, type de vente, date) + recouvrement auto |
| `historique_ventes` | `/vente/ventes/` | superviseur | Liste paginée des ventes |

**Ce que l'app ne fait PAS :**
- Pas de gestion des dettes clients (c'est une future capacité `finance/`).
- Pas de versement bancaire ni de récupération par le ROT.
- Pas de modification / suppression de ventes existantes (fonctionnalités déjà dans `agents/`).
- Ne recalcule pas les KPI financiers du dashboard superviseur (`finances_superviseur`, `SuperviseurDashboardService.get_finances_superviseur`) — hors périmètre.

---

## Tâches

### 1. Création de l'app `vente/`

```bash
python manage.py startapp vente
```

Ajouter `'vente'` dans `INSTALLED_APPS` (`dams/settings.py`).

Ajouter dans `dams/urls.py` :
```python
path('vente/', include('vente.urls', namespace='vente')),
```

---

### 2. `vente/urls.py`

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

### 3. `vente/views.py`

#### Guard d'accès

```python
def _acces_superviseur(agent):
    return agent.est_superviseur
```

#### `liste_affectations`

Affiche les `AffectationLotSuperviseur` du superviseur connecté **qu'il détient encore** (`agent_terrain_direct__isnull=True`, `quantite_restante > 0`) — cas d'exception.

```python
@login_required
def liste_affectations(request):
    agent = request.user.agent
    if not _acces_superviseur(agent):
        return redirect('access_denied')

    affectations = (
        AffectationLotSuperviseur.objects
        .filter(superviseur=agent, agent_terrain_direct__isnull=True, quantite_restante__gt=0)
        .select_related('lot__produit', 'lot__fournisseur')
        .order_by('-date_affectation')
    )
    return render(request, 'vente/liste_affectations.html', {'affectations': affectations})
```

#### `creer_distribution`

- GET : formulaire `DistributionForm` avec agent (ou auto-distribution), affectation (lot), quantité.
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

### 4. `vente/forms.py`

#### `DistributionForm`

Champs : `agent_terrain` (agents du superviseur **+ le superviseur lui-même**, pour l'auto-distribution), `affectation` (lots qu'il détient encore avec `quantite_restante > 0` et `agent_terrain_direct__isnull=True`), `quantite`.

`save(superviseur)` :
1. Crée `DistributionAgent(superviseur=superviseur, agent_terrain=agent_terrain)` — `agent_terrain == superviseur` déclenche automatiquement `type_distribution = 'AUTO'` (logique déjà présente dans `DistributionAgent.save()`).
2. Crée `DetailDistribution(distribution=dist, lot=affectation.lot, quantite=quantite, prix_gros=None, prix_detail=None)` — pas de prix à hériter, l'affectation n'en a pas.
3. Décrémente `affectation.quantite_restante -= quantite` et sauvegarde dans `transaction.atomic()`.

Validation : `quantite <= affectation.quantite_restante`.

#### `VenteForm`

Champs : `agent_terrain` (agents du superviseur, y compris lui-même), `detail_distribution` (distributions actives de cet agent — filtrées par AJAX), `quantite`, `type_vente`, `prix_vente_unitaire` (**requis**, plus un override), `mode_paiement`, `date_vente`.

`__init__(superviseur)` :
- `agent_terrain` : queryset filtré sur `superviseur.agents_geres.filter(est_actif=True)` (+ superviseur lui-même pour les ventes personnelles).
- `detail_distribution` : `none()` en GET, filtré par `agent_terrain` en POST.
- `type_vente` : valeur **initiale suggérée** par `agent.type_vente_par_defaut()` si non `None`, sinon laissé au choix du superviseur (cas `agent_polivalent`/`stagiaire`/lui-même). Reste modifiable dans tous les cas.
- `prix_vente_unitaire` : aucune valeur par défaut (il n'y a plus de prix hérité) — champ obligatoire à chaque vente.

Validation `clean_quantite` : `quantite <= detail_distribution.quantite_restante_calculee`.

---

### 5. Templates

#### Convention commune

Tous les templates héritent de `base.html`. Double layout Bootstrap : table desktop (`d-none d-md-block`) + cartes mobile (`d-md-none`). Pagination via `paginator.get_page()`. Sobriété visuelle : pas de bordures colorées systématiques — une couleur n'apparaît que si elle porte une information réelle (ex. stock épuisé), cf. conventions posées dans `marchandise/APP_MARCHANDISE.md`.

#### `vente/liste_affectations.html`

- En-tête : titre "Stock en attente" (et non "Mes lots" — ce n'est plus le flux principal) + bouton "Distribuer".
- Tableau : Produit | Fournisseur | Qté affectée | Qté restante | Date affectation | Actions.
- Message si vide : "Tout votre stock a déjà été distribué directement par le gestionnaire." (cas normal désormais).

#### `vente/creer_distribution.html`

- Section "Agent & lot" : sélecteur agent (dropdown, **libellé = `full_name` uniquement**, incluant une option "Moi-même (vente personnelle)"), sélecteur affectation (cartes AJAX après sélection agent — même pattern que `marchandise/affecter_superviseur.html`).
- Section "Quantité" : quantité uniquement — plus de type de vente à ce stade.

#### `vente/detail_distribution_superviseur.html`

- Cartes résumé : agent, produit, quantité distribuée, quantité restante.
- Section "Ventes" : desktop table (date, quantité, type, prix, montant, recouvrement) + cartes mobile.
- Bouton "Enregistrer une vente" → `vente:enregistrer_vente?distribution=<pk>`.

#### `vente/enregistrer_vente.html`

- Section "Agent & distribution" :
  - Sélecteur agent (`superviseur.agents_geres` + lui-même).
  - Distribution : cartes AJAX chargées après sélection agent (produit, date distribution, quantité restante — pas de prix affiché, il n'y en a plus).
- Section "Détail de la vente" :
  - Quantité.
  - Type de vente : radio (Détail / Gros), pré-coché selon `agent.type_vente_par_defaut()` si connu, sinon aucun choix pré-coché.
  - Prix unitaire : champ numérique **obligatoire**, aucune valeur par défaut.
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

### 6. Mise à jour `base.html` — menu superviseur

Dans le bloc menu `{% elif request.user.agent.est_superviseur %}`, ajouter :

```html
<a href="{% url 'vente:enregistrer_vente' %}">
  <i class="fas fa-cash-register me-1"></i>Vente
</a>
<a href="{% url 'vente:historique_ventes' %}">
  <i class="fas fa-list me-1"></i>Historique ventes
</a>
<a href="{% url 'vente:creer_distribution' %}">
  <i class="fas fa-share me-1"></i>Distribuer (exception)
</a>
```

`Vente` en premier — c'est l'action que le superviseur fera le plus souvent désormais.

---

### 7. Tableau de bord superviseur — remplacer "Stock" et "Activité récente" par "Produits en circulation"

**Fichier : `agents/services/superviseur_service.py`**

Les deux méthodes `get_stock_superviseur` (table "Stock sous votre responsabilité") et `get_distributions_recentes` (compteur "Activité récente") ne reflètent plus l'activité réelle : la marchandise ne transite plus forcément par le stock du superviseur, elle part directement chez l'agent.

Remplacer ces deux blocs par une méthode unique `get_produits_en_circulation(superviseur)` qui regroupe les `DetailDistribution` actives (issues de distributions directes **ou** manuelles) par agent/produit, avec la quantité restant à vendre :

```python
@staticmethod
def get_produits_en_circulation(superviseur):
    from django.db.models import Sum
    details = (
        DetailDistribution.objects
        .filter(distribution__superviseur=superviseur)
        .select_related('distribution__agent_terrain__user', 'lot__produit')
        .order_by('-distribution__date_distribution')
    )
    return [
        {
            'agent': d.distribution.agent_terrain,
            'produit': d.lot.produit,
            'quantite_distribuee': d.quantite,
            'quantite_restante': d.quantite_restante_calculee,
            'date_distribution': d.distribution.date_distribution,
        }
        for d in details
        if d.quantite_restante_calculee > 0
    ]
```

Mettre à jour `build_dashboard_perimetre` : retirer `stock_superviseur` et `distributions_recentes` du contexte, ajouter `produits_en_circulation`. **Ne pas toucher** `finances_superviseur`, `agents_terrain`, `agents_financiers`.

**Fichier : `agents/templates/agents/dashboards/superviseur.html`**

Remplacer les blocs "Stock sous votre responsabilité" et "Activité récente" par un unique bloc "Produits en circulation" : table Agent | Produit | Distribué | Restant | Date. Garder les 4 cartes KPI en haut de page inchangées. Garder la section agents (déjà alimentée par `agents_terrain`/`agents_financiers`, hors périmètre de ce sprint).

---

## Invariants métier

| Règle | Où l'appliquer |
|-------|---------------|
| `quantite <= affectation.quantite_restante` | `DistributionForm.clean_quantite()` |
| `quantite <= detail_distribution.quantite_restante_calculee` | `VenteForm.clean_quantite()` |
| Décrémentation `AffectationLotSuperviseur.quantite_restante` atomique | `DistributionForm.save()` dans `transaction.atomic()` |
| Création `Recouvrement` atomique avec `Vente` | `enregistrer_vente` view dans `transaction.atomic()` |
| `prix_vente_unitaire` est **obligatoire**, sans valeur par défaut | `VenteForm` |
| `type_vente` **suggéré** (pas imposé) selon `agent.type_vente_par_defaut()` | `VenteForm.__init__` + template JS |
| Recouvrement auto **uniquement** si `mode_paiement == 'comptant'` | `enregistrer_vente` view |
| Pas de recouvrement auto si `mode_paiement == 'credit'` → `Dette` créée par `Vente.save()` | `Vente.save()` existant (ne pas toucher) |
| `get_finances_superviseur` (KPI dashboard) non modifié par ce sprint | `agents/services/superviseur_service.py` |

---

## Flux complet résultant

```
Jean (gestionnaire_stock)
  → AffectationLotSuperviseur                          [app marchandise]
      │
      ├── agent_terrain choisi (cas normal)
      │     → DistributionAgent + DetailDistribution créés directement par marchandise
      │
      └── agent_terrain non choisi (cas d'exception)
            → le superviseur garde le stock
            → DistributionAgent + DetailDistribution     [app vente — creer_distribution]
                  (vers un agent, ou auto-distribution vers lui-même)
                      ↓
Superviseur enregistre une Vente (quantité, prix, type de vente, date)  [app vente]
  → Recouvrement (auto si comptant)                     [app vente]
  → Dette (auto si crédit)                               [Vente.save() — existant]
```

---

## Critères de validation (Definition of Done)

- [ ] Jean distribue un lot directement à un agent depuis `marchandise/` → une `DetailDistribution` apparaît pour cet agent, prête à être vendue, **sans** passage par `vente/creer_distribution`.
- [ ] Jean affecte un lot à un superviseur sans choisir d'agent → il apparaît dans `vente/liste_affectations` de ce superviseur.
- [ ] Le superviseur peut distribuer ce stock à un agent, ou se l'auto-distribuer pour une vente personnelle.
- [ ] La distribution décrémente `AffectationLotSuperviseur.quantite_restante`.
- [ ] `VenteForm` exige un prix à chaque vente (aucune valeur par défaut).
- [ ] Le type de vente est suggéré selon le profil de l'agent mais reste modifiable.
- [ ] Enregistrement d'une vente comptant → `Recouvrement` créé automatiquement avec `montant_recouvre = vente.total_vente`.
- [ ] Enregistrement d'une vente à crédit → pas de `Recouvrement` auto, mais `Dette` créée.
- [ ] La quantité de la vente est refusée si elle dépasse `detail_distribution.quantite_restante_calculee`.
- [ ] Le tableau de bord superviseur affiche "Produits en circulation" à la place de "Stock sous votre responsabilité" et "Activité récente" ; les 4 KPI financiers du haut ne changent pas.
- [ ] Toutes les pages sont lisibles sur mobile (double layout Bootstrap, pas de bordures colorées superflues).
- [ ] `historique_ventes` est paginé (30/page).
- [ ] Le menu superviseur contient les 3 nouveaux liens (Vente en premier).
- [ ] Aucune régression sur les vues existantes dans `agents/`.

---

## Fichiers à créer / modifier

| Fichier | Action |
|---------|--------|
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
| `agents/services/superviseur_service.py` | Modifier — remplacer `get_stock_superviseur`/`get_distributions_recentes` par `get_produits_en_circulation` |
| `agents/templates/agents/dashboards/superviseur.html` | Modifier — bloc "Produits en circulation" à la place des deux anciens blocs |

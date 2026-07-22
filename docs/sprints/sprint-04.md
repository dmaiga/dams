# Sprint 04 — App `surveillance` : alertes durée de vie du stock + refonte navigation par thème

## Contexte

Ce sprint fusionne deux besoins liés :

1. **Chantier 2 du backlog** (`docs/BACKLOG.md`) — suivre le temps qu'un produit passe en entrepôt et alerter sur deux situations : rotation non respectée (agent sans vente depuis 2 jours) et stock qui dort (lot non distribué depuis 2 semaines).
2. **Refonte de la navigation de l'app**, demandée après inspection de l'existant : chacune des 7 vues actuelles (`dashboard_surveillance`, `liste_kg_vendu`, `surveillance_prix`, `detail_prix`, `detail_produit`, `detail_superviseur`) réimplémente ses propres liens vers les autres pages, avec un style différent à chaque fois (`tabs tabs-boxed` sur le dashboard, paires de `btn btn-outline` ailleurs, breadcrumbs qui figent un parent thématique arbitraire). Il n'existe aucun regroupement par thème — Volumes, Prix et (bientôt) Stock sont juxtaposés sans hiérarchie visuelle claire, ce qui rend le parcours utilisateur dispersé et improvisé.

### Révision de la décision d'emplacement du 22/07/2026

Le backlog (Chantier 2) tranchait initialement : *« Emplacement : dans `DashboardSurveillanceView` existant, à côté des ventes rouges déjà affichées — pas de vue dédiée séparée »*. Ce sprint **remplace ce point** (validé par mdmaiga le 22/07/2026, en même temps que la refonte de nav) : les deux nouvelles alertes sont exposées dans un thème dédié **Stock & Rotation**, au même niveau que Prix et Kg vendus, avec seulement un résumé chiffré sur le dashboard global (même traitement que la carte "Anomalies prix" actuelle). Raison : entasser deux tableaux supplémentaires dans le dashboard existant aurait aggravé exactement le problème de dispersion que ce sprint corrige par ailleurs. `docs/BACKLOG.md` (Chantier 2) a été mis à jour en conséquence — voir section correspondante.

### Contexte métier (rappel Chantier 2)

Délai raisonnable fixé à **2 jours** pour la rotation. Deux alertes distinctes :

1. **Produits sans vente depuis plus de 2 jours** — un agent a reçu un lot (`DistributionAgent.date_distribution` / `DetailDistribution`) et n'a enregistré aucune `Vente` depuis plus de 2 jours (délai compté depuis la distribution, ou depuis la dernière vente si l'agent vendait puis s'est arrêté).
2. **Produits en stock depuis plus de 2 semaines** — un `LotEntrepot` avec `quantite_restante > 0`, non ou partiellement distribué, dont `date_reception` dépasse 2 semaines.

Granularité : par lot / distribution à l'agent (`DetailDistribution`), pas par produit agrégé. « Date de sortie » = `DistributionAgent.date_distribution`, jamais la date de vente.

---

## Décisions confirmées

1. **Pas de nouveau modèle.** Tout existe déjà : `LotEntrepot.date_reception`, `LotEntrepot.quantite_restante`, `DistributionAgent.date_distribution`, `DetailDistribution`, `Vente.detail_distribution`, `Vente.est_supprime`.
2. **Nouveau service** `surveillance/services/stock_age_service.py`, sur le modèle de `SurveillancePrixService` : une méthode de résumé par alerte + une méthode `count_*` dédiée aux badges, avec `limit` appliqué au niveau SQL (pattern déjà en place sur `ventes_a_perte`).
3. **Constantes de délai** ajoutées à `surveillance/constants.py`, pas en dur dans le service (cohérent avec `DATE_PLANCHER_PRIX`) : `DELAI_ROTATION_JOURS = 2`, `DELAI_STOCK_DORMANT_JOURS = 14`.
4. **Nouveau thème "Stock & Rotation"** — vue dédiée `StockRotationView`, au même rang que `ListeKgVenduView` et `SurveillancePrixView` (voir écart assumé ci-dessus).
5. **Nav thématique commune** — un seul partial (`partials/_nav_themes.html`) porte les 3 (bientôt 4) onglets de premier niveau, inclus par tous les templates de l'app. Il remplace les `tabs`/`btn btn-outline` dupliqués existants, sans changer le moteur de filtre semaine (`_filtre_semaine.html` reste tel quel, juste réutilisé partout où il manque).
6. **Breadcrumb contextuel** pour les fiches transverses `detail_produit` et `detail_superviseur` (atteignables depuis "Kg vendus" **et** depuis "Anomalies prix") : un paramètre `?from=kg|prix|stock` porté par les liens entrants détermine le fil d'Ariane affiché, au lieu du parent figé actuel ("Kg vendus" en dur).
7. **Respect des invariants existants de l'app** : `est_supprime=False` partout, aucune mutation, accès restreint via `SurveillanceAccessMixin` (déjà en place, pas d'app dams_agro concernée — lecture seule).

---

## User stories

**US-01 — Alerte rotation lente**
En tant que mdmaiga, je veux voir la liste des agents n'ayant enregistré aucune vente depuis plus de 2 jours sur un lot qui leur a été distribué, pour relancer les agents inactifs.

**US-02 — Alerte stock dormant**
En tant que mdmaiga, je veux voir la liste des lots en entrepôt depuis plus de 2 semaines et non distribués, pour identifier l'argent gelé en stock.

**US-03 — Résumé sur le dashboard global**
En tant que mdmaiga, je veux voir un compteur des deux alertes sur le tableau de bord principal, pour repérer un signal fort sans changer de page.

**US-04 — Navigation cohérente**
En tant que mdmaiga, je veux retrouver la même barre de thèmes (Vue d'ensemble / Volumes / Prix / Stock) sur toutes les pages de l'app, pour naviguer sans avoir à deviner où se trouve chaque information.

**US-05 — Fil d'Ariane fidèle au parcours réel**
En tant que mdmaiga, je veux que le fil d'Ariane d'une fiche produit ou superviseur reflète la page depuis laquelle j'y suis arrivé, pour ne pas perdre le contexte de mon analyse.

---

## Découpage en volets

Sprint volontairement gros — découpé en 4 volets livrables indépendamment, dans l'ordre recommandé (le Volet 1 conditionne le Volet 2 ; le Volet 3 peut être fait en parallèle du 1/2 ; le Volet 4 clôture).

### Volet 1 — Service `stock_age_service.py` (backend Chantier 2)

**Fichiers** : `surveillance/constants.py` (modifier), `surveillance/services/stock_age_service.py` (créer).

```python
# surveillance/constants.py — ajout
DELAI_ROTATION_JOURS = 2
DELAI_STOCK_DORMANT_JOURS = 14
```

```python
# surveillance/services/stock_age_service.py (squelette)
from django.utils import timezone
from django.db.models import Max, Q
from core.models import DetailDistribution, LotEntrepot
from surveillance.constants import DELAI_ROTATION_JOURS, DELAI_STOCK_DORMANT_JOURS

class StockAgeService:
    @staticmethod
    def agents_sans_vente_recente(limit=None):
        # DetailDistribution dont la distribution date de plus de DELAI_ROTATION_JOURS
        # et dont la dernière Vente (est_supprime=False) associée, s'il y en a une,
        # date aussi de plus de DELAI_ROTATION_JOURS. Jointure sur
        # distribution.agent_terrain pour identifier l'agent en cause.
        # Agrégat Max('ventes__date_vente') par DetailDistribution, filtré ensuite en Python
        # (comme SurveillancePrixService.get_detail_lot le fait pour "rouge").
        ...

    @staticmethod
    def count_agents_sans_vente_recente():
        ...

    @staticmethod
    def lots_stock_dormant(limit=None):
        # LotEntrepot.quantite_restante > 0, date_reception < now - DELAI_STOCK_DORMANT_JOURS,
        # non ou partiellement distribué (comparer quantite_restante à quantite_initiale
        # ou vérifier l'absence de DistributionAgent liée selon quantite déjà distribuée).
        ...

    @staticmethod
    def count_lots_stock_dormant():
        ...
```

Suivre exactement le pattern de `SurveillancePrixService.get_resume()` : une requête d'agrégation groupée, puis hydratation des objets (`Agent`, `LotEntrepot`) en une seconde requête `filter(id__in=...)`, jamais de boucle Python avec requête par itération.

**DoD Volet 1** :
- [ ] `StockAgeService.agents_sans_vente_recente()` retourne, pour chaque agent concerné, le lot, la date de distribution, la date de dernière vente (ou `None`) et le nombre de jours écoulés.
- [ ] `StockAgeService.lots_stock_dormant()` retourne, pour chaque lot concerné, la quantité restante, la date de réception et le nombre de jours écoulés.
- [ ] Les deux `count_*` n'exécutent qu'une requête `COUNT` SQL (pas de `len()` sur un queryset chargé).
- [ ] Aucun lot/agent avec `est_supprime=True` (ventes) n'apparaît dans les résultats.
- [ ] Tests unitaires (`surveillance/tests.py`) couvrant : agent avec vente récente (absent), agent sans vente > 2j (présent), lot totalement distribué (absent de stock dormant), lot partiel > 14j (présent).

---

### Volet 2 — Vue et template "Stock & Rotation"

**Fichiers** : `surveillance/views/stock_rotation.py` (créer), `surveillance/urls.py` (modifier), `surveillance/templates/surveillance/stock_rotation/dashboard_stock.html` (créer), `surveillance/templates/surveillance/dashboard_surveillance.html` (modifier — carte résumé).

```python
# surveillance/urls.py — ajout
path("stock-rotation/", StockRotationView.as_view(), name="stock_rotation"),
```

`StockRotationView(SurveillanceAccessMixin, TemplateView)` : injecte `agents_sans_vente` (10 premiers + total via `count_agents_sans_vente_recente`) et `lots_dormants` (10 premiers + total), sur le modèle exact de `SurveillancePrixView`.

Template : deux tableaux (rotation lente / stock dormant), header + nav thématique (Volet 3), KPI en tête (nb agents concernés, nb lots dormants, valeur stock immobilisée = `Σ quantite_restante * prix_achat_unitaire` des lots dormants).

Dashboard global (`dashboard_surveillance.html`) : ajouter une 4e carte "priorité" (à côté de Superviseurs / Produits / Anomalies prix) — badge `count_agents_sans_vente_recente + count_lots_stock_dormant`, lien "Voir tout →" vers `stock_rotation`. Ne pas dupliquer les tableaux détaillés sur le dashboard (c'est précisément ce que ce sprint évite).

**DoD Volet 2** :
- [ ] `/surveillance/stock-rotation/` affiche les deux listes avec pagination/limite SQL. Pas de filtre semaine ici : la fenêtre glissante (2 jours / 14 jours) se calcule depuis `timezone.now()`, pas depuis une semaine calendaire sélectionnée.
- [ ] Le dashboard global affiche un compteur agrégé des deux alertes, sans reproduire les tableaux.
- [ ] Accès restreint via `SurveillanceAccessMixin` (même guard que le reste de l'app).
- [ ] Aucune requête N+1 (vérifier via `django-debug-toolbar` ou `assertNumQueries` en test).

---

### Volet 3 — Nav thématique commune (fondation UX)

**Fichiers** : `surveillance/templates/partials/_nav_themes.html` (créer), les 7 templates existants + `dashboard_stock.html` (modifier — inclusion, suppression des blocs de liens ad hoc).

```html
<!-- partials/_nav_themes.html -->
<div class="tabs tabs-boxed bg-base-200">
  <a href="{% url 'dashboard_surveillance' %}{{ qs_semaine }}" class="tab {% if theme == 'accueil' %}tab-active font-semibold{% endif %}">Vue d'ensemble</a>
  <a href="{% url 'liste_kg_vendu' %}{{ qs_semaine }}" class="tab {% if theme == 'kg' %}tab-active font-semibold{% endif %}">Volumes</a>
  <a href="{% url 'surveillance_prix' %}" class="tab {% if theme == 'prix' %}tab-active font-semibold{% endif %}">Prix &amp; Rentabilité</a>
  <a href="{% url 'stock_rotation' %}" class="tab {% if theme == 'stock' %}tab-active font-semibold{% endif %}">Stock &amp; Rotation</a>
</div>
```

Chaque vue passe `context["theme"] = "accueil"|"kg"|"prix"|"stock"` (une ligne par `get_context_data`). Les templates remplacent leur bloc de liens actuel (tabs sur le dashboard, `btn btn-outline` sur `liste_kg_vendu.html`/`surveillance_prix.html`) par `{% include "partials/_nav_themes.html" %}`.

Les fiches de détail (`detail_prix.html`, `detail_produit.html`, `detail_superviseur.html`) gardent leur breadcrumb (Volet 4) mais reçoivent aussi la nav thématique en tête, pour ne jamais laisser l'utilisateur sans repère de thème même en profondeur.

**DoD Volet 3** :
- [ ] Un seul fichier (`_nav_themes.html`) définit le style et les libellés des 4 thèmes ; aucun autre template ne redéfinit de tabs/boutons de navigation inter-thème.
- [ ] L'onglet actif est visuellement marqué sur les 8 pages (7 existantes + `stock_rotation`).
- [ ] `semaine_selectionnee` reste propagé dans les liens de nav sur toutes les pages où il s'applique (actuellement manquant sur `surveillance_prix.html`).

---

### Volet 4 — Fil d'Ariane contextuel (`detail_produit`, `detail_superviseur`)

**Fichiers** : `surveillance/templates/surveillance/produits/detail_produit.html`, `surveillance/templates/surveillance/superviseur/detail_superviseur.html` (modifier), tous les templates qui pointent vers ces deux vues (`liste_kg_vendu.html`, `detail_prix.html`, `dashboard_surveillance.html`, `detail_produit.html` ↔ `detail_superviseur.html` entre elles) (modifier — ajouter `?from=...` aux liens).

Principe : chaque lien entrant vers `detail_produit`/`detail_superviseur` ajoute `&from=kg|prix|stock`. La vue lit `self.request.GET.get("from", "kg")` et l'injecte dans le contexte (`origine`). Le template choisit le libellé et l'URL du parent du breadcrumb en fonction de `origine` :

```html
<div class="breadcrumbs text-sm">
  <ul>
    <li><a href="{% url 'dashboard_surveillance' %}">Accueil</a></li>
    {% if origine == 'prix' %}
      <li><a href="{% url 'surveillance_prix' %}">Anomalies prix</a></li>
    {% elif origine == 'stock' %}
      <li><a href="{% url 'stock_rotation' %}">Stock &amp; Rotation</a></li>
    {% else %}
      <li><a href="{% url 'liste_kg_vendu' %}">Kg vendus</a></li>
    {% endif %}
    <li class="font-semibold">{{ superviseur.full_name }}</li>
  </ul>
</div>
```

Défaut `from=kg` si absent (comportement actuel inchangé pour les liens non mis à jour).

**DoD Volet 4** :
- [ ] Depuis `detail_prix.html` → clic sur un superviseur du tableau "Agents à surveiller" → le breadcrumb de `detail_superviseur` affiche "Anomalies prix" comme parent, pas "Kg vendus".
- [ ] Depuis `stock_rotation` → clic sur un agent/produit concerné → breadcrumb affiche "Stock & Rotation" comme parent.
- [ ] Aucun lien existant cassé (tous les appels `{% url 'detail_superviseur' ... %}` / `{% url 'detail_produit' ... %}` recensés et mis à jour avec leur `from` correspondant).

---

## Invariants (valables sur tout le sprint)

- Lecture seule : aucune vue de `surveillance/` n'écrit sur `core` ni sur dams_agro.
- `est_supprime=False` systématique sur tout filtre `Vente`.
- Agrégations et `limit` appliqués au niveau SQL (ORM), jamais sur des listes Python déjà chargées — cf. point de vigilance déjà noté dans `APP_SURVEILLANCE.md`.
- `SurveillanceAccessMixin` sur toute nouvelle vue (`StockRotationView` inclus).
- Un seul composant de navigation thématique pour toute l'app (Volet 3) — plus de duplication de style de liens inter-pages.

---

## Critères de validation globaux (Definition of Done du sprint)

- [ ] Les 4 volets ci-dessus sont chacun individuellement validés (DoD par volet).
- [ ] `manage.py check` propre, aucune migration nécessaire (aucun nouveau modèle).
- [ ] Parcours manuel complet : Dashboard → Stock & Rotation → détail agent/lot → retour, sans perte de contexte ni lien mort.
- [ ] `APP_SURVEILLANCE.md` mis à jour : nouvelle vue `StockRotationView`, nouveau service `StockAgeService`, section navigation décrivant `_nav_themes.html`.
- [ ] `docs/BACKLOG.md` (Chantier 2) mis à jour : statut → ✅ terminée, note sur l'écart assumé (thème dédié au lieu d'intégration dashboard).

---

## Fichiers à créer / modifier

| Fichier | Action |
|---|---|
| `surveillance/constants.py` | Modifier — `DELAI_ROTATION_JOURS`, `DELAI_STOCK_DORMANT_JOURS` |
| `surveillance/services/stock_age_service.py` | Créer |
| `surveillance/views/stock_rotation.py` | Créer |
| `surveillance/urls.py` | Modifier — route `stock-rotation/` |
| `surveillance/templates/surveillance/stock_rotation/dashboard_stock.html` | Créer |
| `surveillance/templates/partials/_nav_themes.html` | Créer |
| `surveillance/templates/surveillance/dashboard_surveillance.html` | Modifier — carte résumé + nav commune |
| `surveillance/templates/surveillance/kg_vendu/liste_kg_vendu.html` | Modifier — nav commune, `from=kg` sur liens sortants |
| `surveillance/templates/surveillance/prix/surveillance_prix.html` | Modifier — nav commune, propagation `semaine_selectionnee`, `from=prix` |
| `surveillance/templates/surveillance/prix/detail_prix.html` | Modifier — nav commune, `from=prix` sur lien vers `detail_superviseur` |
| `surveillance/templates/surveillance/produits/detail_produit.html` | Modifier — breadcrumb contextuel (`origine`), nav commune |
| `surveillance/templates/surveillance/superviseur/detail_superviseur.html` | Modifier — breadcrumb contextuel (`origine`), nav commune |
| `surveillance/views/dashboard.py`, `kg_vendu.py`, `prix.py`, `produits.py`, `superviseur.py` | Modifier — injection `context["theme"]` / `context["origine"]` |
| `surveillance/tests.py` | Modifier — tests `StockAgeService` |
| `surveillance/APP_SURVEILLANCE.md` | Modifier — documenter Volet 1-4 |
| `docs/BACKLOG.md` | Modifier — statut Chantier 2 |

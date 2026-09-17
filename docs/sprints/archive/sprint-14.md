# Sprint 14 — Traçabilité produits en circulation (suivi distributions, ventes, BI)

**Statut** : 🟢 terminé (chantiers A et B) — livré le 17/09/2026. Chantier C abandonné (décision 4).

> Une fois ce sprint terminé, déplacer ce fichier dans `docs/sprints/archive/`.

**Révision UX du tableau « Produits à investiguer » (même jour, après livraison)** : la version
initiale listait une ligne par produit (avec fournisseur et valorisation FCFA). Retour mdmaiga :
ce n'est pas un document comptable mais une checklist terrain — reconstruite en vue agrégée
superviseur → agent → produits (badges compacts, sans fournisseur ni valorisation), export Excel/
PDF aligné sur la même structure, boutons d'export remontés en tête de page. Détail dans
`direction/APP_DIRECTION.MD` § 7 (source de vérité à jour) ; ce fichier garde la trace de la
demande et du raisonnement initial, non mis à jour ligne à ligne après coup.

---

## Contexte métier

Trois demandes distinctes mais liées par un même problème de fond : **des produits sortis du
dépôt sans vente enregistrée derrière eux sont un angle mort financier** (perte, vol, ou simple
retard non signalé). Une semaine sans vente est normale (écoulement terrain), deux semaines est
jugé suspect par la direction.

1. `direction/suivi-distributions/` — page de traçabilité brute, doit devenir un outil
   d'investigation (liste exportable à remettre à un superviseur/agent).
2. `direction/direction/ventes` — page très consultée par la direction, manque le rattachement
   agent → superviseur en un coup d'œil.
3. BI (`bi/`) — pas d'axe dédié « produits en circulation sans vente » à l'échelle direction
   (toutes équipes), alors que la donnée existe déjà partiellement (`fct_stock_agent.sql`,
   utilisée aujourd'hui uniquement dans les fiches détail agent/superviseur).

Périmètre : `direction` (chantiers A et B) + `bi` (chantier C). Aucun impact `dams_agro`/
`analyse_champ` (lecture seule, hors sujet ici).

---

## Constat — vérification du code existant (avant tout chiffrage)

### A.1 — Bug confirmé : « None FCFA » dans la colonne Valorisation

`direction/templates/direction/analyses/stock/suivi_distributions.html:236-248` affiche
`d.prix_detail` pour les agents `terrain`. Or `rules/ARCHITECTURE.md` § Invariants critiques est
formel : **aucun prix n'est fixé avant la vente** — `DetailDistribution.prix_gros`/`prix_detail`
restent `None` jusqu'à l'enregistrement de la `Vente` (`vente.VenteForm.prix_vente_unitaire`).
`d.prix_detail` est donc toujours `None` pour ces lignes → `{{ d.prix_detail|intcomma }}` produit
littéralement « None FCFA ». Ce n'est pas un défaut d'affichage isolé, c'est une donnée qui n'a
structurellement pas de sens à cet endroit du flux. La demande de mdmaiga (retirer le prix de
vente de cette colonne) est donc la bonne correction, pas un simple masquage de symptôme.

### A.2 — Bug confirmé : le « jeu de couleurs » actuel n'a aucune valeur actionnable

`suivi_distributions.html:253-266` :

```django
{% if d.restant > 0 %}
    ...
    <div class="... {% if d.restant > 0 %}text-amber-600{% endif %}">
        Sorti il y a {{ d.distribution.date_distribution|timesince }}
    </div>
    <span class="badge badge-warning ...">SUR LE TERRAIN</span>
{% else %}
```

La condition `d.restant > 0` à l'intérieur du bloc est **toujours vraie** puisqu'on est déjà dans
la branche `{% if d.restant > 0 %}` du dessus — le texte est donc *systématiquement* ambre dès
qu'un produit est en circulation, qu'il soit sorti hier ou il y a un mois. Confirme exactement ce
que mdmaiga observe : « ce jeu de couleurs sans valeur actionnable ». Il n'existe aujourd'hui
**aucun seuil de jours** codé sur cette page (contrairement à `surveillance/constants.py`, qui a
ses propres seuils mais pour un usage différent — rétention 3 j, dormance entrepôt 15 j — non
transposables tels quels ici, cf. Décision D1).

### A.3 — Filtre par défaut : actuellement aucun

`direction/views.py:2331-2338` — sans `?statut=`, aucun filtre n'est appliqué : la page affiche
distribués + écoulés mélangés dès le premier chargement. Le `<select name="statut">` du template
n'a que deux options (`restant` / `ecoule`), pas de « Tous » explicite — donc impossible
aujourd'hui de revenir sciemment à la vue non filtrée une fois qu'un défaut serveur est en place ;
il faudra ajouter cette option en même temps que le changement de défaut.

Par ailleurs `statut == "dormant"` (ligne 2337-2338) est un code mort : strictement identique à
`statut == "restant"`. Existant, non demandé par mdmaiga — signalé mais **hors périmètre**, sauf
avis contraire (`rules/ABOUT-ME.md` : signaler plutôt que corriger seul hors demande, cf.
`[[feedback_security_hardening_priority]]`-like posture pour du code mort non lié à la demande).

### B.1 — `direction/ventes` : superviseur non affiché, mais accessible sans requête supplémentaire

`direction/services/vente_analyses.py::filter_ventes` fait déjà `select_related("agent",
"agent__user", ...)` mais pas `agent__superviseur`/`agent__superviseur__user`. `Agent.superviseur`
existe (FK déjà utilisée ailleurs, ex. `surveillance/services/stock_age_service.py`). Ajout : un
`select_related` de plus, pas de nouvelle requête N+1 à gérer côté template
(`vente.agent.superviseur.full_name`).

### C.1 — BI : la donnée existe déjà, mais seulement au niveau détail, pas en vue consolidée

`dbt_bi/models/marts/fct_stock_agent.sql` (sprint-11) calcule déjà, par ligne
`DetailDistribution` active, `agent_id`, `superviseur_id`, `produit_nom`, `date_reception`,
`stock_restant_kg` — exactement le grain demandé (« agents concernés, produits, date »). Il est
aujourd'hui exploité à deux endroits seulement :

- `dashboard_agent_detail` (bi/views.py:809) — un agent à la fois ;
- `dashboard_superviseur_detail` (bi/views.py:1154-1161) — agrégé par produit, **une équipe à la
  fois**, sans valorisation.

Il **n'existe pas** de vue direction-wide (toutes équipes) de ce stock en circulation, et le mart
ne porte **aucune valorisation** (`prix_achat_unitaire` absent de `fct_stock_agent.sql`, alors que
`stg_lots`/`prix_achat_unitaire` existe déjà côté `LotEntrepot` — cf. usage identique dans
`surveillance/services/stock_age_service.py::valeur_immobilisee`). C'est ce double manque
(consolidation + valorisation) qui explique le sentiment de mdmaiga (« il y avait eu un travail
là-dessus ») : le travail existe, mais à la mauvaille granularité pour un usage direction/finance.
`DASHBOARDS` (`bi/constants.py`) compte aujourd'hui 5 entrées ; le dashboard "produits" existant
est **Rentabilité Produit** (marge, pas circulation/risque) — à ne pas confondre.

---

## Décisions (mdmaiga, 17/09/2026)

1. ✅ **Seuils de couleur** (chantier A) : `SEUIL_ATTENTION_JOURS = 7`,
   `SEUIL_CRITIQUE_JOURS = 14`, calculés sur `distribution.date_distribution`. Constantes locales
   à `direction/` (pas de réutilisation des seuils `surveillance/constants.py`, besoin différent).
2. ✅ **Seuil du 2ᵉ tableau (liste à investiguer)** : option (a) retenue — tous les produits
   `> 7 jours` (attention + critique), avec une colonne « statut » dans l'export pour que le
   superviseur/l'agent puisse trier.
3. ✅ **Colonne Valorisation (chantier A)** : valeur immobilisée réelle
   (`quantite_restante × lot.prix_achat_unitaire`), comme proposé.
4. ❌ **Chantier C (axe BI « produits en circulation »)** : **abandonné pour l'instant**.
   `direction/suivi-distributions/` (chantier A), une fois enrichi, couvre déjà le besoin de
   valorisation du stock en circulation — dupliquer cette information dans le BI serait une
   surcharge sans valeur ajoutée à ce stade. Le mart `fct_stock_agent.sql` reste inchangé ; le
   constat C.1 (ci-dessous) reste documenté au cas où le besoin BI redevienne pertinent plus tard
   (ex. si la direction veut suivre la tendance dans le temps plutôt qu'un instantané).
5. ✅ **Export chantier A** : les deux formats, Excel (`openpyxl`) et PDF (`reportlab`), comme
   `ExportVentesExcelView`/`ExportVentesPDFView` déjà en place.

---

## Chantier A — `direction/suivi-distributions/`

### Tâches

1. **Vue** (`direction/views.py::suivi_distributions`)
   - Défaut `statut = request.GET.get("statut", "restant")` si `statut` n'est pas explicitement
     dans `request.GET` (distinguer « absent » de `""` choisi via le select) — sinon le premier
     chargement de page ne pourra plus jamais revenir à la vue non filtrée par simple clic sur
     « Filtrer » avec statut vide.
   - Annoter `jours_ecoules` (ou calculer côté template via `timesince`/soustraction explicite) et
     `valeur_immobilisee = F("restant") * F("lot__prix_achat_unitaire")` sur le queryset existant.
   - Calculer le statut couleur (`ok` / `attention` / `critique`) en fonction de D1 — soit via
     `Case/When` SQL, soit en propriété Python sur les lignes de `page_obj` (volume déjà paginé à
     20/page, pas de souci de perf).
2. **Template** (`suivi_distributions.html`)
   - Ajouter l'option « Tous » au `<select name="statut">`, la marquer `selected` quand
     `request.GET.statut` vaut explicitly `""`/`tous`, sinon `restant` par défaut au 1ᵉʳ chargement.
   - Colonne Valorisation (4ᵉ colonne) : retirer `d.prix_detail`/« PRIX VENTE VARIABLE », afficher
     la valeur immobilisée (D3) pour toutes les lignes en circulation (plus de branchement
     conditionnel par `type_agent`, qui n'avait de sens que pour le prix de vente).
   - Remplacer le texte ambre systématique (A.2) par un badge de statut réel : aucune couleur si
     `< 7 j`, orange/attention si `7-13 j`, rouge/critique si `≥ 14 j` (bornes D1).
3. **Nouveau tableau « Produits à investiguer »**
   - Nouvelle vue (ou section de la même vue si le volume reste faible — à trancher selon perf
     réelle) listant les lignes `restant > 0` au-delà du seuil D2, triées par ancienneté
     décroissante. Colonnes utiles à un superviseur sur le terrain : produit, agent, superviseur,
     date de sortie, ancienneté, quantité restante, valeur immobilisée.
   - Boutons export Excel/PDF (D5) sur ce tableau filtré (mêmes filtres actifs que la page, comme
     `ExportVentesExcelView` le fait pour `direction/ventes`).
4. **Constantes** : ajouter `SEUIL_ATTENTION_JOURS`/`SEUIL_CRITIQUE_JOURS` (D1) dans un module
   dédié (`direction/constants.py` si absent, sinon en tête de `direction/views.py` à côté de
   `DATE_DEBUT_SUIVI_TERRAIN`) — jamais en dur dans le template ni la vue.

---

## Chantier B — `direction/direction/ventes`

### Tâches

1. `direction/services/vente_analyses.py::filter_ventes` : ajouter `agent__superviseur`,
   `agent__superviseur__user` au `select_related`.
2. `liste_ventes_admin.html:374-381` : sous le nom de l'agent, ajouter
   `<span class="text-[10px] text-gray-400">{{ vente.agent.superviseur.full_name|default:"—" }}</span>`
   (gérer le cas `superviseur=None` — agents sans superviseur assigné, si le cas existe en base).
3. Vérifier si `ExportVentesExcelView`/`ExportVentesPDFView` doivent aussi porter le superviseur
   en colonne (cohérence de la donnée exportée avec l'écran) — à confirmer avec mdmaiga, pas
   demandé explicitement mais probable oubli sinon.

---

## Chantier C — BI : axe « Produits en circulation » — ❌ abandonné (décision 4)

Non réalisé dans ce sprint — cf. Décision 4. Le constat C.1 (§ Constat plus haut) reste dans ce
fichier comme référence si le besoin redevient pertinent (ex. suivi de tendance dans le temps,
que `direction/suivi-distributions/` ne fait pas puisqu'il montre un instantané courant). Si
repris un jour, prévoir un nouveau sprint dédié plutôt que de rouvrir celui-ci.

---

## Documentation à mettre à jour (toutes apps concernées, cf. CLAUDE.md § Après avoir codé)

- `direction/APP_DIRECTION.MD` (si présent — à vérifier) : nouveau comportement filtre par défaut,
  nouveau tableau d'investigation, export associé, ajout superviseur sur `direction/ventes`.
- `docs/features/` : pas de fichier dédié `direction` identifié à ce jour — à créer si l'app en
  est dépourvue (seul `app_surveillance.md` existe actuellement dans `docs/features/`), ou statuer
  que `APP_DIRECTION.MD` en tient déjà lieu.

---

## Definition of Done

**Chantier A**
- ✅ Premier chargement de `suivi-distributions/` sans paramètre → filtré sur « en circulation »
  par défaut ; une option « Tous les statuts » explicite permet de revenir à la vue non filtrée
  (implémenté avec une valeur `tous` dédiée plutôt qu'une chaîne vide ambiguë — plus robuste que
  la piste envisagée dans les tâches ci-dessus).
- ✅ Colonne Valorisation : plus aucune occurrence de « None FCFA » ; affiche la valeur immobilisée
  réelle (`quantite_restante × lot.prix_achat_unitaire`).
- ✅ Indicateur de couleur basé sur un seuil de jours réel (7 j / 14 j), plus de condition toujours
  vraie.
- ✅ Tableau « Produits à investiguer » : liste les lignes en circulation > 7 j (décision 2),
  exportable en Excel et PDF, mêmes filtres actifs que la page (affichage plafonné à 100 lignes,
  export non plafonné).
- ✅ Vérifié sur données réelles (base locale à jour de la prod, cf. § Vérification ci-dessous) et
  par tests automatisés (< 7 j neutre, 7-13 j attention, ≥ 14 j critique).

**Chantier B**
- ✅ Nom du superviseur visible sous le nom de l'agent sur `direction/ventes`, sans requête N+1
  supplémentaire (vérifié : `select_related` ajouté, 3 requêtes `core_agent` sur toute la page,
  pas de croissance avec le nombre de lignes — le N+1 constaté sur la page, 264 requêtes
  `core_fournisseur`, est préexistant et hors périmètre de ce sprint).

**Chantier C** — hors périmètre (décision 4), rien à livrer.

**Transverse**
- ✅ `python manage.py test direction` vert (20/20, dont 8 nouveaux tests) ; suite complète du
  projet vérifiée (`python manage.py test`, 125/125).
- ✅ `APP_DIRECTION.MD` mis à jour dans la même session que le code (§ 6 et nouvelle § 7).

---

## Vérification (17/09/2026)

- Rendu manuel sur base locale à jour de la prod (`runserver` + `curl`) : plus de « None FCFA »,
  badges « À SURVEILLER »/« À INVESTIGUER » corrects sur données réelles (ex. produits à 33 et
  50 jours de circulation, tous deux correctement classés « critique »).
- Exports Excel (12 Ko) et PDF (19 Ko) générés sans erreur sur 137 lignes réelles à investiguer.
- `direction/tests.py` : `SuiviDistributionsProduitsEnCirculationTests` (7 tests),
  `VentesSuperviseurAffichageTests` (1 test).
- Bug trouvé et corrigé pendant les tests : `StockInvestigationExportService` plantait sur un lot
  sans fournisseur (`lot.fournisseur` nullable) — non observé en donnée réelle mais réel sur le
  modèle (`LotEntrepot.fournisseur`), corrigé par un garde-fou (`if d.lot.fournisseur else "—"`).
  Le tableau HTML de la page (comme la table 1 déjà existante) ne porte pas ce même garde-fou —
  laissé identique au comportement préexistant de la table 1, cohérent mais à surveiller si un lot
  sans fournisseur apparaît un jour en circulation réelle.

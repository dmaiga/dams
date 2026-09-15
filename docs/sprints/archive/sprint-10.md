# Sprint 10 — Lisibilité des pertes déclarées à la vente + impact sur l'incentive agent

**Statut** : ✅ terminé (18/08/2026) — Constat 1 (bouton cliquable), Constat 2 (déduction des
pertes sur l'incentive, Django + dbt, migration `0117_perte_kilo_perdu_incentive`, tests
`paie/tests.py`), et deux ajouts faits en cours de sprint :

- Colonne Quantité de `liste_ventes_admin.html` : kg net facturable affiché (brut barré → net en
  évidence + badge "-X kg perdus"), via `Vente.kilo_perdu`/`Vente.kilo_net` (`core/models.py`).
- Deux bugs trouvés et corrigés en testant le sprint en conditions réelles (mdmaiga, 18/08/2026) :
  1. `enregistrer_vente.html` perdait la sélection du produit distribué après toute soumission
     invalide (le select est peuplé par JS, jamais re-rendu par Django) — corrigé en rechargeant
     et restaurant la sélection au chargement de page.
  2. `direction/services/product_analysis_service.py` (fiche produit, KPI globaux, dashboard
     produits) ne sommait que `Perte.quantite_perdue`, qui reste à 0 pour une perte déclarée sur un
     produit conditionné — les pertes de ce type étaient invisibles sur ces écrans alors qu'elles
     réduisaient bien l'incentive de l'agent. Corrigé avec
     `Coalesce(kilo_perdu_incentive, quantite_perdue)` sur les 4 agrégations concernées.

Reste à faire manuellement en déploiement : `migrate` + `dbt run` sur `stg_pertes`/`fct_salaires`.

## Contexte

Deux sujets remontés dans la continuité l'un de l'autre : le premier rend visible les pertes
déclarées sur une vente, le second corrige le fait que ces pertes, une fois visibles, n'ont
aujourd'hui aucun effet sur l'incentive payé à l'agent qui les a occasionnées.

---

## Constat 1 — Le hover "perte" ne se déclenche pas correctement sur la liste des ventes

**Fichier** : `direction/templates/direction/analyses/ventes/liste_ventes_admin.html:389-393`

```html
{% if vente.commentaire_perte %}
<i class="fas fa-circle-info ..." title="Perte : {{ vente.commentaire_perte }}"></i>
{% elif vente.pertes_liees.all %}
<i class="fas fa-circle-info ..." title="Perte ({{ vente.pertes_liees.all.0.quantite_perdue }} kg) : {{ vente.pertes_liees.all.0.description }}"></i>
{% endif %}
```

### Diagnostic

Ce n'est pas un tooltip Bootstrap : c'est l'attribut `title` natif du navigateur. Cette page hérite
de `direction/templates/base_admin.html`, un layout Tailwind/DaisyUI qui ne charge ni le CSS ni le
JS de Bootstrap. Ailleurs dans l'app (ex. `core/templates/core/ventes/detail_dette.html:255` avec
`data-bs-toggle="tooltip"` et son initialisation `new bootstrap.Tooltip(...)` sur `DOMContentLoaded`
lignes 407-411), les tooltips sont de vrais tooltips Bootstrap — cette page-ci utilise un mécanisme
différent et dégradé.

Conséquences concrètes :
- **Aucun déclenchement tactile fiable** : le `title` natif ne réagit pas au survol sur tablette
  (les superviseurs terrain travaillent souvent sur tablette), seulement à un appui long, peu
  intuitif et peu découvrable.
- **Zone de survol minuscule** : l'icône (`font-size: 0.65rem`, `padding: 2px`, ≈ 12px) est
  difficile à cibler précisément à la souris comme au doigt.
- Le modèle sous-jacent est correct et déjà bien peuplé (`core/models.py:1685`
  `Vente.commentaire_perte` pour les produits à l'unité ; `core/models.py:1254-1261`
  `Perte.vente`/`Perte.quantite_perdue` pour les produits vrac, remplis par `vente/forms.py:284-296`)
  — rien à corriger côté données, uniquement côté affichage.

### Décision actée (mdmaiga, 18/08/2026)

Remplacer le `title` natif par un point/icône **cliquable** affichant le message de perte — cohérent
avec l'usage tactile réel de l'app, plutôt qu'un hover qui ne se déclenche pas de façon fiable au
doigt. Choisir le mécanisme le plus simple et cohérent avec l'existant du template :

- Si Bootstrap est déjà chargé côté `base_admin.html` (à vérifier au moment de coder — l'exploration
  initiale ne l'a pas trouvé) : réutiliser un `data-bs-toggle="popover"`/`"tooltip"` avec
  `trigger: 'click'` plutôt que `'hover'`, à l'identique du pattern de `detail_dette.html`.
- Sinon (cas le plus probable vu que `base_admin.html` est Tailwind/DaisyUI) : un petit composant
  local en CSS/Tailwind (`group` + `group-focus`/état contrôlé par un clic JS minimal, ou l'attribut
  natif `<details>`/`<summary>` pour un popover 100% sans JS) qui affiche/masque le message au clic
  sur l'icône, avec fermeture au clic extérieur. Pas besoin d'introduire une dépendance JS
  supplémentaire pour ce seul usage.
- Agrandir la zone cliquable (actuellement ~12px) à une taille tactile raisonnable (44px de zone
  cliquable minimum recommandée, l'icône visuelle peut rester petite avec du padding).

### Tâches

1. **Template** — `direction/templates/direction/analyses/ventes/liste_ventes_admin.html:389-393` :
   remplacer l'attribut `title` par le composant cliquable retenu, pour les deux branches
   (`commentaire_perte` produit à l'unité, `pertes_liees` produit vrac).
2. **Vérifier** si d'autres templates de l'app affichent la même information de perte avec le même
   pattern `title` dégradé (grep `commentaire_perte`/`pertes_liees` sur `**/*.html`) — corriger au
   même endroit si un doublon existe, pour ne pas laisser un deuxième hover cassé ailleurs.
3. **Test manuel** : vérifier le comportement au clic sur mobile/tablette (émulateur navigateur ou
   device réel) et à la souris (desktop), y compris la fermeture du popover.

### Definition of Done

- Le message de perte est visible et lisible au clic (souris et tactile) sur `liste_ventes_admin.html`.
- Aucune dépendance JS lourde ajoutée pour ce seul besoin si une solution CSS pure suffit.
- `vente/APP_VENTE.md` mis à jour si le pattern d'affichage des pertes y est documenté.

---

## Constat 2 — Les kilos perdus n'affectent pas l'incentive de l'agent

### Flux actuel

La perte est déclarée par le **superviseur**, au moment où il enregistre la vente de son agent,
via `VenteForm` (`vente/forms.py:160-178`, `superviseur` passé à `__init__` ligne 201) : case à
cocher "Il y a eu une perte sur ce produit", puis `quantite_perdue` (kg, produit vrac) ou
`commentaire_perte` (produit à l'unité). À la sauvegarde (`vente/forms.py:265-298`), un
`Perte` est créé (`detail_distribution=..., vente=vente, quantite_perdue=...`) pour le vrac ; pour
l'unité, seul `Vente.commentaire_perte` est renseigné (pas de quantité chiffrée exploitable).

Le calcul de l'incentive (`paie/services/salaire_calculator.py::calcul_salaire_mamy`, lignes
53-120) agrège `kilo_total` uniquement à partir de `Vente.quantite × poids_unitaire_kg` (lignes
72-89), puis applique `incentive = kilo_total * incentive_par_kg` (ligne 91,
`RegleSalaire.incentive_par_kg` = **25 FCFA/kg**, initialisé dans
`direction/management/commands/init_regles_remuneration.py:16`). **Les `Perte` liées ne sont jamais
soustraites** : un agent qui vend 20 kg et fait déclarer 5 kg de perte par son superviseur est payé
sur 20 kg, alors que mdmaiga veut qu'il soit payé sur `(20 - 5) × 25`.

### Ce que la correction implique

Dans `calcul_salaire_mamy`, en plus de `kilo_total` (kg vendus), calculer un `kilo_perdu` = somme des
`Perte.quantite_perdue` dont `Perte.vente` appartient au queryset `ventes` déjà filtré (même agent,
même période, `est_supprime=False`) :

```python
kilo_perdu = Perte.objects.filter(
    vente__in=ventes
).aggregate(total=Coalesce(Sum("kilo_perdu_incentive"), Decimal("0.00")))["total"]

kilo_facturable = kilo_total - kilo_perdu
incentive = kilo_facturable * incentive_par_kg
```

`kilo_total` sert **aussi** au seuil du salaire de base (`>= 750 kg` → 20 000, sinon 10 000, lignes
96-99). Décision actée : ce seuil se lit désormais sur `kilo_facturable` (net des pertes), pas sur
`kilo_total` brut — remplacer la condition ligne 96 par `if kilo_facturable >= Decimal("750")`.

### Sous-constat — Les produits conditionnés (sac/carton) ne peuvent pas déclarer de perte en kg aujourd'hui

`Perte.quantite_perdue` n'est aujourd'hui alimenté que pour les produits **vrac**
(`Produit.poids_unitaire_kg` nul) : la `clean()` de `VenteForm` (ligne 260) exige un simple
commentaire texte — pas de quantité chiffrée — dès que `poids_unitaire_kg` est renseigné (produit
conditionné, ex. un sac d'oignon de 25 kg). Or un agent peut très bien vendre "1 sac" tout en
signalant une perte partielle à l'intérieur de ce sac (ex. 5 kg abîmés sur les 25 kg), sans que ça
corresponde à la perte d'un sac entier.

**Piège identifié en cadrant ce sprint** : `DetailDistribution.quantite_restante_calculee`
(`core/models.py:1539-1557`) soustrait `Perte.quantite_perdue` **dans la même unité que
`DetailDistribution.quantite`** — kg pour un produit vrac, mais **nombre de sacs/cartons** pour un
produit conditionné. Réutiliser tel quel `Perte.quantite_perdue` pour y stocker des kg perdus sur un
produit conditionné casserait donc ce calcul (ça soustrairait "5" du stock compté en sacs, au lieu
de 5 kg).

**Décision actée (mdmaiga, 18/08/2026)** : un **nouveau champ dédié**, distinct de
`Perte.quantite_perdue`, sert uniquement à l'incentive et ne touche jamais le décompte de stock. Le
sac/carton continue d'être compté normalement comme vendu/distribué (une unité), qu'il y ait ou non
une perte partielle déclarée dessus.

- **Modèle** — `core/models.py` : ajouter sur `Perte` un champ `kilo_perdu_incentive` (Decimal,
  nullable), toujours exprimé en kg quel que soit le type de produit :
  - Produit vrac : continuer de renseigner `quantite_perdue` comme aujourd'hui (décrémente le
    stock) ; `kilo_perdu_incentive` peut simplement recevoir la même valeur (les deux coïncident
    puisque l'unité de stock est déjà le kg), pour que `paie` n'ait qu'un seul champ à lire quel que
    soit le type de produit.
  - Produit conditionné : ne **jamais** toucher `quantite_perdue` (le sac reste décompté comme une
    unité entière vendue) ; renseigner uniquement `kilo_perdu_incentive` avec la quantité en kg
    saisie par le superviseur.
- **`vente/forms.py`** — `VenteForm` : afficher/activer le champ kg perdus pour **tous** les
  produits dès que `declaration_perte` est coché, pas seulement pour le vrac (`is_vrac`). Séparer
  clairement les deux logiques de validation :
  - Vrac (comportement actuel, inchangé) : `quantite_perdue` obligatoire, borné par
    `quantite_restante_calculee` (ligne 255).
  - Conditionné (nouveau) : `kilo_perdu_incentive` obligatoire si perte déclarée, borné par le poids
    nominal du lot vendu (`quantite_vendue × poids_unitaire_kg`) — une perte ne peut pas dépasser le
    poids du sac/carton effectivement vendu sur cette ligne.
- **`paie/services/salaire_calculator.py`** — agréger `Sum("kilo_perdu_incentive")` (et non
  `quantite_perdue`) pour calculer `kilo_perdu`, afin que le calcul fonctionne uniformément pour le
  vrac comme pour le conditionné sans lire deux champs différents selon le type de produit.

### Décisions actées (mdmaiga, 18/08/2026)

1. Le seuil de 750 kg du salaire fixe se calcule **après** déduction des pertes, c'est-à-dire sur
   `kilo_facturable` (kilo vendu − kilo perdu), pas sur `kilo_total` brut.
2. Application **non rétroactive** : le correctif s'applique aux calculs de paie effectués à partir
   de la mise en production. Les paies déjà émises pour des pertes déjà déclarées ne sont pas
   recalculées.

### Tâches (une fois la décision actée)

1. **`core/models.py`** — `Perte` : ajouter le champ `kilo_perdu_incentive` (Decimal, nullable) +
   migration. Adapter `vente/forms.py::VenteForm.save()` (lignes 265-298) pour le peupler dans les
   deux cas (vrac : mirroir de `quantite_perdue` ; conditionné : valeur saisie dédiée, sans toucher
   `quantite_perdue`).
2. **`vente/forms.py`** — `VenteForm` : nouveau champ de saisie kg perdus actif pour les produits
   conditionnés (cf. sous-constat ci-dessus), avec sa propre validation bornée au poids nominal
   vendu sur la ligne.
3. **`paie/services/salaire_calculator.py`** — `calcul_salaire_mamy` : agrégation
   `Sum("kilo_perdu_incentive")` sur les `Perte` liées aux `ventes` déjà filtrées, déduction avant
   application du taux, et seuil des 750 kg basé sur `kilo_facturable` (voir ci-dessus). Vérifier
   aussi `calcul_salaire_gros` (lignes 125+) : si le même mécanisme de perte s'applique aux agents
   gros (cartons plutôt que kg), traiter en cohérence ou documenter explicitement pourquoi ce type
   d'agent n'est pas concerné.
4. Exposer `kilo_perdu` (et `kilo_facturable`) dans le dict retourné par `calcul_salaire_mamy`, pour
   que l'écran de fiche de paie puisse afficher le détail du calcul à l'agent/superviseur
   (transparence sur pourquoi l'incentive est inférieure au brut vendu).
5. **Test de non-régression** ciblé : un agent avec des ventes vrac sans perte (incentive inchangée),
   un agent avec ventes vrac + perte partielle, et un agent avec une vente de produit conditionné
   (sac) + perte partielle en kg déclarée sur ce sac — incentive réduite du montant attendu dans les
   deux cas, sans que le décompte de stock (`quantite_restante_calculee`) ne soit affecté pour le cas
   conditionné.
6. **Couche BI/dbt** (`dbt_bi/`) — `fct_salaires.sql` **duplique déjà** le calcul de
   `calcul_salaire_mamy` (commentaire explicite dans le fichier renvoyant à
   `paie/services/salaire_calculator.py`). Son CTE `kg_par_salaire` calcule un `kg_realise` brut
   (uniquement `fct_ventes`, sans déduction des pertes) et applique dessus le seuil des 750 kg pour
   recalculer `fixe_recalcule`. Sans mise à jour, ce seuil dbt divergera du salaire réellement versé
   dès que Django applique la déduction nette. À faire en cohérence avec les décisions actées :
   - `dbt_bi/models/staging/stg_pertes.sql` : exposer le nouveau champ `kilo_perdu_incentive` (pas
     seulement `quantite_perdue`, qui reste un concept de décompte de stock, pas d'incentive).
   - `dbt_bi/models/marts/fct_salaires.sql` : joindre les pertes par agent/période et soustraire
     `Sum(kilo_perdu_incentive)` de `kg_realise` **avant** la comparaison au seuil 750 kg dans
     `fixe_recalcule`, pour rester aligné sur `kilo_facturable` côté Django.
   - Le montant `incentive` lui-même n'a pas besoin d'être recalculé dans dbt (il est lu tel quel
     depuis `stg_salaires`, donc déjà correct dès que Django le calcule bien) — seul le
     `salaire_base`/seuil 750 kg recalculé côté dbt est concerné.
   - Dashboards à revérifier après ce correctif dbt : **Dashboard 1 "Santé Globale"**
     (`vw_rentabilite_globale`, coût salaires) et **Dashboard 3 "Agent"** (`vw_performance_agent`,
     incentive/marge agent) — tous deux lisent `fct_salaires`.
   - Respecter la même décision de non-rétroactivité (point 2 ci-dessus) : le modèle dbt reflète les
     nouvelles paies calculées à partir de la mise en production, pas un recalcul historique.

### Definition of Done

- `calcul_salaire_mamy` déduit les kilos perdus déclarés sur la période avant d'appliquer le taux
  d'incentive.
- Le comportement du seuil 750 kg est conforme à la décision actée (point 1 ci-dessus), pas laissé
  au hasard de l'implémentation, **côté Django comme côté dbt** (`fct_salaires.sql`).
- `paie/APP_PAIE.md` mis à jour pour documenter que l'incentive terrain se calcule désormais sur le
  kilo net (vendu moins perdu), avec la formule et la référence à `Perte.kilo_perdu_incentive`.
- Si applicable, `vente/APP_VENTE.md` mentionne que la perte déclarée à la vente a un effet direct
  sur la paie de l'agent (pas seulement sur le suivi de stock), pour que quiconque modifie
  `VenteForm` à l'avenir sache que ce champ est désormais lu par `paie`.
- `dbt_bi/models/marts/fct_salaires.sql` recalcule le seuil 750 kg sur le kilo net, cohérent avec
  `calcul_salaire_mamy` — plus de divergence possible entre le salaire versé et les KPI des
  Dashboards 1 et 3.

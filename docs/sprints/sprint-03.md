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
6. ~~**`VersementBancaire.superviseur`** — marqué "⛔ à déprécier" dans le modèle, mais c'est en réalité le **seul champ qui indique de quel superviseur provient la recette versée**... `finance/` continue de s'appuyer dessus pour l'attribution par superviseur.~~ **⚠️ SUPERSÉDÉE par la décision n°13** — c'était une erreur d'interprétation. `superviseur` et `effectue_par` jouent le **même rôle** ("qui a effectué l'action") ; `superviseur` est simplement l'ancien champ, conservé pour ne pas casser l'historique, mais jamais une attribution de source. Voir décision n°13.
7. **`peut_faire_depense`** : nouveau champ booléen sur `Agent` (pas dérivé du rôle), pour permettre plus tard à un superviseur de saisir ses propres dépenses. `Depense.effectue_par` n'a déjà aucune restriction de `type_agent` au niveau modèle — seule la vue doit vérifier ce flag.
8. ~~**`RecouvrementSuperviseur` ne fait jamais baisser le solde**~~ **⚠️ SUPERSÉDÉE par la décision n°13** — conclusion tirée d'un test réel (un recouvrement saisi depuis l'admin n'apparaissait pas dans le solde), mais mauvais diagnostic : le problème n'était pas que `RecouvrementSuperviseur` ne devait jamais compter, c'est qu'il existe **deux soldes distincts** et que `RecouvrementSuperviseur` fait baisser celui du superviseur (pas la caisse globale, que seul `VersementBancaire` fait baisser). Voir décision n°13.
9. **`core.forms.VersementForm.save()` étendu, pas dupliqué.** Il refusait tout `rot` dont `est_rot` était faux (`ValueError`), ce qui bloquait explicitement mdmaiga. Condition élargie à `rot.est_rot or rot.est_direction`, sans changement de comportement pour le flux ROT existant (`core/views.py::creer_versement`).
10. **Simplification du flux quotidien (retour terrain) : une action groupée remplace les deux étapes manuelles.** Faire un recouvrement puis un versement séparément, superviseur par superviseur, était jugé trop lourd pour l'usage réel de mdmaiga. `finance/` expose donc une vue unique (formset) qui traite tous les superviseurs actifs en une soumission — voir US-07 et tâche 7 ci-dessous. Les vues individuelles (`recouvrer_superviseur`, `creer_versement`) restent en code pour une correction ponctuelle, mais ne sont plus liées dans l'UI, de même que `creer_depense` (mdmaiga ne compte pas suivre les dépenses pour l'instant).
11. ~~**Bug corrigé : `date_debut` ne doit jamais être un paramètre libre de `calculer_solde_superviseur`... corrigé en ancrant `date_debut` sur `_borne_ouverture(superviseur)` (dernière `ClotureMensuelle`).**~~ **⚠️ SUPERSÉDÉE par la décision n°13** — le diagnostic du bug (un même `VersementBancaire` recompté deux fois selon la fenêtre) était juste, mais la correction proposée (ancrer sur la dernière clôture) s'est révélée elle-même bâtie sur le mauvais modèle (décision n°6, superédée). La correction définitive supprime `ClotureMensuelle` du calcul entièrement plutôt que de s'y ancrer.
12. ~~**Ajout d'une action "Clôturer"** — `finance.services.cloturer_superviseur()` crée/actualise une `ClotureMensuelle`...~~ **⚠️ RETIRÉE par la décision n°13** — construite pour résorber le problème de la décision n°11, elle-même abandonnée. mdmaiga a confirmé vouloir éviter toute dépendance à `ClotureMensuelle`/`cloturer_mois` pour `finance/`, justement pour ne pas hériter de dette technique de l'ancien système. Les vues `cloturer_tous`/`cloturer_un_superviseur` et `services.cloturer_superviseur()` ont été retirées du code.
13. **Modèle à deux niveaux, calcul 100% dynamique, sans clôture (décision définitive)** — mdmaiga a corrigé une erreur de conception fondamentale : `VersementBancaire.superviseur` et `effectue_par` jouent le **même rôle** ("qui a effectué l'action"), `superviseur` étant l'ancien champ (avant l'ajout du rôle ROT) conservé pour ne pas casser l'historique — **ce n'est pas** une attribution de source. Le flux réel : le superviseur détient son cash jusqu'à ce qu'un acteur admin le recouvre (`RecouvrementSuperviseur`) — à cet instant l'argent est **mutualisé**, et les dépenses/versements qui suivent (`Depense`/`VersementBancaire`) sont des événements de la **caisse globale**, plus attribuables à un superviseur précis. Conséquences :
    - **`solde_superviseur(superviseur)`** = `Recouvrement` (encaissé) − `Depense` **personnelle** (si `effectue_par` est ce superviseur, `peut_faire_depense`) − `RecouvrementSuperviseur` (déjà remis). Jamais de `VersementBancaire` dans ce calcul.
    - **`solde_caisse_globale()`** = `RecouvrementSuperviseur` (total reçu, tous superviseurs) − `Depense` (effectuée par un ROT/direction) − `VersementBancaire.montant_vente`. Jamais filtré par `superviseur`. Formule identique à `Agent.solde_rot` (déjà correcte, déjà dans la table de contexte comme "correct et à jour, mais scope ROT") — `finance/` la généralise pour la Direction.
    - **Aucun solde d'ouverture, aucune `ClotureMensuelle`.** Calcul purement dynamique sur tout l'historique de `Recouvrement`/`RecouvrementSuperviseur`/`Depense`/`VersementBancaire`, sans borne de date basse. Choix explicite de mdmaiga : éviter toute dette technique envers l'ancien système plutôt que de traiter un solde de clôture (potentiellement lui-même faux) comme une base de départ fiable.
    - **Anomalie découverte sur les données de test** : pour les 3 superviseurs, le total `RecouvrementSuperviseur` dépasse le total `Recouvrement` (soldes négatifs, jusqu'à -10M FCFA), et la caisse globale aussi (-22M FCFA) — mathématiquement impossible dans un système cohérent. Diagnostiqué comme un problème de **données de dev/test incohérentes**, pas un bug de la formule ; volontairement non masqué (pas de plancher à zéro).
14. ~~**Somme sur tout l'historique, sans borne basse**~~ **⚠️ REVENUE par mdmaiga (décision n°14, définitive)** — après avoir vu l'anomalie de la décision n°13 en usage réel, mdmaiga a préféré ne pas remonter dans un historique jugé incohérent (ancien paradigme superviseur, introduction tardive du rôle ROT faussant les rapprochements). `DATE_DEBUT_FINANCE = date(2026, 7, 1)` (constante de `finance/services.py`) devient la borne basse de **tous** les calculs (`solde_superviseur`, `solde_caisse_globale`) et de la fenêtre de consultation des mouvements (`detail_solde_superviseur`) — tout ce qui précède est ignoré, sans tentative de le corriger ou de le récupérer.

---

## Formules officielles (`finance/services.py`)

**Version définitive** (décision n°13 — modèle à deux niveaux ; décision n°14 — coupure au 01/07/2026) :

```python
DATE_DEBUT_FINANCE = date(2026, 7, 1)  # historique antérieur ignoré (décision n°14)


def solde_superviseur(superviseur, date_fin=None):
    """Cash détenu par CE superviseur, pas encore remis, depuis DATE_DEBUT_FINANCE."""
    date_fin = date_fin or timezone.localdate()

    encaissements = Recouvrement.objects.filter(
        superviseur=superviseur,
        date_recouvrement__date__gte=DATE_DEBUT_FINANCE, date_recouvrement__date__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant_recouvre"), Decimal("0.00")))["total"]

    depenses_perso = Depense.objects.filter(
        effectue_par=superviseur,
        date_depense__gte=DATE_DEBUT_FINANCE, date_depense__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    deja_remis = RecouvrementSuperviseur.objects.filter(
        superviseur=superviseur,
        date_recouvrement__date__gte=DATE_DEBUT_FINANCE, date_recouvrement__date__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    return encaissements - depenses_perso - deja_remis


def solde_caisse_globale(date_fin=None):
    """Cash détenu par les acteurs admin (ROT/direction) après mutualisation, depuis DATE_DEBUT_FINANCE."""
    date_fin = date_fin or timezone.localdate()

    recouvre = RecouvrementSuperviseur.objects.filter(
        date_recouvrement__date__gte=DATE_DEBUT_FINANCE, date_recouvrement__date__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    depenses = Depense.objects.filter(
        effectue_par__type_agent__in=['rot', 'direction'],
        date_depense__gte=DATE_DEBUT_FINANCE, date_depense__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant"), Decimal("0.00")))["total"]

    versements = VersementBancaire.objects.filter(
        date_versement_reelle__date__gte=DATE_DEBUT_FINANCE, date_versement_reelle__date__lte=date_fin
    ).aggregate(total=Coalesce(Sum("montant_vente"), Decimal("0.00")))["total"]

    return recouvre - depenses - versements
```

Aucune des deux fonctions n'accepte de `date_debut` — l'agrégation part toujours de `DATE_DEBUT_FINANCE` (`2026-07-01`), constante non paramétrable. Seul `date_fin` est un paramètre ("solde à la date du..."). La fenêtre de consultation des mouvements (`detail_solde_superviseur`, `_get_periode_mouvements`) est bornée de la même façon (`max(mvt_debut, DATE_DEBUT_FINANCE)`).

---

## User stories

**US-01 — Vue d'ensemble des soldes**
En tant que mdmaiga, je veux voir en un coup d'œil le solde actuel de chaque superviseur (recette non encore versée), pour savoir qui doit encore remettre de l'argent.

**US-02 — Recouvrer la recette d'un superviseur**
En tant que mdmaiga, je veux enregistrer que tel superviseur m'a remis sa recette de la veille (`RecouvrementSuperviseur`), pour que **son** solde individuel diminue d'autant (l'argent devient mutualisé).

**US-03 — Enregistrer un versement bancaire**
En tant que mdmaiga, je veux enregistrer le versement réel (montant vente + montant hors-vente séparément, reçu à l'appui), pour que la **caisse globale** diminue du montant vente uniquement — ce versement ne concerne plus un superviseur en particulier (décision n°13).

**US-04 — Enregistrer une dépense**
En tant que mdmaiga (ou un superviseur avec `peut_faire_depense`), je veux enregistrer une dépense datée, indépendamment de tout versement, pour qu'elle réduise immédiatement le solde disponible.

**US-05 — Historique / détail par superviseur**
En tant que mdmaiga, je veux voir le détail des mouvements (encaissements, dépenses, versements) d'un superviseur sur une période, pour comprendre comment son solde a été obtenu.

**US-06 — Alerte montant manquant**
En tant que mdmaiga, je veux voir signalés les superviseurs dont le solde dépasse un seuil sans versement récent, pour savoir qui appeler.

**US-07 — Recouvrement + versement groupé (ajoutée en cours de sprint)**
En tant que mdmaiga, je veux traiter tous les superviseurs en une seule action (montant recouvré préempli avec le solde courant, apport hors vente optionnel, reçu à joindre), plutôt que de répéter US-02 puis US-03 superviseur par superviseur. Une ligne laissée à 0 (superviseur sans recette sur la période) n'est simplement pas traitée. Devient l'action principale au quotidien ; US-02/US-03 restent disponibles par URL directe pour une correction ponctuelle sur un seul superviseur.

~~**US-08 — Clôturer un ou tous les superviseurs**~~ **retirée (décision n°13)** — l'action de clôture répondait à un problème (solde d'ouverture figé) causé par un modèle depuis abandonné. Le calcul dynamique sans clôture rend cette US sans objet.

---

## Périmètre de l'app `finance/`

| Vue | URL | Acteur | Exposée dans l'UI | Description |
|-----|-----|--------|--------------------|-------------|
| `dashboard_finance` | `/finance/` | direction (mdmaiga) | Oui | Caisse globale + liste des soldes superviseurs (à la date du jour, ou à une date passée via `?date_fin=`), badge alerte si seuil dépassé |
| `detail_solde_superviseur` | `/finance/superviseur/<pk>/` | direction | Oui | Solde du superviseur (dynamique, tout l'historique) + mouvements **paginés** (30/page) sur une fenêtre filtrable séparément |
| `recouvrement_versement_groupe` | `/finance/recouvrement-versement/` | direction | Oui — action principale | Formset multi-superviseurs : recouvrement + versement + reçu en une soumission (US-07) |
| `recouvrer_superviseur` | `/finance/recouvrer/<pk>/` | direction | **Non** | Formulaire `RecouvrementSuperviseur` — gardé pour correction ponctuelle |
| `creer_versement` | `/finance/versement/nouveau/` | direction | **Non** | Formulaire `VersementBancaire` (+ upload reçu `RecuVersement`) — idem |
| `creer_depense` | `/finance/depense/nouvelle/` | direction, ou agent avec `peut_faire_depense` | **Non** | Formulaire `Depense` — la saisie de dépenses n'est pas suivie pour l'instant |
| `historique_versements` | `/finance/versements/` | direction | **Non** | Liste complète (date sans heure) |
| `historique_depenses` | `/finance/depenses/` | direction | **Non** | Liste complète |

Les vues marquées "Non" restent en code (urls.py, views.py, templates) — seuls les liens de navigation ont été retirés, sur demande explicite (éviter les sous-actions redondantes maintenant que US-07 les couvre, et parce que le suivi des dépenses n'est pas prioritaire). Elles restent accessibles par URL directe.

Guard : `_acces_finance(agent) = agent.est_direction` — capacité, pas nom en dur, mais dans le template le menu reste conditionné comme le reste du backoffice (cohérent avec le pattern déjà en place dans `base_admin.html` pour "Surveillance").

**Ce que l'app ne fait PAS (pour ce sprint) :**
- Ne touche pas aux 5 propriétés `Agent.solde_*` existantes (décision n°3).
- Ne migre pas `agents/services/rot_dashboard_service.py`, `agents/services/superviseur_service.py`, `direction/services/cloture_service.py` ni `Agent.solde_rot` vers la nouvelle fonction — ils continuent de fonctionner tels quels. La migration progressive est un sprint futur.
- Ne construit pas de grand livre journalier persistant (décision n°2) ni de solde d'ouverture/clôture (décision n°13) — calcul 100% dynamique.
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

Contient `solde_superviseur(superviseur, date_fin=None)` et `solde_caisse_globale(date_fin=None)` (voir formules ci-dessus, version définitive — décision n°13) + `lister_soldes_superviseurs(date_fin=None)` qui applique la première à tous les superviseurs actifs pour alimenter le dashboard.

### 4. `finance/forms.py`

Réutilisation de l'existant plutôt que duplication (repéré avant d'écrire du code neuf) :

- `RecouvrementSuperviseurForm` : réexportée telle quelle depuis `agents.forms` (superviseur, montant, commentaire, date — déjà réutilisable, `.rot` est fixé par la vue appelante).
- `DepenseForm` : réexportée telle quelle depuis `core.forms` (`Depense.effectue_par` n'a aucune restriction modèle). `DepenseFinanceForm(DepenseForm)` ajoute juste un `agent_cible` optionnel pour que mdmaiga saisisse au nom d'un agent.
- `VersementBancaireForm` : **nouvelle**, sans champ `superviseur` (une version antérieure de ce sprint en ajoutait un par erreur — voir décision n°6, superédée). Champs : `montant_vente`, `montant_hors_vente`, `description`, `date_versement_reelle`, upload reçu(s) (`recus`/`recus_description` → `RecuVersement`). Sa `.save()` refusait `rot.est_direction` (voir décision n°9, corrigée dans `core.forms.VersementForm` lui-même plutôt que dupliquée).
- `LigneRecouvrementVersementForm` + `RecouvrementVersementFormSet` (`forms.formset_factory`) : une ligne par superviseur pour US-07 — `superviseur` (hidden), `montant`, `montant_hors_vente`, `recu`, tous optionnels sauf `superviseur`.

### 5. `finance/views.py`

Guard `_acces_finance(agent) = agent.est_direction`. Vue `creer_depense` élargie : `agent.est_direction or agent.peut_faire_depense`.

### 6. Templates

Héritent de **`base_admin.html`** (et non `base.html`) — c'est l'espace de mdmaiga. Entrée "Solde superviseurs" ajoutée dans le menu FINANCE existant de `base_admin.html`, sans remplacer "Versements"/"Dépenses" (vues `direction_*` non touchées).

Correction de surbrillance associée : le lien direction "Versements" (`versements_direction`) testait uniquement `'versement' in request.resolver_match.url_name`, ce qui l'activait aussi sur des pages `finance:*` dont l'`url_name` contient "versement" (ex. `historique_versements`) — les deux entrées de menu s'allumaient en même temps. Condition corrigée : `request.resolver_match.namespace != 'finance' and 'versement' in request.resolver_match.url_name`.

Dans les listes de mouvements (`detail_solde_superviseur.html`, `historique_versements.html`), l'heure a été retirée de l'affichage des dates (`d/m/Y` au lieu de `d/m/Y H:i`) — non pertinente pour une lecture quotidienne par jour.

### 7. Action groupée — `recouvrement_versement_groupe` (ajoutée en cours de sprint, US-07)

**Fichiers : `finance/forms.py`, `finance/views.py`, `finance/urls.py`, `finance/templates/finance/recouvrement_versement_groupe.html`**

- Formset (`RecouvrementVersementFormSet`) initialisé à partir de `lister_soldes_superviseurs()` (sans date — toujours le solde réel ancré) : une ligne par superviseur actif, `montant` préempli avec `solde_fin` si positif (sinon vide).
- À la soumission, pour chaque ligne dont `montant` est renseigné : création atomique (`transaction.atomic()`) d'un `RecouvrementSuperviseur` (traçabilité, décision n°8) **et** d'un `VersementBancaire` (+ `RecuVersement` si fichier joint) avec `effectue_par=agent`. Une ligne vide est ignorée sans erreur de validation.
- Redirige vers `dashboard_finance` avec un message récapitulant le nombre de superviseurs traités.

### 8. Modèle à deux niveaux, calcul dynamique définitif (décision n°13)

**Fichiers : `finance/services.py`, `finance/views.py`, `finance/forms.py`, `finance/urls.py`, tous les templates du dashboard/détail/action groupée**

- `finance/services.py` réécrit : `solde_superviseur`/`solde_caisse_globale` (voir formules ci-dessus) remplacent `calculer_solde_superviseur` ; suppression de `ClotureMensuelle`, `_borne_ouverture`, `cloturer_superviseur` et de tout ce qui en dépendait (vues `cloturer_tous`/`cloturer_un_superviseur`, boutons associés — retirés du code, pas juste de l'UI).
- `VersementBancaireForm` perd son champ `superviseur` ; `VersementBancaire.superviseur` n'est plus jamais renseigné par du code neuf (`recouvrement_versement_groupe`, `creer_versement`).
- `detail_solde_superviseur` : les mouvements affichés sont `Recouvrement` (+), `Depense` personnelle du superviseur (-) et `RecouvrementSuperviseur` (-, libellé "Remise") — plus de `VersementBancaire` (événement de la caisse globale, pas de ce superviseur).
- `dashboard.html` : nouveau bloc "Caisse globale" (`solde_caisse_globale`) au-dessus du tableau par superviseur ; colonnes renommées (Encaissements / Dépenses (perso) / Déjà remis / Reste à remettre).
- `historique_versements.html` : colonne "Superviseur" retirée (champ sans signification pour les nouveaux enregistrements).

---

## Invariants

- `montant_hors_vente` n'entre jamais dans `solde_caisse_globale`.
- Un seul flux d'encaissement (`Recouvrement`), jamais additionné avec `Vente(agent=superviseur)` en parallèle (source du bug actuel dans `cloture_service.py`).
- `VersementBancaire` et `Depense(effectue_par` = ROT/direction`)` sont des événements de la **caisse globale**, jamais attribués à un superviseur — ne jamais filtrer `VersementBancaire` par `superviseur` dans du code neuf (décision n°13).
- `Depense(effectue_par=superviseur)` réduit le solde individuel de ce superviseur, pas la caisse globale — ne jamais compter la même dépense dans les deux.
- `RecouvrementSuperviseur` réduit le solde individuel du superviseur concerné (décision n°13, remplace la décision n°8).
- Aucun solde d'ouverture, aucune clôture : `solde_superviseur`/`solde_caisse_globale` toujours calculés depuis `DATE_DEBUT_FINANCE` (`2026-07-01`) jusqu'à `date_fin` — ne jamais réintroduire un paramètre `date_debut` par requête, ni reculer cette constante sans nouvelle décision explicite (décision n°14).
- Comparaisons de dates sur des `DateTimeField` timezone-aware toujours faites via `__date__gte`/`__date__lte`, jamais directement contre un `date` naïf (sinon avertissement de fuseau et frontière de journée potentiellement décalée).

---

## Critères de validation (Definition of Done)

- [x] `manage.py check` propre après migration des `limit_choices_to` et ajout de `peut_faire_depense`.
- [x] mdmaiga peut recouvrer un superviseur et enregistrer un versement (vente + hors-vente séparés) avec reçu, sans passer par le compte `rot` d'Abdoulaye — via l'action groupée US-07 en usage courant, ou les vues individuelles par URL directe.
- [x] Le dashboard `finance` affiche un solde par superviseur cohérent avec la formule officielle (pas de double comptage des ventes personnelles).
- [x] Une dépense enregistrée sans versement associé réduit immédiatement le solde affiché (vue `creer_depense` fonctionnelle, non liée dans l'UI par choix de mdmaiga).
- [x] `montant_hors_vente` est visible dans le détail du versement mais absent du calcul de solde.
- [x] Aucune régression sur `agents/services/*`, `direction/services/cloture_service.py` ni les propriétés `Agent.solde_*` (non touchés par ce sprint).
- [x] Accès à `finance/` refusé à tout agent qui n'est pas `est_direction`.
- [x] L'action groupée (US-07) traite plusieurs superviseurs en une soumission, ignore sans erreur les lignes vides, et le solde diminue bien après traitement (vérifié : `solde_fin` avant/après cohérent avec le montant saisi).
- [x] Le détail des mouvements par superviseur est paginé (30/page).
- [x] Le solde superviseur et la caisse globale sont deux valeurs distinctes, jamais mélangées, calculées sans dépendance à `ClotureMensuelle` — vérifié via `solde_superviseur`/`solde_caisse_globale` sur les données réelles.
- [x] `VersementBancaire`/`Depense(ROT-direction)` n'affectent plus le solde d'un superviseur individuel ; `RecouvrementSuperviseur` réduit bien le sien.
- [x] Coupure au 01/07/2026 (`DATE_DEBUT_FINANCE`) appliquée à `solde_superviseur`, `solde_caisse_globale` et à la fenêtre de consultation des mouvements — l'anomalie "déjà remis > encaissé" a disparu pour les soldes superviseur sur les données réelles (vérifié : tous positifs après la coupure). La caisse globale reste négative, résidu assumé des tests effectués avant l'introduction de la coupure (versement de l'ancien solde mal borné) — pas une anomalie du code.

---

## Fichiers à créer / modifier

| Fichier | Action |
|---------|--------|
| `core/models.py` | Modifier — `limit_choices_to` sur `RecouvrementSuperviseur.rot` et `VersementBancaire.effectue_par` ; ajout `Agent.peut_faire_depense` |
| `core/migrations/0107_extend_finance_permissions_and_peut_faire_depense.py` | Créé via `makemigrations` |
| `core/forms.py` | Modifier — `VersementForm.save()` accepte `rot.est_rot or rot.est_direction` (décision n°9) |
| `dams/settings.py` | Modifier — ajout `'finance'` |
| `dams/urls.py` | Modifier — `path('finance/', ...)` |
| `finance/__init__.py`, `apps.py`, `urls.py`, `views.py`, `forms.py`, `services.py` | Créés |
| `finance/APP_FINANCE.md` | Créé — documentation de l'app (pattern `APP_*.md`) |
| `finance/templates/finance/*.html` | Créés (héritent de `base_admin.html`) — dont `recouvrement_versement_groupe.html` (US-07) |
| `direction/templates/base_admin.html` | Modifier — lien "Solde superviseurs" + correction de la condition de surbrillance du lien "Versements" |

### Révision majeure post-livraison (décision n°13 — modèle à deux niveaux)

Remplace les "ajouts post-livraison" précédents (décisions n°11/n°12, désormais superédées et retirées) :

| Fichier | Action |
|---------|--------|
| `finance/services.py` | Réécrit — `solde_superviseur`/`solde_caisse_globale` remplacent `calculer_solde_superviseur` ; suppression de toute logique `ClotureMensuelle` (`_borne_ouverture`, `cloturer_superviseur`, etc.) |
| `finance/views.py` | Modifier — suppression des vues `cloturer_tous`/`cloturer_un_superviseur` ; `detail_solde_superviseur` n'affiche plus `VersementBancaire` dans les mouvements ; `recouvrement_versement_groupe` ne renseigne plus `VersementBancaire.superviseur` |
| `finance/forms.py` | Modifier — `VersementBancaireForm` perd son champ `superviseur` |
| `finance/urls.py` | Modifier — retrait de `cloturer-tous/`, `superviseur/<pk>/cloturer/` |
| `finance/templates/finance/dashboard.html` | Modifier — bloc "Caisse globale", colonnes renommées, retrait du bouton "Clôturer tous" |
| `finance/templates/finance/detail_solde_superviseur.html` | Modifier — retrait du bouton "Clôturer maintenant", mouvements = encaissements/dépenses perso/remises (plus de versements) |
| `finance/templates/finance/creer_versement.html` | Modifier — retrait du champ superviseur |
| `finance/templates/finance/historique_versements.html` | Modifier — retrait de la colonne "Superviseur" |

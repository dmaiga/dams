# APP_FINANCE.md

## Rôle

`finance` est la troisième app **orientée capacité métier** de DAMS — "Flux de trésorerie".

Elle devient la **source unique de vérité** du solde superviseur (cash détenu, non encore remis), un calcul qui était jusqu'ici dispersé et incohérent sur au moins quatre endroits (`Agent.solde_*`, `direction/services/cloture_service.py`, `agents/services/rot_dashboard_service.py`). Elle porte aussi le recouvrement de la recette d'un superviseur, l'enregistrement du versement bancaire réel et la saisie des dépenses.

**Contexte métier (modèle à deux niveaux — voir décision n°13, sprint-03) :**

1. Un superviseur récupère l'argent de ses agents (vente comptant → `Recouvrement` automatique, géré par `vente/`). Il détient ce cash **personnellement**, tant qu'il ne l'a pas remis.
2. **mdmaiga** (Direction) — ou un ROT — recouvre cette recette (`RecouvrementSuperviseur`) : à partir de cet instant, l'argent est **mutualisé**, il n'appartient plus à un superviseur en particulier.
3. mdmaiga effectue les dépenses (`Depense`) et le versement bancaire réel (`VersementBancaire`) **depuis cette caisse mutualisée** — ces deux événements ne concernent plus un superviseur individuel, seulement l'acteur qui les a effectués (`effectue_par`).

`finance/` reflète donc **deux soldes distincts**, jamais mélangés : le solde de chaque superviseur ("combien me doit-il encore ?") et la caisse globale ("combien ai-je réellement en main après mutualisation ?").

Voir `docs/sprints/sprint-03.md` pour le détail des décisions et de la formule.

---

## Frontières

| Ce que l'app possède | Ce qu'elle ne touche pas |
|---|---|
| Solde par superviseur (`solde_superviseur`) et caisse globale (`solde_caisse_globale`) | Les 5 propriétés `Agent.solde_*` existantes (non nettoyées, non dépréciées ce sprint) |
| Recouvrement de la recette superviseur → acteur admin | `agents/services/rot_dashboard_service.py`, `direction/services/cloture_service.py`, `Agent.solde_rot` (non migrés, continuent de fonctionner tels quels) |
| Versement bancaire (montant vente + hors vente séparés, reçu) | `ClotureMensuelle`/`cloturer_mois` — `finance/` ne s'appuie sur aucune clôture, calcul 100% dynamique |
| Dépense (personnelle à un superviseur, ou de la caisse globale) | Ouverture de `peut_faire_depense` dans l'UI superviseur (`vente/`) — champ ajouté sur `Agent`, exploitation UI hors périmètre |
| Historique/détail des mouvements par superviseur | Paiements fournisseurs (`PaiementFournisseur`, resté dans `direction/`) |

---

## URLs (`/finance/`)

| Nom | URL | Accès | Exposée dans l'UI |
|---|---|---|---|
| `finance:dashboard_finance` | `/finance/` | direction | Oui — menu FINANCE ("Solde superviseurs") |
| `finance:detail_solde_superviseur` | `/finance/superviseur/<pk>/` | direction | Oui — bouton "Détail" du dashboard |
| `finance:recouvrement_versement_groupe` | `/finance/recouvrement-versement/` | direction | Oui — bouton principal du dashboard |
| `finance:recouvrer_superviseur` | `/finance/recouvrer/<pk>/` | direction | **Non** — superflue depuis l'action groupée, gardée en code pour correction ponctuelle |
| `finance:creer_versement` | `/finance/versement/nouveau/` | direction | **Non** — idem |
| `finance:creer_depense` | `/finance/depense/nouvelle/` | direction, ou agent avec `peut_faire_depense` | **Non** — la saisie de dépenses n'est pas suivie pour l'instant |
| `finance:historique_versements` | `/finance/versements/` | direction | **Non** — plus liée depuis que "Nouveau versement" a été retiré du menu |
| `finance:historique_depenses` | `/finance/depenses/` | direction | **Non** — idem |

Les vues et templates marqués "Non" restent en place (code, urls.py, templates intacts) — seuls les liens de navigation ont été retirés, sur demande explicite, pour ne pas encombrer l'interface avec des actions redondantes ou non utilisées. Elles restent accessibles par URL directe si besoin d'une correction ponctuelle.

Guards locaux (pattern de permission par capacité, voir `rules/ARCHITECTURE.md`) :
- `_acces_finance(agent) = agent.est_direction`
- `_acces_depense(agent) = agent.est_direction or agent.peut_faire_depense`

### Action groupée (`finance:recouvrement_versement_groupe`)

Remplace dans l'usage quotidien les deux actions individuelles `recouvrer_superviseur` + `creer_versement` : un formset (`RecouvrementVersementFormSet`, `finance/forms.py`) avec une ligne par superviseur actif, montant préempli avec son solde réel actuel (`lister_soldes_superviseurs()`), champ "apport hors vente" et upload de reçu. À la soumission, chaque ligne renseignée crée à la fois un `RecouvrementSuperviseur` (réduit le solde individuel du superviseur) **et** un `VersementBancaire` (+ `RecuVersement` si fichier joint, réduit la caisse globale) dans une transaction atomique. Une ligne laissée vide (superviseur sans recette) n'est simplement pas traitée — pas d'erreur de validation.

---

## Modèles utilisés (définis dans `core`)

| Modèle | Usage |
|---|---|
| `Agent` | Nouveau champ `peut_faire_depense` (booléen, indépendant du rôle) — permet plus tard à un superviseur de saisir ses propres dépenses ; seule la vue vérifie ce flag, `Depense.effectue_par` n'a aucune restriction modèle |
| `RecouvrementSuperviseur` | `rot` étend `limit_choices_to` à `type_agent__in=['rot','direction']` — mdmaiga (`type_agent='direction'`) peut désormais y figurer. **Le seul champ correctement attribué à un superviseur source** (`superviseur`). Chaque enregistrement réduit le solde individuel de ce superviseur. |
| `VersementBancaire` | `effectue_par` étendu de la même façon. **`superviseur` n'est PAS une attribution de source** — c'est un champ historique qui joue le même rôle que `effectue_par` ("qui a effectué l'action"), devenu redondant depuis l'introduction de `effectue_par` (voir décision n°13). `finance/` ne le renseigne plus jamais dans le nouveau code ; le versement est un événement de la caisse globale, filtré uniquement par date, jamais par superviseur. |
| `Recouvrement` | Encaissement du superviseur — couvre déjà les ventes des agents **et** les ventes personnelles du superviseur (auto-distribution). Ne jamais additionner `Vente(agent=superviseur)` en plus (source du double comptage dans `cloture_service.py`) |
| `Depense` | Selon `effectue_par` : si un superviseur (`peut_faire_depense`), réduit **son** solde individuel (dépense faite avant remise) ; si un ROT/direction, réduit la **caisse globale** (dépense faite après mutualisation). Ne jamais compter dans les deux à la fois. |
| `RecuVersement` | Upload de reçu(s), multiple, attaché au versement |

Migration `core/migrations/0107_extend_finance_permissions_and_peut_faire_depense.py`.

`ClotureMensuelle` **n'est plus utilisée par `finance/`** (voir décision n°13) : le calcul est entièrement dynamique sur l'historique complet de `Recouvrement`/`RecouvrementSuperviseur`/`Depense`/`VersementBancaire`, sans solde d'ouverture ni dépendance à une clôture.

---

## Service métier (`finance/services.py`)

### `solde_superviseur(superviseur, date_fin=None)`

Cash détenu par CE superviseur, pas encore remis :

```
solde = encaissements(Recouvrement) - depenses_perso(Depense, effectue_par=superviseur) - deja_remis(RecouvrementSuperviseur)
```

- Calcul dynamique depuis **`DATE_DEBUT_FINANCE`** (`date(2026, 7, 1)`, constante de module) — pas de borne basse arbitraire par requête, pas de "solde d'ouverture", pas de dépendance à `ClotureMensuelle`. L'historique antérieur (jugé incohérent : ancien paradigme superviseur, introduction tardive du rôle ROT) est délibérément ignoré — décision n°14, sprint-03.
- `date_fin` (paramètre, `aujourd'hui` par défaut) permet uniquement de consulter *"quel était le solde à telle date"* — toujours borné en bas par `DATE_DEBUT_FINANCE`.
- `alerte` : `solde >= SEUIL_ALERTE_SOLDE` (seuil `100 000 FCFA`, repris de `direction/services/alertes/solde.py::SoldeAlertService`).

**Historique** : une première version sommait tout l'historique sans borne basse (décision n°13). Constat en usage réel : `deja_remis` dépassait `encaissements` pour les 3 superviseurs de test, un signal jugé plus gênant qu'utile — mdmaiga a préféré couper franchement au 01/07/2026 plutôt que d'investiguer des données de test anciennes (décision n°14).

### `lister_soldes_superviseurs(date_fin=None)`

Applique `solde_superviseur` à tous les superviseurs actifs (`type_agent='entrepot', est_actif=True`), pour alimenter le dashboard.

### `solde_caisse_globale(date_fin=None)`

Cash détenu par les acteurs admin (ROT/direction) une fois la recette de tous les superviseurs mutualisée :

```
solde = recouvre(RecouvrementSuperviseur, tous superviseurs) - depenses(Depense, effectue_par ROT/direction) - versements(VersementBancaire.montant_vente)
```

Jamais filtré par `superviseur`. Affichée en haut du dashboard, à côté (et non mélangée avec) la liste des soldes individuels. Bornée en bas par `DATE_DEBUT_FINANCE` comme `solde_superviseur`.

---

## Forms (`finance/forms.py`)

Réutilisation maximale de l'existant plutôt que duplication :

- **`RecouvrementSuperviseurForm`** — réexporté tel quel depuis `agents.forms` (superviseur, montant, date, commentaire ; `.rot` est fixé par la vue, pas de restriction de type sur le formulaire lui-même — déjà réutilisable sans modification).
- **`DepenseForm`** — réexporté tel quel depuis `core.forms` (`Depense.effectue_par` n'a aucune restriction modèle).
- **`VersementBancaireForm`** — **nouveau**, sans champ `superviseur` (contrairement à une version antérieure de ce sprint qui en ajoutait un par erreur — voir décision n°13). Champs : `montant_vente`, `montant_hors_vente`, `description`, `date_versement_reelle`, upload reçu(s) (`recus`/`recus_description` → `RecuVersement`). `.save(effectue_par)` accepte `est_rot` **ou** `est_direction`.
- **`DepenseFinanceForm(DepenseForm)`** — ajoute un champ optionnel `agent_cible` (ROT, superviseur ou direction) pour permettre à mdmaiga de saisir une dépense au nom d'un agent plutôt qu'en son propre nom ; masqué côté vue si l'utilisateur n'est pas direction.
- **`LigneRecouvrementVersementForm` + `RecouvrementVersementFormSet`** (`forms.formset_factory`) : une ligne par superviseur pour l'action groupée — `superviseur` (hidden), `montant`, `montant_hors_vente`, `recu`, tous optionnels sauf `superviseur`.

**Changement partagé (`core/forms.py`)** : `VersementForm.save()` acceptait uniquement `rot.est_rot` et levait une `ValueError` sinon — bloquant explicitement mdmaiga. Étendu à `rot.est_rot or rot.est_direction`, sans changement de comportement pour le flux ROT existant (`core/views.py::creer_versement`).

---

## Vues (`finance/views.py`)

Deux notions de "date" bien séparées, avec des paramètres GET distincts :

- `_get_date_solde(request)` : une seule date (`GET date_fin`, aujourd'hui par défaut) — "solde à la date du...". Ne change jamais la nature du calcul (toujours dynamique sur tout l'historique jusqu'à cette date).
- `_get_periode_mouvements(request)` : une fenêtre libre (`GET mvt_debut`/`mvt_fin`, mois en cours par défaut) — purement pour consulter l'historique des mouvements dans `detail_solde_superviseur`.

Vues :
- `dashboard_finance` : liste des soldes (`lister_soldes_superviseurs`) + caisse globale (`solde_caisse_globale`) + compteur d'alertes.
- `detail_solde_superviseur` : solde du superviseur + mouvements **paginés** (`Paginator`, 30/page). Les mouvements affichés sont `Recouvrement` (encaissement, +), `Depense` personnelle (-) et `RecouvrementSuperviseur` (remise, -) — **jamais `VersementBancaire`**, qui n'appartient plus à ce superviseur une fois la recette mutualisée.
- `recouvrement_versement_groupe` : voir section dédiée ci-dessus — action principale au quotidien.
- `recouvrer_superviseur` / `creer_versement` / `creer_depense` : conservées, non exposées dans l'UI (voir tableau des URLs).
- `historique_versements` / `historique_depenses` : listes complètes, non filtrées, triées par date décroissante (colonne "Superviseur" retirée de `historique_versements.html`, ce champ n'ayant plus de sens).

---

## Templates

Héritent de `base_admin.html` (espace direction), style DaisyUI/Tailwind cohérent avec `direction/templates/direction/factures/*.html`.

| Template | Description |
|---|---|
| `dashboard.html` | Stats "caisse globale" en haut, tableau des soldes par superviseur (encaissements / dépenses perso / déjà remis / reste à remettre), sélecteur "solde à la date du", badge alerte, bouton vers l'action groupée. |
| `detail_solde_superviseur.html` | Stats (encaissements/dépenses perso/déjà remis/reste à remettre) + tableau paginé des mouvements sur une fenêtre filtrable séparément (dates sans l'heure). |
| `recouvrement_versement_groupe.html` | Formset `RecouvrementVersementFormSet` — une ligne par superviseur (nom, solde actuel en lecture seule, montant, apport hors vente, reçu). |
| `recouvrer_superviseur.html` | Formulaire `RecouvrementSuperviseurForm` — non lié dans la navigation. |
| `creer_versement.html` | Formulaire `VersementBancaireForm` (sans champ superviseur) + upload de reçu(s) — non lié dans la navigation. |
| `creer_depense.html` | Formulaire `DepenseFinanceForm` — non lié dans la navigation. |
| `historique_versements.html` | Liste complète des versements (effectué par, montants, nombre de reçus), dates sans l'heure. |
| `historique_depenses.html` | Liste complète des dépenses (effectuée par, catégorie, note, montant). |

Lien ajouté dans le menu FINANCE de `direction/templates/base_admin.html` ("Solde superviseurs"), sans modifier les entrées existantes ("Versements"/"Dépenses"/"Factures Fournisseurs", qui restent des vues `direction_*` non remplacées ce sprint). Le lien direction "Versements" (`versements_direction`) exclut désormais explicitement le namespace `finance` de sa condition de surbrillance (`request.resolver_match.namespace != 'finance'`).

---

## Invariants

- `montant_hors_vente` n'entre jamais dans `solde_caisse_globale` (traçable dans le détail du versement, absent du calcul).
- `VersementBancaire` et `Depense(effectue_par=ROT/direction)` sont des événements de la **caisse globale**, jamais attribués à un superviseur individuel — ne jamais filtrer `VersementBancaire` par `superviseur` dans du code neuf (champ historique déprécié, voir décision n°13).
- `Depense(effectue_par=superviseur)` réduit le solde individuel de ce superviseur, pas la caisse globale — ne jamais compter la même dépense dans les deux.
- Un seul flux d'encaissement (`Recouvrement`), jamais additionné avec `Vente(agent=superviseur)` en parallèle.
- Aucun solde d'ouverture, aucune clôture : `solde_superviseur`/`solde_caisse_globale` sont calculés depuis `DATE_DEBUT_FINANCE` (`2026-07-01`) jusqu'à `date_fin` — jamais avant cette constante (décision n°14). Toute fenêtre de consultation (mouvements, historiques) doit aussi être bornée par elle.
- Comparaisons de dates sur des `DateTimeField` timezone-aware toujours faites via `__date__gte`/`__date__lte`/`__date__lte` (ou `.date()` côté Python), jamais directement contre un `date` naïf.
- Accès à `finance/` refusé à tout agent qui n'est pas `est_direction` (403 via `access_denied`) ; `creer_depense` élargi à `peut_faire_depense`.

---

## User stories couvertes

Voir `docs/sprints/sprint-03.md` (US-01 à US-07).

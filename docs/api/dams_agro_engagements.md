# Contrat API — `dams_agro` : Engagements superviseur ↔ champ

> **Contrat figé côté dams_agro** — repo séparé (`dams_champs`), terminé, aucune modification
> possible depuis `dams`. Ce document est la référence à réutiliser pour tout code (`dams`) qui a
> besoin d'appeler ces endpoints — évite de rouvrir l'autre repo pour vérifier un nom de champ.
> Source de vérité en cas de divergence : `dams_champs/engagements/` (`models.py`,
> `api_views.py`, `serializers.py`, `APP_ENGAGEMENTS.md`).

**Dernière vérification contre le code source** : 06/08/2026.

---

## Base URL & authentification

```
Base URL   : {API_URL}/api/engagements/     (API_URL = variable d'env, ex: http://127.0.0.1:8000)
Auth       : en-tête  X-Api-Key: <valeur>
Secret     : variable d'env DAMS_DISTRIBUTION_API_KEY — MÊME NOM ET MÊME VALEUR des deux côtés
             (dams_champs/.env et dams/.env), c'est un secret partagé, pas deux clés différentes.
Sans clé   : 403 Forbidden (HasDamsDistributionAPIKey)
```

C'est le **seul** groupe d'endpoints dams_agro qui accepte `POST`/écriture — tout le reste de
l'API dams_agro consommée par `dams` (`/api/dashboard/`, `/api/operations/`, `/api/cultures/`...)
reste strictement GET, sans authentification. Ne pas réutiliser ce header ailleurs.

Client HTTP côté `dams` : `analyse_champ/services.py` (`_post_json`, `creer_engagement_dams_agro`,
`_request_engagements`, `get_engagements_champ_superviseur`) — timeout 10s, toute erreur
(réseau/timeout/HTTP) levée comme `DamsAgroAPIError`, jamais silencieuse.

> ⚠️ **`POST /api/engagements/<id>/remboursements/` n'est plus appelé par `dams`
> depuis le 06/08/2026** (décision mdmaiga : le remboursement ne doit jamais être
> initié depuis `dams`, ça disperserait la responsabilité — c'est à dams_agro de
> l'indiquer). L'endpoint reste documenté ci-dessous pour référence (contrat
> dams_agro inchangé, potentiellement rappelable plus tard), mais `dams` ne fait
> plus que le **lire** via `GET /api/engagements/` (réconciliation, voir § Usage
> prévu plus bas) — jamais l'appeler en écriture.

---

## Modèle de données (rappel, côté dams_agro)

**`EngagementFinancier`** — l'avance ou la dépense elle-même :

| Champ | Type | Notes |
|---|---|---|
| `id` | int | |
| `nature` | `"avance_tresorerie"` \| `"depense_compte"` | seules valeurs valides |
| `nature_display` | string | libellé humain (lecture seule) |
| `reference_superviseur` | string (≤150) | **texte libre**, pas de FK — identifie le superviseur dams. Doit être **stable** (côté `dams` : `str(Agent.pk)`, jamais renommé une fois utilisé) |
| `reference_externe` | string (≤100, optionnel) | non utilisée actuellement côté `dams` |
| `technicien` | int \| null | FK `users.User` **côté dams_agro** — sans rapport avec `dams`, ne jamais y mettre un id d'`Agent` dams |
| `technicien_nom` | string \| null | lecture seule |
| `montant_initial` | string décimal (`"50000.00"`) | |
| `montant_rembourse` | string décimal, **calculé, jamais stocké** | somme des remboursements liés |
| `reste_a_rembourser` | string décimal, **calculé** | `montant_initial - montant_rembourse` |
| `etat` | `"ouvert"` \| `"partiel"` \| `"solde"` | **calculé**, jamais stocké |
| `label` | string (≤255) | |
| `date_engagement` | date `YYYY-MM-DD` | optionnel en écriture → défaut = date du jour dams_agro |
| `note` | text | |
| `operation_generee` | int \| null | lecture seule — id interne dams_agro (`finance.Operation`), sans intérêt côté `dams` |
| `created_at` | datetime ISO | lecture seule |

**`RemboursementEngagement`** — un remboursement (partiel ou total) rattaché à un engagement :

| Champ | Type | Notes |
|---|---|---|
| `id` | int | |
| `montant` | string décimal | doit être `> 0` et `≤ reste_a_rembourser` de l'engagement au moment de l'appel |
| `date_remboursement` | date `YYYY-MM-DD` | optionnel en écriture → défaut = date du jour dams_agro |
| `reference_externe` | string (≤100, optionnel) | |
| `note` | text | |
| `operation_generee` | int \| null | lecture seule |
| `created_at` | datetime ISO | lecture seule |

`montant_rembourse`/`reste_a_rembourser`/`etat` sont **toujours** recalculés côté dams_agro au
moment de la requête — jamais de valeur à faire confiance côté client si elle a été mise en cache
plus de quelques secondes.

---

## Endpoints

### `POST /api/engagements/` — créer un engagement

**Payload (JSON)** :
```json
{
  "nature": "avance_tresorerie",
  "montant_initial": "50000",
  "label": "Avance carburant",
  "reference_superviseur": "2",
  "note": "commentaire libre (optionnel)"
}
```
Champs obligatoires : `nature`, `montant_initial`, `label`, `reference_superviseur`.
Champs optionnels : `reference_externe`, `technicien`, `date_engagement`, `note`.

**Réponse `201 Created`** : l'objet `EngagementFinancier` complet (voir tableau ci-dessus),
notamment `id` — **à conserver côté `dams`** (`Depense.reference_dams_agro`), c'est la seule
façon de rembourser cet engagement plus tard.

**Erreurs** :
- `400` — validation refusée (ex. `montant_initial` négatif, `nature` invalide) : corps JSON
  `{"champ": ["message"]}` (format DRF standard).
- `403` — `X-Api-Key` manquante ou invalide.

**Effet côté dams_agro** (rappel métier, pour comprendre ce qu'on déclenche) :
- `avance_tresorerie` → génère une `Operation` revenu dans la finance dams_agro (le solde du
  champ augmente réellement).
- `depense_compte` → ne génère **aucune** `Operation` (le champ ne reçoit jamais cet argent).

---

### `GET /api/engagements/` — lister

**Query params (tous optionnels, cumulables)** :

| Param | Exemple | Effet |
|---|---|---|
| `nature` | `?nature=avance_tresorerie` | filtre exact |
| `technicien` | `?technicien=7` | filtre exact (id `users.User` dams_agro) |
| `reference_superviseur` | `?reference_superviseur=2` | **le plus utile côté `dams`** — récupère uniquement les engagements de ce superviseur |
| `etat` | `?etat=partiel` | `ouvert` \| `partiel` \| `solde` |
| `period` | `?period=month` | `DateFilterMixin` — filtre sur `date_engagement` |
| `date_from` / `date_to` | `?date_from=2026-08-01` | idem |

**Réponse `200`** : liste JSON (array), **non paginée**.

---

### `GET /api/engagements/dashboard/` — indicateurs agrégés

Mêmes query params que la liste (`reference_superviseur`, `period`, `date_from`, `date_to`) —
**pas de filtre `nature`/`etat`/`technicien` ici**.

**Réponse `200`** :
```json
{
  "nombre_engagements": 2,
  "total_engage": 100000.0,
  "total_avance_tresorerie": 50000.0,
  "total_depense_compte": 50000.0,
  "total_rembourse": 72000.0,
  "reste_a_rembourser": 28000.0,
  "nombre_ouverts": 0,
  "nombre_partiels": 1,
  "nombre_soldes": 1
}
```
⚠️ Ici les montants sont rendus en **`float`** (pas en string), contrairement à
`EngagementFinancierSerializer` — cohérent avec le style des autres endpoints "dashboard" de
dams_agro (`/api/dashboard/`), mais **incohérent avec `/api/engagements/`** (string). Ne pas
supposer un type unique pour tous les montants de cette API : vérifier au cas par cas.

**Non utilisé côté `dams`** pour la réconciliation — ce endpoint ne donne qu'un total
agrégé (`reste_a_rembourser` pour l'ensemble des engagements du superviseur), pas de
détail par engagement, donc pas assez précis pour savoir **quelle** `Depense` locale
mettre à jour. La réconciliation réelle (`finance.services.synchroniser_engagements_champ`,
implémentée le 06/08/2026) utilise plutôt `GET /api/engagements/?reference_superviseur=...`
ci-dessus (liste, `reste_a_rembourser` par engagement, matché par `id` ==
`Depense.reference_dams_agro`).

---

### `GET /api/engagements/<id>/` — détail

**Réponse `200`** : l'objet `EngagementFinancier`, **plus un champ `remboursements`** (array
d'objets `RemboursementEngagement` imbriqués, triés par date décroissante).

**Erreurs** : `404` si l'id n'existe pas.

**Deuxième usage côté `dams` (06/08/2026)** : `analyse_champ.services.get_engagement_detail`,
consommé par `operation_detail_view` (page Direction `finance_champs/operations/<pk>/`) pour
retrouver le commentaire réel (`note`/`label`) d'un engagement à partir de l'`Operation` générée
automatiquement côté dams_agro — celle-ci n'a qu'un `note` générique pour une avance ("Généré
automatiquement depuis l'engagement #N"), jamais le commentaire métier. L'id est extrait par regex
depuis `note`/`label` de l'Operation (`#(\d+)`), pas de champ dédié exposé côté API pour ce lien.

---

### `POST /api/engagements/<id>/remboursements/` — enregistrer un remboursement

**Payload (JSON)** :
```json
{
  "montant": "20000"
}
```
Seul `montant` est obligatoire. Optionnels : `date_remboursement`, `reference_externe`, `note`.

**Réponse `201 Created`** : l'objet `RemboursementEngagement` créé (`id` à conserver si un lien
1:1 avec un enregistrement local est utile — non exploité aujourd'hui côté `dams`).

**Erreurs** :
- `400` — `montant ≤ 0`, ou `montant > reste_a_rembourser` de l'engagement au moment de l'appel.
  Corps : `{"detail": "Le montant dépasse le reste à rembourser (30000.00)."}`.
- `404` — engagement inexistant.

**Effet côté dams_agro** : génère **toujours** une `Operation` dépense (le solde du champ
diminue), quelle que soit la `nature` de l'engagement d'origine — un remboursement est une
sortie de cash réelle même pour une `depense_compte` (le champ n'avait rien reçu, mais rembourse
quand même une dette réelle envers le superviseur).

---

### `GET /api/engagements/<id>/remboursements/` — lister les remboursements d'un engagement

**Réponse `200`** : liste JSON (array) d'objets `RemboursementEngagement`, non paginée.

---

## Points de vigilance pour tout futur code `dams`

1. **`reference_superviseur` doit rester strictement stable dans le temps** pour un même `Agent`
   côté `dams` (aujourd'hui : `str(Agent.pk)`, voir `finance.services.reference_superviseur_dams_agro`).
   La changer casserait le lien avec tous les engagements déjà créés pour ce superviseur — aucun
   moyen de les retrouver autrement, c'est un champ texte libre sans FK.
2. **Types de montants incohérents entre endpoints** : string décimale sur
   `/api/engagements/` et `/api/engagements/<id>/`, `float` sur `/api/engagements/dashboard/`.
   Toujours `Decimal(str(valeur))` côté Python avant tout calcul, jamais de comparaison de
   float direct.
3. **Pas de pagination** sur `GET /api/engagements/` — acceptable vu le volume attendu (un seul
   agent dams habilité aujourd'hui, cf. `docs/sprints/sprint-06.md` § Suggestions
   complémentaires, point 1), mais à surveiller si le volume augmente.
4. **Aucune suppression/annulation** d'engagement ou de remboursement dans ce contrat — une
   erreur de saisie ne peut être corrigée qu'en compensant manuellement (voir sprint-06, point 5).
5. **`technicien` (id `users.User` dams_agro) n'a aucun rapport avec un id `Agent` de `dams`** —
   ne jamais les confondre ; ce champ n'est d'ailleurs pas utilisé par l'intégration actuelle.

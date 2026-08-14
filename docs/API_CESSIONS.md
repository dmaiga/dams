# API_CESSIONS.md

## Rôle

Point d'entrée par lequel **dams_champs** (app `cessions`) transmet à
**dams** les produits agricoles cédés à DAMS Distribution.

`dams_champs` reste la **source de vérité** de la notion métier "cession"
(`cessions.Cession`, avec son propre cycle de vie et son propre statut de
transmission — voir `dams_champs/cessions/APP_CESSIONS.md`). `dams` ne
recrée aucune notion parallèle : il se contente de recevoir chaque cession
et de la matérialiser comme un `LotEntrepot` de stock central, exactement
comme s'il s'agissait d'une réception manuelle par un gestionnaire de
stock.

C'est le **seul endpoint du repo `dams` accepté en écriture** — tous les
autres endpoints de `dams` sont des vues web (session), et `dams` reste
par ailleurs lecteur seul vis-à-vis de `dams_agro` via `analyse_champ`
(GET uniquement, `rules/ARCHITECTURE.md`). Le sens de cet endpoint est
inverse à celui d'`analyse_champ`.

---

## Endpoint

```
POST /api/cessions/
```

### Authentification

En-tête `X-Api-Key`, comparé (temps constant, `hmac.compare_digest`) à
`settings.DAMS_CHAMPS_API_KEY` (voir `marchandise/permissions.py` —
`HasDamsChampsAPIKey`). Variable d'environnement dédiée, jamais codée en
dur — distincte de `DAMS_DISTRIBUTION_API_KEY`, qui authentifie `dams` en
tant qu'**appelant** vers `dams_agro` sur son `/api/engagements/` (sens
inverse). Réponse `403` si l'en-tête est absent ou invalide.

### Payload

```json
{
    "idempotency_key": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "produit": "concombre",
    "quantite": "10.00",
    "prix_cession": "1000.00",
    "date_cession": "2026-08-14"
}
```

| Champ             | Type                | Contrainte                                  |
|--------------------|---------------------|-----------------------------------------------|
| `idempotency_key`  | UUID                | Requis — identifie la cession de façon stable côté dams_champs (`Cession.idempotency_key`) |
| `produit`          | string              | Requis — nom du produit agricole (`core.models.Produit.nom`), doit déjà exister |
| `quantite`         | decimal (string)    | Requis, `> 0`                                  |
| `prix_cession`     | decimal (string)    | Requis, `>= 0` — **prix unitaire**, pas un montant total |
| `date_cession`     | date `AAAA-MM-JJ`   | Requis                                         |

Contrat volontairement minimal — ne pas ajouter de champ sans besoin
identifié des deux côtés.

### Réponses

**`201 Created`** — cession intégrée pour la première fois :

```json
{
    "status": "created",
    "idempotency_key": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "lot_id": 123,
    "reference_lot": "20260814-0004"
}
```

**`200 OK`** — cession déjà intégrée (même `idempotency_key` reçue une
seconde fois) : même corps de réponse, `"status": "already_exists"`, avec
le `lot_id`/`reference_lot` du lot déjà créé. Choix documenté : `200` (et
non `409 Conflict`) parce que du point de vue de l'émetteur, ce n'est pas
une erreur — le résultat souhaité (le lot existe) est bien atteint, de
façon idempotente.

**`400 Bad Request`** — payload invalide (champ manquant, quantité/prix
invalide, date invalide) **ou** produit/agent de réception introuvable
côté `dams` :

```json
{"detail": "Produit inconnu côté DAMS Distribution : « patate ». ..."}
```

**`403 Forbidden`** — clé API absente ou invalide.

---

## Traitement côté `dams`

Voir `marchandise/services.py::CessionReceptionService.recevoir_cession` —
appelé depuis `marchandise/api_views.py::CessionReceptionAPIView` (vue
mince : authentification, validation du payload via
`marchandise/serializers.py::CessionReceptionSerializer`, délégation).

### Correspondance Cession → Produit → Fournisseur → Agent → LotEntrepot

| Champ `LotEntrepot`     | Origine                                                              |
|--------------------------|-----------------------------------------------------------------------|
| `produit`                | `Produit.objects.get(nom__iexact=payload.produit)` — **jamais créé automatiquement** ; `400` explicite si absent |
| `fournisseur`             | `Fournisseur.objects.get_or_create(nom="Champ DAMS")` — fournisseur déjà existant en base (36 lots au moment de l'implémentation), réutilisé tel quel, jamais dupliqué |
| `quantite_initiale`       | `payload.quantite`                                                    |
| `quantite_restante`       | `payload.quantite` (lot neuf, rien distribué)                         |
| `prix_achat_unitaire`     | `payload.prix_cession`                                                |
| `date_reception`          | `payload.date_cession` converti en `datetime` à minuit (fuseau du projet, `TIME_ZONE=UTC`) — convention documentée, en l'absence d'heure source |
| `receptionne_par`         | `Agent.objects.get(user__username="abdoulaye.kone")` — compte précis imposé par le contrat métier. **Ne pas confondre** avec l'agent ROT `kone.abdoulaye` (username inversé, rôle différent). Précondition : ce compte doit exister ; aucune création automatique, `400` explicite sinon |
| `reference_lot`           | `core.services.lot_service.generer_reference_lot()` — même mécanisme que la réception manuelle (`AAAAMMJJ-NNNN`) |
| `cession_idempotency_key` | `payload.idempotency_key` — clé d'idempotence, voir plus bas |

### Idempotence

`LotEntrepot.cession_idempotency_key` (`UUIDField`, `null=True, blank=True,
unique=True`) porte la clé d'idempotence. `NULL` pour tout lot reçu
manuellement (PostgreSQL autorise plusieurs `NULL` sous une contrainte
unique) — la contrainte ne s'applique qu'aux lots réellement issus d'une
cession.

Le service crée `LotEntrepot` + `MouvementStock` dans un même
`transaction.atomic()`. En cas de requêtes concurrentes portant la même
`idempotency_key`, la contrainte unique en base fait échouer l'une des deux
insertions (`IntegrityError`) — le service rattrape cette erreur, relit le
lot déjà créé par l'autre requête et répond `already_exists`. **La
protection n'est donc pas un simple `if exists()` applicatif** (non fiable
en cas de concurrence) mais une contrainte PostgreSQL.

### Mouvement de stock

Toute réception de lot — manuelle (`ReceptionLotForm.save()`,
`marchandise/views.py::reception_lot`) ou via cession — crée
systématiquement un `MouvementStock(type_mouvement='RECEPTION',
quantite=lot.quantite_initiale, date_mouvement=lot.date_reception)`. Même
invariant respecté dans les deux flux, aucune duplication de la logique de
génération de `reference_lot` (extraite dans
`core/services/lot_service.py::generer_reference_lot`, réutilisée par le
formulaire et par le service de réception de cession).

### Hors périmètre de cette phase

Pas de `Vente`, pas de `DetailDistribution`, pas d'affectation, pas de
mouvement de sortie — la seule opération métier est
`Cession → LotEntrepot`. Le lot créé rejoint le stock central
normalement : un gestionnaire de stock le retrouve dans
`marchandise:liste_lots` comme n'importe quel autre lot reçu, et peut
l'affecter à un superviseur via le workflow existant, inchangé.

Pas de webhook, pas de polling, pas de Celery, pas de synchronisation
planifiée — `dams_champs` appelle cet endpoint de façon synchrone au
moment de la déclaration de la cession (voir
`dams_champs/cessions/services.py::transmettre_cession`).

---

## Configuration (`.env`)

| Variable              | Rôle                                                          |
|-------------------------|------------------------------------------------------------------|
| `DAMS_CHAMPS_API_KEY`   | Clé attendue dans l'en-tête `X-Api-Key` sur `POST /api/cessions/` |

Côté `dams_champs`, la variable correspondante (valeur partagée, nom
différent car chaque repo nomme la clé depuis son propre point de vue) est
`DAMS_DISTRIBUTION_OUTBOUND_API_KEY` (voir
`dams_champs/cessions/APP_CESSIONS.md`).

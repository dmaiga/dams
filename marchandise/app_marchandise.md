# APP_MARCHANDISE.md

## Rôle

`marchandise` est la première app **orientée capacité métier** de DAMS.

Elle gère tout ce qui concerne le produit physique : réception, stock central, affectation aux superviseurs, historique des sorties.

Elle ne connaît ni les paiements, ni les banques, ni les dettes fournisseurs.

---

## Frontières

| Ce que l'app possède | Ce qu'elle ne touche pas |
|---|---|
| Réception de lot | PaiementFournisseur |
| Stock central (consultation) | VersementBancaire |
| Affectation lot → superviseur | Recouvrement |
| Historique des affectations | Dettes |
| Mouvements de stock (lecture) | Paie |

---

## URLs (`/marchandise/`)

| Nom | URL | Accès |
|---|---|---|
| `marchandise:liste_lots` | `/marchandise/` | gestionnaire_stock, rot |
| `marchandise:detail_lot` | `/marchandise/lot/<pk>/` | gestionnaire_stock, rot |
| `marchandise:reception_lot` | `/marchandise/reception/` | gestionnaire_stock, rot |
| `marchandise:affecter_superviseur` | `/marchandise/affecter/` | gestionnaire_stock, rot |
| `marchandise:historique_affectations` | `/marchandise/historique/` | gestionnaire_stock, rot |

---

## Modèles utilisés (définis dans `core`)

Les modèles restent dans `core.models`. `marchandise` les importe sans les posséder.

| Modèle | Usage |
|---|---|
| `LotEntrepot` | Unité centrale de stock |
| `AffectationLotSuperviseur` | Sortie stock vers superviseur (avec prix gros/détail) |
| `MouvementStock` | Traçabilité des entrées/sorties |
| `MiseDispositionRot` | Créé à chaque affectation pour compatibilité historique |
| `Produit` | Référentiel produit |
| `Fournisseur` | Référentiel fournisseur |

---

## Forms (`marchandise/forms.py`)

### `AffectationSuperviseurForm`

Gère la sortie d'un lot du stock central vers un superviseur.

Champs : `produit`, `lot`, `superviseur`, `quantite`, `prix_gros`, `prix_detail`, `date_affectation`.

**Comportement clé :**
- `lot` queryset vide au GET — peuplé par AJAX sur changement de produit.
- En POST : queryset filtré sur `lot_id` soumis pour valider sans bloquer.
- `save(agent)` : crée `AffectationLotSuperviseur`, décrémente `lot.quantite_restante`, incrémente `lot.quantite_disponible_rot` (compatibilité ancienne logique).

---

## Templates

Tous les templates sont **mobile-first** : double layout Bootstrap (tableau `d-none d-md-block` / cartes `d-md-none`).

| Template | Description |
|---|---|
| `liste_lots.html` | Stock central paginé (30/page). Boutons "Détail" et "Affecter" distincts par lot. |
| `detail_lot.html` | Fiche lot : affectations superviseurs + mouvements de stock. |
| `reception_lot.html` | Réception avec toggle produit/fournisseur existant ou nouveau (même JS que core ROT). |
| `affecter_superviseur.html` | Formulaire d'affectation. Lots affichés en cartes cliquables après sélection produit (AJAX). |
| `historique_affectations.html` | Historique paginé (30/page). |

---

## Endpoint AJAX réutilisé

`/agents/ajax/lots-par-produit/?produit_id=X` — défini dans `agents/views.py`, réutilisé sans duplication pour peupler les lots dans le formulaire d'affectation.

---

## Invariants

- Une affectation décrémente `lot.quantite_restante` de manière atomique (`transaction.atomic` dans `save()`).
- Le bouton "Affecter" sur la liste est masqué si `lot.quantite_restante == 0`.
- Les prix (gros/détail) sont saisis par le gestionnaire de stock au moment de la sortie — le superviseur lui communique les prix lors de la demande.
- `lot.receptionne_par` est automatiquement renseigné avec l'agent connecté à la réception.

---

## User stories couvertes

### Gestionnaire de stock (Jean)

- Réceptionner un lot (produit existant ou nouveau, fournisseur existant ou nouveau).
- Consulter la liste du stock central avec quantités restantes.
- Accéder au détail d'un lot (affectations, mouvements).
- Affecter une quantité d'un lot à un superviseur avec prix gros/détail.
- Consulter l'historique de toutes les affectations.

### ROT (Abdoulaye)

- Accès complet en lecture et écriture sur les mêmes vues (`_acces_stock` = gestionnaire_stock **ou** rot).

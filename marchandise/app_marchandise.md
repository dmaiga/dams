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
| `AffectationLotSuperviseur` | Sortie stock vers superviseur (prix laissés vides — voir Invariants). Champ `agent_terrain_direct` renseigné si distribution directe. |
| `MouvementStock` | Traçabilité des entrées/sorties |
| `MiseDispositionRot` | Créé à chaque affectation pour compatibilité historique |
| `Produit` | Référentiel produit |
| `Fournisseur` | Référentiel fournisseur |
| `DistributionAgent` | Créé si distribution directe à un agent lors de l'affectation |
| `DetailDistribution` | Détail (lot, quantité, prix) de la distribution directe |

---

## Forms (`marchandise/forms.py`)

### `AffectationSuperviseurForm`

Gère la sortie d'un lot du stock central vers un superviseur — avec option de distribution directe à un agent pour casser la friction du flux en deux étapes (Jean → superviseur → agent).

Champs : `produit`, `lot`, `superviseur`, `agent_terrain` (optionnel), `quantite`, `date_affectation`.

**Comportement clé :**
- `lot` queryset vide au GET — peuplé par AJAX sur changement de produit.
- `agent_terrain` queryset vide au GET — peuplé par AJAX sur changement de superviseur (agents de type `terrain`, `agent_gros`, `agent_polivalent`, `stagiaire`, rattachés à ce superviseur).
- En POST : querysets `lot` et `agent_terrain` filtrés sur les ID soumis pour valider sans bloquer.
- `clean()` : rejette `agent_terrain` s'il n'est pas rattaché au `superviseur` sélectionné.
- `save(agent)` : crée toujours `AffectationLotSuperviseur` avec `prix_gros`/`prix_detail` à `None` (traçabilité du passage par le superviseur), décrémente `lot.quantite_restante`, incrémente `lot.quantite_disponible_rot` (compatibilité ancienne logique).
- Si `agent_terrain` est renseigné : crée en plus `DistributionAgent` + `DetailDistribution` (prix également `None`) vers cet agent dans la même transaction, renseigne `affectation.agent_terrain_direct` (traçabilité — sinon rien ne relierait l'affectation à la distribution créée) et met `affectation.quantite_restante = 0` (tout est parti directement, rien ne reste "en attente" chez le superviseur).

**Décision produit — pas de prix à cette étape :**
Le prix dépend du type de l'agent qui vendra (`terrain`/mami → détail uniquement, `agent_gros` → gros uniquement, `agent_polivalent`/`stagiaire` → libre, cf. `Agent.type_vente_par_defaut()`). Plutôt que de conditionner deux champs de prix ici, le gestionnaire de stock n'indique **aucun prix** à l'affectation : c'est le superviseur qui le saisira au moment d'enregistrer la vente de l'agent (avec le type de vente), pour plus de flexibilité. Cela laisse `AffectationLotSuperviseur.prix_gros/prix_detail` et `DetailDistribution.prix_gros/prix_detail` à `None` en sortie de `marchandise`.

**Libellés des `ModelChoiceField` — full name uniquement :**
`superviseur` et `agent_terrain` utilisent `label_from_instance = lambda obj: obj.full_name` (pas `Agent.__str__()` qui ajoute `- {type_agent_display}`, ni de type entre parenthèses). Objectif : listes déroulantes courtes et lisibles sur mobile, où un `<select>` natif avec des libellés trop longs peut déborder visuellement dans les outils d'inspection desktop (un vrai téléphone utilise un picker natif dimensionné à l'écran, donc ce n'est un souci qu'en émulation).

---

## Endpoint AJAX propre à l'app

`/marchandise/ajax/agents-par-superviseur/?superviseur_id=X` — retourne les agents actifs rattachés au superviseur, pour peupler `agent_terrain`.

---

## Templates

Tous les templates sont **mobile-first** : double layout Bootstrap (tableau `d-none d-md-block` / cartes `d-md-none`).

| Template | Description |
|---|---|
| `liste_lots.html` | Stock central paginé (30/page). Cartes mobiles avec libellés explicites "Reçu"/"Restant" (pas de chiffres nus). Boutons "Détail" et "Affecter" distincts par lot. |
| `detail_lot.html` | Fiche lot : affectations superviseurs + mouvements de stock. Affiche le destinataire direct (`superviseur → agent`) si `agent_terrain_direct` est renseigné. |
| `reception_lot.html` | Réception avec toggle produit/fournisseur existant ou nouveau (même JS que core ROT). |
| `affecter_superviseur.html` | Formulaire d'affectation en 3 étapes numérotées (produit & lot → destinataires → quantité & date). Lots affichés en cartes cliquables après sélection produit (AJAX). Bouton de validation collé en bas de l'écran (`sticky`) sur mobile. |
| `historique_affectations.html` | Historique paginé (30/page). Colonne/ligne "Destinataire" affichant `superviseur → agent` si distribution directe. Cartes mobiles avec libellés "Distribué"/"Restant" (plus de badge muet). |

**Sobriété visuelle (toutes les vues) :** les bordures colorées systématiques (`border-start border-4 border-success/primary`) ont été retirées des cartes mobiles. Une couleur (rouge) n'apparaît que si elle porte une information réelle — stock épuisé (`quantite_restante == 0`).

---

## Endpoint AJAX réutilisé

`/agents/ajax/lots-par-produit/?produit_id=X` — défini dans `agents/views.py`, réutilisé sans duplication pour peupler les lots dans le formulaire d'affectation.

---

## Vue externe affichant des données `marchandise`

`agents/templates/agents/affectations/dashboard_gestionnaire_stock.html` (vue `agents.views.dashboard_gestionnaire_stock`) affiche les "Dernières affectations" (`AffectationLotSuperviseur`) sur le tableau de bord du gestionnaire de stock. Mise à jour avec les mêmes règles que `historique_affectations.html` : colonne "Destinataire" (`superviseur → agent` si distribution directe), plus de bordure colorée systématique sur les cartes mobiles.

---

## Invariants

- Une affectation décrémente `lot.quantite_restante` de manière atomique (`transaction.atomic` dans `save()`).
- Le bouton "Affecter" sur la liste est masqué si `lot.quantite_restante == 0`.
- Les prix (gros/détail) ne sont **plus** saisis dans `marchandise` — ils sont laissés à `None` et seront indiqués par le superviseur au moment d'enregistrer la vente de l'agent, avec le type de vente.
- `lot.receptionne_par` est automatiquement renseigné avec l'agent connecté à la réception.

---

## User stories couvertes

### Gestionnaire de stock (Jean)

- Réceptionner un lot (produit existant ou nouveau, fournisseur existant ou nouveau).
- Consulter la liste du stock central avec quantités restantes.
- Accéder au détail d'un lot (affectations, mouvements).
- Affecter une quantité d'un lot à un superviseur (sans prix), avec option de distribution directe à un agent.
- Consulter l'historique de toutes les affectations.

### ROT (Abdoulaye)

- Accès complet en lecture et écriture sur les mêmes vues (`_acces_stock` = gestionnaire_stock **ou** rot).

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
| `AffectationLotSuperviseur` | Sortie de stock vers l'agent via son superviseur. `agent_terrain_direct` et `quantite_restante` restent des champs de compatibilité et de traçabilité. |
| `MouvementStock` | Traçabilité des entrées/sorties |
| `MiseDispositionRot` | Créé à chaque affectation pour compatibilité historique |
| `Produit` | Référentiel produit |
| `Fournisseur` | Référentiel fournisseur |
| `DistributionAgent` | Créé si distribution directe à un agent lors de l'affectation |
| `DetailDistribution` | Vérité économique de la distribution (quantité réellement distribuée, base des ventes et des recouvrements). |

---

## Forms (`marchandise/forms.py`)

### `AffectationSuperviseurForm`

Gère la sortie d'un lot du stock central vers un agent rattaché à son superviseur. La création de `DistributionAgent` et `DetailDistribution` fait partie du flux normal lorsqu'un agent est sélectionné.

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

## Service métier (`marchandise/services.py`)

### `AffectationLotService.corriger_affectation(...)`

Point d'entrée unique des corrections administratives d'une `AffectationLotSuperviseur`.

Le service est appelé depuis le `ModelAdmin` centralisé dans `core/admin.py` et peut être réutilisé par toute autre interface.

Il constitue le **miroir fonctionnel** de `AffectationSuperviseurForm.save()` : au lieu de créer les objets métier, il met à jour ceux déjà existants afin de conserver la cohérence du workflow.

**Règles appliquées :**

- Corrige les champs administratifs autorisés (`quantite`, `date_affectation`).
- Recalcule le delta de quantité entre l'ancienne et la nouvelle valeur.
- Met à jour de façon cohérente :
  - `LotEntrepot`
  - `AffectationLotSuperviseur`
  - `DistributionAgent`
  - `DetailDistribution`
- Maintient la cohérence entre le stock central et les quantités réellement distribuées.
- Refuse toute correction conduisant à un stock négatif ou à une incohérence métier.
- Une correction de date n'a aucun impact sur les stocks.

**Atomicité :**

Toutes les modifications sont exécutées dans une unique `transaction.atomic()` afin de garantir que l'ensemble des objets impactés restent synchronisés.

**Important :**

`DetailDistribution` constitue la vérité économique de la distribution. Les ventes et les recouvrements s'appuient sur sa quantité. Toute correction d'une affectation doit donc également mettre à jour `DetailDistribution` afin de conserver la cohérence du système.

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
- Toute correction administrative passe exclusivement par `AffectationLotService.corriger_affectation()`.
- Le service est le miroir de `AffectationSuperviseurForm.save()` : toute correction met à jour l'ensemble des objets impactés (`LotEntrepot`, `AffectationLotSuperviseur`, `DistributionAgent` et `DetailDistribution`) dans une unique transaction atomique.
- `DetailDistribution` reste la référence métier utilisée par les ventes et les recouvrements ; sa quantité doit toujours être synchronisée avec une correction d'affectation.
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
